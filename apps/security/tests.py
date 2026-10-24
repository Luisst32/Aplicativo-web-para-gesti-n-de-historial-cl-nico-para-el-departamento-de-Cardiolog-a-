from django.test import SimpleTestCase
from security.models import User, Role, UserRole


class SecurityModelStatusTests(SimpleTestCase):
    def test_user_default_status(self):
        user = User(username='doc_test', email='doc@unemi.edu.ec', first_name='Doc', last_name='Cardio')
        self.assertEqual(user.status, User.Status.ACTIVE)

    def test_user_inactive_status_when_account_not_in_use(self):
        user = User(username='retired_user', email='ret@unemi.edu.ec', first_name='Carlos', last_name='Doc')
        user.status = User.Status.INACTIVE
        self.assertEqual(user.status, User.Status.INACTIVE)

    def test_role_and_user_role_status(self):
        role = Role(name='Clinical Cardiologist')
        self.assertEqual(role.status, Role.Status.ACTIVE)

        user = User(username='dr_role', email='dr@unemi.edu.ec', first_name='Luis', last_name='S')
        user_role = UserRole(user=user, role=role)
        self.assertEqual(user_role.status, UserRole.Status.ACTIVE)
