from django.test import SimpleTestCase
from audit.models import ChangeLog


class AuditModelStatusTests(SimpleTestCase):
    def test_changelog_status_default(self):
        log = ChangeLog(
            schema_name='clinical',
            table_name='patient',
            record_key='101',
            action='UPDATE'
        )
        self.assertEqual(log.status, ChangeLog.Status.RECORDED)
