from django.test import SimpleTestCase
from audit.models import ChangeLog


class AuditModelStatusSimpleTests(SimpleTestCase):
    def test_changelog_status_default(self):
        log = ChangeLog(
            schema_name='clinical',
            table_name='patient',
            record_key='101',
            action='UPDATE'
        )
        self.assertEqual(log.status, ChangeLog.AuditStatus.RECORDED)
        self.assertFalse(log.is_flagged)

    def test_changelog_flagged_status(self):
        log = ChangeLog(
            schema_name='security',
            table_name='user',
            record_key='5',
            action='DELETE',
            status=ChangeLog.AuditStatus.FLAGGED,
            is_flagged=True
        )
        self.assertEqual(log.status, ChangeLog.AuditStatus.FLAGGED)
        self.assertTrue(log.is_flagged)
