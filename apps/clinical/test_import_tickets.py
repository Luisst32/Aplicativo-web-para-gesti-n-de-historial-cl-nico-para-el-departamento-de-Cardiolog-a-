from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase, override_settings
from django.contrib.auth.models import Permission

from clinical.services.import_tickets import (
    store_upload, claim_upload, InvalidImportTicket, SALT, MAX_AGE,
)
from clinical.services import sav_importer
from security.models import User


class ImportTicketTests(SimpleTestCase):
    def setUp(self):
        root = self.enterContext(TemporaryDirectory(prefix='cardio-private-import-'))
        media = self.enterContext(TemporaryDirectory(prefix='cardio-media-import-'))
        self.enterContext(override_settings(IMPORT_TEMP_ROOT=root, MEDIA_ROOT=media))
        self.root = Path(root)
        self.user = SimpleNamespace(pk=11)
        self.other = SimpleNamespace(pk=12)

    def upload(self, extension='.csv'):
        return store_upload(BytesIO(b'synthetic,value\n1,2\n'), 'dataset' + extension, self.user)

    def test_valid_ticket_is_private_owner_bound_and_single_use(self):
        ticket, path = self.upload()
        self.assertEqual(path.parent, self.root.resolve())
        with claim_upload(ticket, self.user) as claimed:
            self.assertEqual(claimed.read_bytes(), b'synthetic,value\n1,2\n')
            self.assertFalse(path.exists())
        self.assertFalse(claimed.exists())
        with self.assertRaises(InvalidImportTicket):
            with claim_upload(ticket, self.user):
                self.fail('Replayed ticket accepted')

    def test_all_supported_extensions_preserve_parser_selection(self):
        for ext in ('.sav', '.zsav', '.csv', '.rds', '.rdata', '.rda', '.r'):
            ticket, _ = self.upload(ext)
            with claim_upload(ticket, self.user) as claimed:
                self.assertEqual(claimed.suffix, ext)

    def test_other_user_cannot_claim_or_delete_upload(self):
        ticket, path = self.upload()
        with self.assertRaises(InvalidImportTicket):
            with claim_upload(ticket, self.other):
                self.fail('Foreign ticket accepted')
        self.assertTrue(path.is_file())
        with claim_upload(ticket, self.user):
            pass

    def test_unsigned_paths_patterns_and_invalid_types_never_reach_filesystem(self):
        for token in ('../outside', '..\\outside', 'C:\\outside', '/tmp/outside', '*', '**',
                      'legacy-uuid', '', None, [], {}, 'a' * 2049):
            with self.subTest(token=type(token).__name__), patch(
                'clinical.services.import_tickets.private_root', side_effect=AssertionError('Filesystem touched'),
            ), self.assertRaises(InvalidImportTicket):
                with claim_upload(token, self.user):
                    self.fail('Invalid ticket accepted')

    def test_tampered_or_expired_token_is_rejected_without_claiming_file(self):
        ticket, path = self.upload()
        with self.assertRaises(InvalidImportTicket):
            with claim_upload(ticket + 'tampered', self.user):
                pass
        with patch('django.core.signing.time.time', return_value=4_000_000_000):
            with self.assertRaises(InvalidImportTicket):
                with claim_upload(ticket, self.user):
                    pass
        self.assertTrue(path.exists())

    def test_even_signed_payloads_cannot_supply_paths_or_extra_fields(self):
        invalid = [
            {'id': '../outside', 'ext': '.csv', 'owner': 11},
            {'id': 'a' * 32, 'ext': '../outside', 'owner': 11},
            {'id': 'a' * 32, 'ext': '.csv', 'owner': 11, 'path': '/outside'},
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(InvalidImportTicket):
                with claim_upload(signing.dumps(payload, salt=SALT), self.user):
                    pass

    def test_parallel_claims_have_exactly_one_winner(self):
        for attempt in range(20):
            with self.subTest(attempt=attempt):
                ticket, _ = self.upload()
                barrier = Barrier(8)

                def claim(_):
                    barrier.wait(timeout=10)
                    try:
                        with claim_upload(ticket, self.user) as claimed:
                            claimed.read_bytes()
                            return True
                    except InvalidImportTicket:
                        return False

                with ThreadPoolExecutor(max_workers=8) as pool:
                    outcomes = list(pool.map(claim, range(8)))
                self.assertEqual(outcomes.count(True), 1)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_failure_still_consumes_ticket_and_removes_claimed_file(self):
        ticket, _ = self.upload()
        with self.assertRaises(RuntimeError):
            with claim_upload(ticket, self.user):
                raise RuntimeError('Synthetic failure')
        self.assertEqual(list(self.root.iterdir()), [])


class ImportTicketEndpointTests(TestCase):
    def setUp(self):
        root = self.enterContext(TemporaryDirectory(prefix='cardio-api-import-'))
        self.enterContext(override_settings(IMPORT_TEMP_ROOT=root))
        self.root = Path(root)
        self.user = User.objects.create_user(username='ticket_owner', email='owner@example.invalid')
        self.other = User.objects.create_user(username='ticket_other', email='other@example.invalid')
        permissions = Permission.objects.filter(content_type__app_label='clinical')
        self.user.user_permissions.set(permissions)
        self.other.user_permissions.set(permissions)
        self.client.force_login(self.user)

    def analyze(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post('/clinical/api/import-sav/analyze/', {
            'file': SimpleUploadedFile('synthetic.csv', b'CODIGO\n1\n'),
        })

    def execute(self, ticket):
        return self.client.post('/clinical/api/import-sav/execute/',
                                {'temp_token': ticket}, content_type='application/json')

    def test_analyze_issues_ticket_and_owner_can_execute_it_once(self):
        response = self.analyze()
        self.assertEqual(response.status_code, 200)
        ticket = response.json()['temp_token']
        payload = signing.loads(ticket, salt=SALT, max_age=MAX_AGE)
        self.assertEqual(payload['owner'], self.user.pk)
        with patch.object(sav_importer, '_execute_staged_dataset', return_value={'success': True}) as execute:
            self.assertEqual(self.execute(ticket).status_code, 200)
            self.assertEqual(self.execute(ticket).status_code, 400)
            execute.assert_called_once()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_foreign_ticket_never_reaches_parser_or_mutations(self):
        ticket = self.analyze().json()['temp_token']
        self.client.force_login(self.other)
        with patch.object(sav_importer, '_execute_staged_dataset') as execute:
            self.assertEqual(self.execute(ticket).status_code, 400)
            execute.assert_not_called()
        self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_bad_token_types_and_traversal_return_400_without_parser(self):
        with patch.object(sav_importer, '_read_dataset_file') as read:
            for token in ('../outside', '*', [], {}, 123, None):
                with self.subTest(token=token):
                    self.assertEqual(self.execute(token).status_code, 400)
            read.assert_not_called()

    def test_failed_analysis_removes_temporary_file(self):
        with patch.object(sav_importer, '_read_dataset_file', side_effect=ValueError('Synthetic failure')):
            self.assertEqual(self.analyze().status_code, 400)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_service_entry_points_require_import_authorization(self):
        self.user.user_permissions.clear()
        with self.assertRaises(PermissionDenied):
            sav_importer.analyze_sav_file(BytesIO(b'synthetic'), 'dataset.csv', self.user)
        with self.assertRaises(PermissionDenied):
            sav_importer.execute_sav_import('invalid', self.user)
        self.assertEqual(list(self.root.iterdir()), [])
