"""Regression tests for A02, using synthetic clinical records only."""
from datetime import date
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from catalog.models import Country, Ethnicity, Institution, Sex
from clinical.models import Patient, SecureShare, Visit
from security.access import ACTION_PERMISSIONS, clinical_capabilities, has_clinical_access
from security.models import Role, User, UserRole


class ClinicalAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.home = Institution.objects.create(acronym='AUTH1', name='Synthetic institution one')
        cls.other = Institution.objects.create(acronym='AUTH2', name='Synthetic institution two')
        cls.user = User.objects.create_user(
            username='clinical_actor', email='actor@example.invalid',
            password='SyntheticPassword2026!', institution=cls.home,
        )
        cls.role = Role.objects.create(name='Clinical reviewer')
        cls.assignment = UserRole.objects.create(user=cls.user, role=cls.role)
        country = Country.objects.create(iso_alpha3='AUT', name='Synthetic country')
        sex = Sex.objects.create(sex_id=1, name='Synthetic sex')
        ethnicity = Ethnicity.objects.create(name='Synthetic ethnicity')
        cls.patients = [Patient.objects.create(
            institution=institution, id_card=f'AUTH-{i}', first_names=f'Synthetic {i}',
            last_name1='Authorization', birth_date=date(1990, 1, 1),
            birth_country=country, sex=sex, ethnicity=ethnicity, created_by=cls.user,
        ) for i, institution in enumerate((cls.home, cls.other))]

    def setUp(self):
        cache.clear()

    def grant(self, action, *, target=None):
        required = ACTION_PERMISSIONS[action]
        permissions = Permission.objects.filter(
            content_type__app_label='clinical',
            codename__in=[name.split('.', 1)[1] for name in required],
        )
        self.assertEqual(permissions.count(), len(required))
        (target or self.role.permissions).set(permissions)

    def login(self):
        self.client.force_login(self.user)

    def test_empty_role_and_staff_flag_do_not_authorize(self):
        self.assertFalse(any(clinical_capabilities(self.user).values()))
        self.user.is_staff = True
        self.user.save()
        self.assertFalse(any(clinical_capabilities(self.user).values()))

    def test_all_actions_require_their_complete_grants(self):
        for action in ACTION_PERMISSIONS:
            with self.subTest(action=action):
                self.grant(action)
                self.assertTrue(has_clinical_access(self.user, action))
                permission = self.role.permissions.get(codename='view_visit')
                self.role.permissions.remove(permission)
                self.assertFalse(has_clinical_access(self.user, action))

    def test_read_grants_do_not_allow_writes_or_exports(self):
        self.grant('read')
        self.assertEqual(clinical_capabilities(self.user), {
            action: action == 'read' for action in ACTION_PERMISSIONS
        })

    def test_inactive_role_and_assignment_revoke_access(self):
        self.grant('read')
        self.assertTrue(has_clinical_access(self.user))
        self.role.status = Role.Status.INACTIVE
        self.role.save()
        self.assertFalse(has_clinical_access(self.user))
        self.role.status = Role.Status.ACTIVE
        self.role.save()
        self.assignment.status = UserRole.Status.INACTIVE
        self.assignment.save()
        self.assertFalse(has_clinical_access(self.user))

    def test_inactive_assignment_cannot_borrow_another_users_active_assignment(self):
        self.grant('read')
        self.assignment.status = UserRole.Status.INACTIVE
        self.assignment.save()
        another = User.objects.create_user(username='another', email='another@example.invalid')
        UserRole.objects.create(user=another, role=self.role)
        self.assertFalse(has_clinical_access(self.user))

    def test_native_user_and_group_permissions_are_explicit_grants(self):
        self.grant('read', target=self.user.user_permissions)
        self.assertTrue(has_clinical_access(self.user))
        # Even if Django has cached a positive native has_perm, revocation is effective.
        self.assertTrue(self.user.has_perm('clinical.view_patient'))
        self.user.user_permissions.clear()
        self.assertFalse(has_clinical_access(self.user))
        group = Group.objects.create(name='Clinical readers')
        self.grant('read', target=group.permissions)
        self.user.groups.add(group)
        self.assertTrue(has_clinical_access(self.user))
        group.permissions.clear()
        self.assertFalse(has_clinical_access(self.user))

    def test_role_permission_revocation_is_immediate(self):
        self.grant('read')
        self.assertTrue(has_clinical_access(self.user))
        self.role.permissions.clear()
        self.assertFalse(has_clinical_access(self.user))

    def test_only_active_administrators_get_all_actions(self):
        self.role = Role.objects.get(name='Administrador')
        self.assignment.role = self.role
        self.assignment.save()
        self.assertTrue(all(clinical_capabilities(self.user).values()))
        self.assignment.status = UserRole.Status.INACTIVE
        self.assignment.save()
        self.assertFalse(any(clinical_capabilities(self.user).values()))
        self.user.is_superuser = True
        self.user.save()
        self.assertTrue(all(clinical_capabilities(self.user).values()))
        self.user.status = User.Status.SUSPENDED
        self.user.save()
        self.assertFalse(any(clinical_capabilities(self.user).values()))

    def test_anonymous_or_inconsistent_inactive_users_have_no_access(self):
        self.assertFalse(has_clinical_access(AnonymousUser()))
        self.assertFalse(has_clinical_access(None))
        self.grant('read')
        self.user.status = User.Status.INACTIVE
        self.assertFalse(has_clinical_access(self.user))
        self.user.status = User.Status.ACTIVE
        self.user.is_active = False
        self.assertFalse(has_clinical_access(self.user))

    def test_unauthorized_endpoints_deny_before_clinical_reads_or_effects(self):
        self.login()
        routes = [
            ('get', '/clinical/api/pacientes/'),
            ('get', f'/clinical/api/pacientes/{self.patients[1].pk}/'),
            ('get', f'/clinical/api/ficha/{self.patients[1].pk}/'),
            ('post', '/clinical/api/pacientes/crear/'),
            ('post', '/clinical/api/ficha/guardar/'),
            ('post', '/clinical/api/ficha/eliminar/'),
            ('post', '/clinical/api/ficha/enviar-correo/'),
            ('get', '/clinical/api/ficha/descargar-seleccionados/'),
            ('post', '/clinical/api/import-sav/analyze/'),
            ('post', '/clinical/api/import-sav/execute/'),
            ('get', '/clinical/api/export-dataset/'),
            ('post', '/clinical/api/export-dataset/'),
            ('get', '/dashboard/api/data/'),
            ('get', '/api/data/'),
            ('post', '/chatbot/query/'),
        ]
        with (
            patch('clinical.views.generate_clinical_sheet_pdf') as pdf,
            patch('clinical.views.generate_export_dataset') as export,
            patch('clinical.views.analyze_sav_file') as analyze,
            patch('clinical.views.execute_sav_import') as execute,
            patch('dashboard.services.get_dashboard_evaluation_data') as dashboard,
            patch('chatbot.views.query_gemini_assistant') as assistant,
        ):
            for method, url in routes:
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(response.json()['status'], 'forbidden')
                    self.assertNotIn('Synthetic', response.content.decode())
            for mocked in (pdf, export, analyze, execute, dashboard, assistant):
                mocked.assert_not_called()
        self.assertEqual(Patient.objects.count(), 2)
        self.assertEqual(Visit.objects.count(), 0)
        self.assertEqual(SecureShare.objects.count(), 0)

    def test_html_and_pdf_routes_deny_without_permission(self):
        self.login()
        for url in ('/', '/clinical/listado/', '/clinical/formulario/',
                    '/dashboard/', '/chatbot/', '/clinical/ficha/pdf/',
                    '/clinical/ficha/123/pdf/', '/clinical/ficha/pdf/?blank=1'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_active_read_role_can_read_every_institution(self):
        self.grant('read')
        self.login()
        response = self.client.get('/clinical/api/pacientes/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 2)
        for patient in self.patients:
            with self.subTest(institution=patient.institution_id):
                response = self.client.get(f'/clinical/api/pacientes/{patient.pk}/')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['paciente']['cedula'], patient.id_card)
                self.assertEqual(self.client.get(f'/clinical/api/ficha/{patient.pk}/').status_code, 200)

    def test_read_role_has_html_dashboard_and_assistant_access(self):
        self.grant('read')
        self.login()
        for url in ('/', '/clinical/formulario/', '/dashboard/', '/dashboard/api/data/',
                    '/api/data/', '/chatbot/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        with patch('chatbot.views.query_gemini_assistant', return_value={'status': 'success'}) as query:
            response = self.client.post('/chatbot/query/', {'question': 'Cohort size'})
            self.assertEqual(response.status_code, 200)
            query.assert_called_once()

    def test_read_only_user_cannot_write_import_export_or_share(self):
        self.grant('read')
        self.login()
        for method, url in (
            ('post', '/clinical/api/pacientes/crear/'),
            ('post', '/clinical/api/ficha/guardar/'),
            ('post', '/clinical/api/ficha/eliminar/'),
            ('post', '/clinical/api/ficha/enviar-correo/'),
            ('get', '/clinical/api/ficha/descargar-seleccionados/'),
            ('post', '/clinical/api/import-sav/analyze/'),
            ('post', '/clinical/api/import-sav/execute/'),
            ('get', '/clinical/api/export-dataset/'),
            ('get', '/clinical/ficha/pdf/'),
        ):
            with self.subTest(url=url):
                self.assertEqual(getattr(self.client, method)(url).status_code, 403)

    def test_read_user_can_download_blank_template_only(self):
        self.grant('read')
        self.login()
        with patch('clinical.views.generate_clinical_sheet_pdf', return_value=b'%PDF-synthetic') as pdf:
            response = self.client.get('/clinical/ficha/pdf/?blank=1')
            self.assertEqual(response.status_code, 200)
            pdf.assert_called_once_with(None, is_blank=True)
            pdf.reset_mock()
            self.assertEqual(self.client.get('/clinical/ficha/pdf/').status_code, 403)
            pdf.assert_not_called()

    def test_export_permission_does_not_grant_edit_import_delete_or_share(self):
        self.grant('export')
        self.login()
        with patch('clinical.views.generate_export_dataset', return_value=(b'test', 'test.csv', 'text/csv')) as export:
            self.assertEqual(self.client.get('/clinical/api/export-dataset/?format=csv&scope=all').status_code, 200)
            export.assert_called_once()
        for action in ('create', 'change', 'delete', 'import', 'share'):
            self.assertFalse(has_clinical_access(self.user, action))

    def test_import_permission_reaches_importer_without_granting_delete_or_share(self):
        self.grant('import')
        self.login()
        with patch('clinical.views.execute_sav_import', return_value={'success': True}) as execute:
            response = self.client.post('/clinical/api/import-sav/execute/',
                                        data='{"temp_token":"synthetic"}', content_type='application/json')
            self.assertEqual(response.status_code, 200)
            execute.assert_called_once()
        self.assertFalse(has_clinical_access(self.user, 'delete'))
        self.assertFalse(has_clinical_access(self.user, 'share'))

    def test_expired_role_no_longer_has_http_access(self):
        self.grant('read')
        self.login()
        self.assertEqual(self.client.get('/clinical/api/pacientes/').status_code, 200)
        self.role.status = Role.Status.INACTIVE
        self.role.save()
        for url in ('/clinical/api/pacientes/', '/dashboard/api/data/'):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post('/chatbot/query/').status_code, 403)

    def test_direct_assistant_service_requires_authorization(self):
        from chatbot.services import query_gemini_assistant

        with patch('chatbot.services.get_dashboard_evaluation_data') as data:
            with self.assertRaises(PermissionDenied):
                query_gemini_assistant('Cohort size', user=self.user)
            with self.assertRaises(PermissionDenied):
                query_gemini_assistant('Cohort size')
            data.assert_not_called()

    def test_staff_cannot_enter_backoffice_even_with_native_model_permissions(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.set(Permission.objects.all())
        request = RequestFactory().get('/admin/')
        request.user = self.user
        self.assertFalse(admin.site.has_permission(request))
        self.login()
        self.assertEqual(self.client.get('/admin/').status_code, 302)
        self.assertEqual(self.client.get('/admin/security/user/').status_code, 302)

    def test_backoffice_requires_active_admin_and_staff(self):
        request = RequestFactory().get('/admin/')
        request.user = self.user
        self.role = Role.objects.get(name='Administrador')
        self.assignment.role = self.role
        self.assignment.save()
        self.assertFalse(admin.site.has_permission(request))
        self.user.is_staff = True
        self.user.save()
        self.assertTrue(admin.site.has_permission(request))
        self.role.status = Role.Status.INACTIVE
        self.role.save()
        self.assertFalse(admin.site.has_permission(request))
        self.user.is_superuser = True
        self.user.save()
        self.assertTrue(admin.site.has_permission(request))
        self.user.is_active = False
        self.assertFalse(admin.site.has_permission(request))

    def test_anonymous_api_requests_remain_json_401(self):
        for url in ('/clinical/api/pacientes/', '/dashboard/api/data/', '/api/data/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()['status'], 'unauthorized')

    def test_ui_capabilities_follow_backend_grants(self):
        self.grant('read')
        self.login()
        response = self.client.get('/clinical/formulario/')
        self.assertTrue(response.context['clinical_access']['read'])
        self.assertFalse(response.context['clinical_access']['change'])
        self.assertContains(response, 'change: false')
        self.assertContains(response, '[data-clinical-action="change"] { display: none !important; }')
        self.grant('change')
        response = self.client.get('/clinical/formulario/')
        self.assertTrue(response.context['clinical_access']['change'])
        self.assertContains(response, 'change: true')

    def test_cardiologo_role_capabilities_and_restrictions_when_role_mode_active(self):
        from security.models import SystemSetting

        roles_map = SystemSetting.ensure_institutional_roles()
        SystemSetting.set_settings(role_mode_enabled=True)
        cardio_user = User.objects.create_user(
            username='cardiologo_role_user',
            email='cardio_role@example.invalid',
            password='SyntheticPassword2026!',
            institution=self.home,
        )
        UserRole.objects.create(user=cardio_user, role=roles_map['Cardiólogo'], status=UserRole.Status.ACTIVE)

        caps = clinical_capabilities(cardio_user)
        self.assertEqual(caps, {
            'read': True,
            'create': True,
            'change': True,
            'delete': True,
            'share': True,
            'import': False,
            'export': False,
        })
        self.assertFalse(has_clinical_access(cardio_user, 'dashboard'))

        self.client.force_login(cardio_user)
        list_res = self.client.get('/')
        self.assertEqual(list_res.status_code, 200)
        self.assertContains(list_res, '[data-clinical-action="dashboard"] { display: none !important; }')
        self.assertContains(list_res, '[data-clinical-action="import"] { display: none !important; }')
        self.assertContains(list_res, '[data-clinical-action="export"] { display: none !important; }')
        self.assertNotIn('id="cardModoRolAdmin"', list_res.content.decode())

        # Dashboard, import and export endpoints are blocked for Cardiólogo
        self.assertEqual(self.client.get('/dashboard/').status_code, 403)
        self.assertEqual(self.client.get('/dashboard/api/data/').status_code, 403)
        self.assertEqual(self.client.get('/clinical/api/export-dataset/').status_code, 403)
        self.assertEqual(self.client.post('/clinical/api/import-sav/analyze/').status_code, 403)

    def test_estadistica_role_capabilities_and_restrictions_when_role_mode_active(self):
        from security.models import SystemSetting

        roles_map = SystemSetting.ensure_institutional_roles()
        SystemSetting.set_settings(role_mode_enabled=True)
        stats_user = User.objects.create_user(
            username='estadistica_role_user',
            email='stats_role@example.invalid',
            password='SyntheticPassword2026!',
            institution=self.home,
        )
        UserRole.objects.create(
            user=stats_user,
            role=roles_map['Departamento de Estadística'],
            status=UserRole.Status.ACTIVE,
        )

        caps = clinical_capabilities(stats_user)
        self.assertEqual(caps, {
            'read': True,
            'create': False,
            'change': False,
            'delete': False,
            'share': True,
            'import': True,
            'export': True,
        })
        self.assertTrue(has_clinical_access(stats_user, 'dashboard'))

        self.client.force_login(stats_user)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/dashboard/').status_code, 200)
        self.assertEqual(self.client.get('/dashboard/api/data/').status_code, 200)

        # Create, edit and delete are strictly denied for Estadística
        self.assertEqual(self.client.post('/clinical/api/pacientes/crear/').status_code, 403)
        self.assertEqual(self.client.post('/clinical/api/ficha/guardar/').status_code, 403)
        self.assertEqual(self.client.post('/clinical/api/ficha/eliminar/').status_code, 403)

    def test_disabling_role_mode_unlocks_clinical_and_dashboard_but_keeps_admin_settings_exclusive(self):
        import json
        from security.models import SystemSetting

        roles_map = SystemSetting.ensure_institutional_roles()
        cardio_user = User.objects.create_user(
            username='cardio_freemode',
            email='cardio_free@example.invalid',
            password='SyntheticPassword2026!',
            institution=self.home,
        )
        UserRole.objects.create(user=cardio_user, role=roles_map['Cardiólogo'], status=UserRole.Status.ACTIVE)

        admin_user = User.objects.create_user(
            username='admin_rolemode',
            email='admin_rolemode@example.invalid',
            password='SyntheticPassword2026!',
            institution=self.home,
        )
        UserRole.objects.create(user=admin_user, role=roles_map['Administrador'], status=UserRole.Status.ACTIVE)

        # Admin disables Modo Rol via /security/api/settings/
        self.client.force_login(admin_user)
        res = self.client.post(
            '/security/api/settings/',
            data=json.dumps({'chatbot_enabled': True, 'role_mode_enabled': False}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(SystemSetting.is_role_mode_enabled())

        # Now Cardiólogo has free access to Dashboard, Export, Import, etc.
        self.assertTrue(all(clinical_capabilities(cardio_user).values()))
        self.assertTrue(has_clinical_access(cardio_user, 'dashboard'))

        self.client.force_login(cardio_user)
        self.assertEqual(self.client.get('/dashboard/').status_code, 200)
        home_html = self.client.get('/').content.decode()
        # Admin settings in Ajustes MUST remain hidden and forbidden to non-admins
        self.assertNotIn('id="cardModoRolAdmin"', home_html)
        self.assertNotIn('id="tabBtnAjustesApis"', home_html)

        forbidden_res = self.client.post(
            '/security/api/settings/',
            data=json.dumps({'role_mode_enabled': True}),
            content_type='application/json',
        )
        self.assertEqual(forbidden_res.status_code, 403)
        self.assertFalse(SystemSetting.is_role_mode_enabled())

