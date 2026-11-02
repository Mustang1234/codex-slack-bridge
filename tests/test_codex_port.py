import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_slack_bridge import config, server, threads


class CodexPortTests(unittest.TestCase):
    def test_session_pid_skips_bridge_and_wrappers(self):
        output = ('90 80 python -m codex_slack_bridge\n'
                  '80 70 uvx codex-slack-bridge\n'
                  '70 60 /opt/bin/codex\n'
                  '60 1 zsh\n')
        with patch.object(server.os, 'getpid', return_value=90), patch.object(
            server.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output)
        ):
            self.assertEqual(server._session_pid(), 70)

    def test_unrecognized_parent_and_ps_failure_use_server_pid(self):
        for result in (subprocess.CompletedProcess([], 0, '90 80 python\n80 1 unrelated\n'),
                       subprocess.CompletedProcess([], 1, '')):
            with self.subTest(result=result), patch.object(server.os, 'getpid', return_value=90), patch.object(
                server.subprocess, 'run', return_value=result
            ):
                self.assertEqual(server._session_pid(), 90)

    def test_legacy_environment_is_not_loaded(self):
        with patch.dict(config.os.environ, {'SLACK_BOT_TOKEN': 'fake', 'SLACK_CHANNEL': 'fake'}, clear=True), patch.object(
            type(config.CONFIG_PATH), 'exists', return_value=False
        ):
            self.assertIsNone(config.load())

    def test_namespaced_environment_loads(self):
        with patch.dict(config.os.environ, {'CODEX_SLACK_BRIDGE_BOT_TOKEN': 'fake',
                                           'CODEX_SLACK_BRIDGE_CHANNEL': 'fake'}, clear=True), patch.object(
            type(config.CONFIG_PATH), 'exists', return_value=False
        ):
            self.assertEqual(config.load().bot_token, 'fake')

    def test_state_and_command_namespace(self):
        self.assertEqual(config.CONFIG_DIR.name, '.codex-slack-bridge')
        self.assertEqual(threads.THREADS_DIR.parent.name, '.codex-slack-bridge')
        for has_console_script in (True, False):
            with self.subTest(has_console_script=has_console_script), patch.object(
                Path, 'is_file', return_value=has_console_script
            ):
                command = threads.keeper_command('123.4')
                if has_console_script:
                    self.assertEqual(Path(command[0]).name, 'codex-slack-bridge')
                    self.assertEqual(command[1:], ['keeper', '--thread', '123.4'])
                else:
                    self.assertEqual(command[1:], [
                        '-m', 'codex_slack_bridge', 'keeper', '--thread', '123.4'
                    ])
                for token in command:
                    self.assertNotIn(Path(token).name, {
                        'claude-slack-bridge', 'claude_slack_bridge'
                    })
