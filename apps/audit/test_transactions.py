"""Real PostgreSQL transaction/context regressions, with synthetic temporary rows."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.db import DatabaseError, connection, transaction
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from audit.middleware import PostgreSQLAuditMiddleware
from audit.models import ChangeLog
from audit.services import AuditLogError, audit_request_state, register_audit_log


class AuditTransactionTests(SimpleTestCase):
    databases = {'default'}

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.get_autocommit())
        with connection.cursor() as cursor:
            cursor.execute('CREATE TEMP TABLE a10_probe (value integer, actor text, peer text)')
            cursor.execute('CREATE TEMP TABLE a10_commit_context (actor text)')
            cursor.execute("""
                CREATE OR REPLACE FUNCTION pg_temp.a10_capture() RETURNS trigger AS $$
                BEGIN
                    NEW.actor := current_setting('app.current_user_id', true);
                    NEW.peer := current_setting('app.client_ip', true);
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
            """)
            cursor.execute('CREATE TRIGGER a10_capture BEFORE INSERT ON a10_probe '
                           'FOR EACH ROW EXECUTE FUNCTION pg_temp.a10_capture()')
            cursor.execute("""
                CREATE OR REPLACE FUNCTION pg_temp.a10_deferred() RETURNS trigger AS $$
                BEGIN
                    INSERT INTO a10_commit_context VALUES (current_setting('app.current_user_id', true));
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
            """)
            cursor.execute('CREATE CONSTRAINT TRIGGER a10_at_commit AFTER INSERT ON a10_probe '
                           'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION pg_temp.a10_deferred()')
        self.addCleanup(self.cleanup_probe)

    def cleanup_probe(self):
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS a10_probe')
            cursor.execute('DROP TABLE IF EXISTS a10_commit_context')
            cursor.execute('DROP FUNCTION IF EXISTS pg_temp.a10_capture()')
            cursor.execute('DROP FUNCTION IF EXISTS pg_temp.a10_deferred()')

    def request(self, user=101, **meta):
        request = RequestFactory().get('/synthetic-audit/', REMOTE_ADDR='192.0.2.10', **meta)
        request.user = AnonymousUser() if user is None else SimpleNamespace(pk=user, is_authenticated=True)
        return request

    def insert(self, value=1):
        with connection.cursor() as cursor:
            cursor.execute('INSERT INTO a10_probe (value) VALUES (%s)', [value])

    def rows(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT value, actor, peer FROM a10_probe ORDER BY value')
            return cursor.fetchall()

    def context(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_user_id', true), "
                           "current_setting('app.client_ip', true)")
            return tuple(value or '' for value in cursor.fetchone())

    def test_authenticated_context_reaches_real_trigger_in_autocommit_and_is_restored(self):
        before = self.context()
        def view(request):
            self.assertTrue(connection.in_atomic_block)
            self.insert()
            return HttpResponse('ok')
        self.assertEqual(PostgreSQLAuditMiddleware(view)(self.request()).status_code, 200)
        self.assertEqual(self.rows(), [(1, '101', '192.0.2.10')])
        with connection.cursor() as cursor:
            cursor.execute('SELECT actor FROM a10_commit_context')
            self.assertEqual(cursor.fetchall(), [('101',)])
        self.assertEqual(self.context(), before)
        self.assertTrue(connection.get_autocommit())

    def test_reused_connection_has_exact_user_or_explicit_anonymous_context(self):
        for value, user in enumerate((101, 202, None), start=1):
            def view(request):
                self.insert(value)
                return HttpResponse('ok')
            PostgreSQLAuditMiddleware(view)(self.request(user))
        self.assertEqual([row[1] for row in self.rows()], ['101', '202', ''])

    def test_restores_existing_outer_transaction_context(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.current_user_id', 'outer', true), "
                               "set_config('app.client_ip', 'outer-peer', true)")
            PostgreSQLAuditMiddleware(lambda request: HttpResponse('ok'))(self.request())
            self.assertEqual(self.context(), ('outer', 'outer-peer'))
        self.assertNotEqual(self.context()[0], 'outer')

    def test_forwarded_header_cannot_forge_database_actor_address(self):
        def view(request):
            self.assertEqual(request.client_ip, '192.0.2.10')
            self.insert()
            return HttpResponse('ok')
        response = PostgreSQLAuditMiddleware(view)(self.request(HTTP_X_FORWARDED_FOR="198.51.100.2'; SELECT 1;--"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.rows()[0][2], '192.0.2.10')

    def test_invalid_peer_address_is_unknown_and_never_sql_source(self):
        request = self.request()
        request.META['REMOTE_ADDR'] = "x'; SELECT 1;--"
        def view(request):
            self.insert()
            return HttpResponse('ok')
        self.assertEqual(PostgreSQLAuditMiddleware(view)(request).status_code, 200)
        self.assertEqual(self.rows()[0][2], 'unknown')

    def test_context_failure_blocks_view_and_returns_generic_error(self):
        with patch.object(connection, 'cursor', side_effect=DatabaseError('SYNTHETIC_PRIVATE')), \
                self.assertLogs('apps.audit', level='ERROR') as logs:
            view = Mock()
            response = PostgreSQLAuditMiddleware(view)(self.request())
        self.assertEqual(response.status_code, 503)
        view.assert_not_called()
        self.assertNotIn('SYNTHETIC_PRIVATE', str(logs.output) + response.content.decode())
        self.assertIsNone(audit_request_state.get())

    def test_converted_500_response_rolls_back_writes(self):
        before = self.context()
        def view(request):
            self.insert()
            return HttpResponse('failed', status=500)
        self.assertEqual(PostgreSQLAuditMiddleware(view)(self.request()).status_code, 500)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.context(), before)

    def test_400_response_keeps_deliberate_state_such_as_failed_attempt_counter(self):
        def view(request):
            self.insert()
            return HttpResponse('bad code', status=400)
        self.assertEqual(PostgreSQLAuditMiddleware(view)(self.request()).status_code, 400)
        self.assertEqual(len(self.rows()), 1)

    def test_uncaught_exception_rolls_back_and_cleans_request_context(self):
        def view(request):
            self.insert()
            raise RuntimeError('synthetic')
        with self.assertRaises(RuntimeError):
            PostgreSQLAuditMiddleware(view)(self.request())
        self.assertEqual(self.rows(), [])
        self.assertIsNone(audit_request_state.get())

    def test_swallowed_audit_error_cannot_commit_or_return_success(self):
        def view(request):
            self.insert()
            # Even a nested caller swallowing the error cannot clear the request flag.
            with transaction.atomic():
                try:
                    register_audit_log(None, 'synthetic', 'A10', 'INVALID')
                except AuditLogError:
                    pass
            return HttpResponse('false success')
        with self.assertLogs('apps.audit', level='ERROR'):
            response = PostgreSQLAuditMiddleware(view)(self.request())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.rows(), [])
        self.assertIsNone(audit_request_state.get())
        response = PostgreSQLAuditMiddleware(lambda request: HttpResponse('ok'))(self.request())
        self.assertEqual(response.status_code, 200)

    def test_successful_audit_and_business_write_roll_back_together_on_later_error(self):
        key = 'A10_SYNTHETIC_ROLLBACK'
        def view(request):
            self.insert()
            register_audit_log(None, 'synthetic', key, 'INSERT', new_value={'synthetic': True})
            return HttpResponse('failed', status=500)
        PostgreSQLAuditMiddleware(view)(self.request())
        self.assertEqual(self.rows(), [])
        self.assertFalse(ChangeLog.objects.filter(record_key=key).exists())

    def test_sql_failure_is_visible_without_copying_row_values_to_logs(self):
        with self.assertLogs('apps.audit', level='ERROR') as logs:
            with self.assertRaises(AuditLogError) as error:
                with transaction.atomic():
                    register_audit_log(None, 'synthetic', 'A10_PRIVATE_KEY', 'INVALID',
                                       new_value={'private': 'SYNTHETIC_PRIVATE_VALUE'})
        message = str(logs.output) + str(error.exception)
        self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', message)
        self.assertNotIn('A10_PRIVATE_KEY', message)
        self.assertEqual(self.rows(), [])
