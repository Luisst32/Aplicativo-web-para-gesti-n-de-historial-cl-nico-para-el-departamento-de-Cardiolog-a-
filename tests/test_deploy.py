import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.deploy import deploy, check_health, NoRedirects

SHA = 'a' * 40
URL = 'https://clinic.example/security/login/'


class DeploymentGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cardio-deploy-mock-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        python = self.root / 'venv/bin/python'
        python.parent.mkdir(parents=True)
        python.touch()

    def successful_commands(self):
        commands = []
        with contextlib.redirect_stdout(io.StringIO()):
            deploy(self.root, SHA, URL, run=commands.append, healthcheck=Mock())
        return commands

    def test_success_checks_exact_commit_dependencies_and_service_before_health(self):
        commands, events = [], []
        def run(command):
            commands.append(command)
            events.append(command)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            deploy(self.root, SHA, URL, run=run, healthcheck=lambda url: events.append(url))
        self.assertIn(['git', 'checkout', '--detach', SHA], commands)
        self.assertEqual(sum('install' in c and '-r' in c for c in commands), 2)
        self.assertIn(['systemctl', 'is-active', '--quiet', 'django_app'], commands)
        self.assertEqual(events[-1], URL)
        self.assertIn(f'Deployment verified: {SHA}', output.getvalue())

    def test_each_command_failure_blocks_later_steps_and_success_message(self):
        expected = self.successful_commands()
        for index in range(len(expected)):
            with self.subTest(failure=expected[index]):
                seen, output, health = [], io.StringIO(), Mock()
                def fail(command):
                    seen.append(command)
                    if len(seen) - 1 == index:
                        raise subprocess.CalledProcessError(1, command)
                with contextlib.redirect_stdout(output), self.assertRaises(subprocess.CalledProcessError):
                    deploy(self.root, SHA, URL, run=fail, healthcheck=health)
                self.assertEqual(seen, expected[:index + 1])
                health.assert_not_called()
                self.assertNotIn('Deployment verified', output.getvalue())

    def test_missing_venv_refuses_system_python_before_checkout(self):
        run = Mock()
        with tempfile.TemporaryDirectory() as missing, self.assertRaises(RuntimeError):
            deploy(missing, SHA, URL, run=run)
        run.assert_not_called()

    def test_invalid_commit_or_healthcheck_never_changes_repository(self):
        for sha, url in (('develop', URL), (SHA, ''), (SHA, 'http://clinic.example/'),
                         (SHA, 'https://user:password@clinic.example/'), (SHA, URL + '?token=x')):
            with self.subTest(sha=sha, url=url), self.assertRaises(ValueError):
                deploy(self.root, sha, url, run=Mock())

    def test_failed_healthcheck_does_not_report_success(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(RuntimeError):
            deploy(self.root, SHA, URL, run=Mock(), healthcheck=Mock(side_effect=RuntimeError('Synthetic failure')))
        self.assertNotIn('Deployment verified', output.getvalue())

    def test_default_runner_requires_every_subprocess_to_succeed(self):
        with patch('scripts.deploy.subprocess.run') as run, contextlib.redirect_stdout(io.StringIO()):
            deploy(self.root, SHA, URL, healthcheck=Mock())
        self.assertTrue(run.call_args_list)
        for call in run.call_args_list:
            self.assertIs(call.kwargs['check'], True)
            self.assertEqual(call.kwargs['cwd'], self.root)

    def test_healthcheck_requires_http_200_and_does_not_follow_redirects(self):
        with patch('scripts.deploy.build_opener') as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status = 200
            check_health(URL)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, URL)
            self.assertEqual(request.get_header('User-agent'), 'CardioUNEMI-DeploymentHealthcheck/1.0')
            self.assertEqual(request.get_header('Cache-control'), 'no-cache')
            self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'], 15)
            response.status = 301
            with self.assertRaises(RuntimeError):
                check_health(URL)
        self.assertIsNone(NoRedirects().redirect_request(None, None, None, None, None, None))

    def test_healthcheck_retries_transient_gateway_errors(self):
        from urllib.error import HTTPError
        with patch('scripts.deploy.build_opener') as opener, patch('scripts.deploy.time.sleep') as mock_sleep:
            good_response = Mock()
            good_response.status = 200
            context_manager = Mock()
            context_manager.__enter__ = Mock(return_value=good_response)
            context_manager.__exit__ = Mock(return_value=None)
            err = HTTPError(URL, 502, 'Bad Gateway', {}, None)
            opener.return_value.open.side_effect = [err, context_manager]
            check_health(URL, attempts=3, delay=0.01)
            self.assertEqual(opener.return_value.open.call_count, 2)
            mock_sleep.assert_called_once_with(0.01)


class MigrationCredentialTests(unittest.TestCase):
    def test_refuses_non_migration_commands(self):
        from scripts.migration_manage import main
        with patch('sys.argv', ['migration_manage.py','shell']), self.assertRaises(RuntimeError):
            main()

    def test_refuses_credentials_inside_application(self):
        from scripts.migration_manage import main
        import os
        root=Path(__file__).resolve().parent.parent
        with patch('sys.argv',['migration_manage.py','migrate']), patch.dict(os.environ,{'MIGRATION_ENV_FILE':str(root/'README.md')}), self.assertRaises(RuntimeError):
            main()

    def test_separate_credentials_are_used_only_in_migration_process(self):
        from scripts.migration_manage import main
        import os
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'migration.env'
            path.write_text('DB_USER=synthetic_migrator\nDB_PASSWORD=synthetic_password\n',encoding='utf-8')
            path.chmod(0o600)
            def execute(argv):
                self.assertEqual(os.environ['DB_USER'],'synthetic_migrator')
                self.assertEqual(argv,['manage.py','migrate','--noinput'])
            with patch.dict(os.environ,{'MIGRATION_ENV_FILE':str(path)}), patch('sys.argv',['migration_manage.py','migrate','--noinput']), patch('django.core.management.execute_from_command_line',side_effect=execute) as command:
                main()
                command.assert_called_once()


if __name__ == '__main__':
    unittest.main()
