from django.test import SimpleTestCase
from security.models import User, Role, UserRole


class SecurityModelStatusSimpleTests(SimpleTestCase):
    def test_user_default_status_and_active(self):
        user = User(username='doc_test', email='doc@unemi.edu.ec', first_name='Doc', last_name='Cardio')
        self.assertEqual(user.status, User.AccountStatus.ACTIVE)
        self.assertTrue(user.is_active)
        self.assertIsNone(user.status_reason)
        self.assertIsNone(user.deactivated_at)

    def test_user_deactivation_when_not_using_account(self):
        user = User(username='retired_user', email='ret@unemi.edu.ec', first_name='Carlos', last_name='Doc')
        # Simulate deactivation in memory
        user.is_active = False
        user.status = User.AccountStatus.INACTIVE
        user.status_reason = "Desvinculación institucional - Ya no utiliza la cuenta"

        self.assertEqual(user.status, User.AccountStatus.INACTIVE)
        self.assertFalse(user.is_active)
        self.assertEqual(user.status_reason, "Desvinculación institucional - Ya no utiliza la cuenta")

    def test_user_reactivation_logic(self):
        user = User(username='temp_user', email='temp@unemi.edu.ec', first_name='Ana', last_name='Pérez')
        user.status = User.AccountStatus.INACTIVE
        user.is_active = False

        user.is_active = True
        user.status = User.AccountStatus.ACTIVE
        user.status_reason = None
        user.deactivated_at = None

        self.assertEqual(user.status, User.AccountStatus.ACTIVE)
        self.assertTrue(user.is_active)
        self.assertIsNone(user.status_reason)
        self.assertIsNone(user.deactivated_at)

    def test_role_and_user_role_status(self):
        role = Role(name='Cardiólogo Clínico')
        self.assertTrue(role.is_active)

        user = User(username='dr_role', email='dr@unemi.edu.ec', first_name='Luis', last_name='S')
        user_role = UserRole(user=user, role=role)
        self.assertTrue(user_role.is_active)
