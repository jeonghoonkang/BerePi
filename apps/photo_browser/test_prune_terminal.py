import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from prune_progress import PruneProgress
from prune_terminal import PruneTerminal, clipped


class TTY(io.StringIO):
    def isatty(self):
        return True


class PruneTerminalTests(unittest.TestCase):
    def setUp(self):
        ansi = patch('prune_terminal.PruneTerminal._enable_ansi', return_value=True)
        ansi.start()
        self.addCleanup(ansi.stop)

    def test_header_is_reserved_above_normal_stdout_and_stderr(self):
        out, err = TTY(), TTY()
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                patch.dict(os.environ, {'TERM': 'xterm'}), \
                patch('prune_terminal.shutil.get_terminal_size', return_value=os.terminal_size((100, 24))):
            db = Path(folder) / 'db'; db.mkdir()
            with PruneTerminal() as terminal:
                self.assertTrue(terminal.enabled)
                with PruneProgress(db, Path(folder) / 'plan.sqlite', 'db-prune-plan', interval=3600, terminal=terminal) as monitor:
                    monitor('plan-total', 1000, 'media')
                    monitor('plan', 100, 'media/current.json')
                    monitor.write()
                    print('NORMAL_STDOUT')
                    print('NORMAL_STDERR', file=sys.stderr)
                print(json.dumps({'result': 'final JSON below the header'}))
            self.assertIs(sys.stdout, out)
            self.assertIs(sys.stderr, err)
            self.assertEqual(json.loads(monitor.path.read_text().splitlines()[-1])['processed'], 100)
        text = out.getvalue()
        self.assertIn('\033[10;24r', text)
        self.assertIn('\033[2;1H\033[2K로그 파일:', text)
        self.assertIn('10.00%', text)
        self.assertIn('NORMAL_STDOUT', text)
        self.assertIn('NORMAL_STDERR', text)
        self.assertIn('final JSON below the header', text)
        self.assertTrue(text.endswith('\0337\033[r\0338'))
        self.assertEqual(err.getvalue(), '')

    def test_ram_header_is_visible_from_start_and_refreshes_during_blocked_io(self):
        out, err = TTY(), TTY()
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                patch.dict(os.environ, {'TERM': 'xterm'}), \
                patch('prune_terminal.shutil.get_terminal_size', return_value=os.terminal_size((80, 24))), \
                patch('prune_progress.system_memory', return_value={'rss_bytes': 64 * 1024 * 1024,
                                                                   'available_bytes': 512 * 1024 * 1024}):
            db = Path(folder) / 'db'; db.mkdir()
            with PruneTerminal() as terminal:
                with PruneProgress(db, Path(folder) / 'plan.sqlite', 'db-prune-plan', interval=.02,
                                   files=1, terminal=terminal) as monitor:
                    self.assertIn('RAM 사용(RSS): 64.0 MiB', out.getvalue())
                    monitor.set_memory_provider(lambda: {'rss_bytes': 128 * 1024 * 1024,
                                                         'available_bytes': 256 * 1024 * 1024,
                                                         'cache_used_bytes': 2 * 1024 * 1024,
                                                         'cache_budget_bytes': 16 * 1024 * 1024})
                    # No operation callbacks while the independent heartbeat refreshes.
                    threading.Event().wait(.07)
                    self.assertIn('RAM 사용(RSS): 128.0 MiB', out.getvalue())
                    self.assertIn('가용: 256.0 MiB', out.getvalue())
                    self.assertIn('캐시: 2.0/16.0 MiB', out.getvalue())
                    self.assertEqual(json.loads(monitor.path.read_text())['memory']['rss_bytes'], 128 * 1024 * 1024)
        self.assertIn('\033[3;1H\033[2KRAM 사용(RSS):', out.getvalue())
        self.assertIn('\033[4;1H\033[2K캐시:', out.getvalue())

    def test_pipes_keep_plain_json_even_if_pretty_requested(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with PruneTerminal('pretty') as terminal:
                self.assertFalse(terminal.enabled)
                print(json.dumps({'status': 'ready'}))
        self.assertEqual(json.loads(out.getvalue()), {'status': 'ready'})
        self.assertNotIn('\033', out.getvalue())

    def test_cli_pretty_option_preserves_piped_result_and_log(self):
        from cli import main
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'db'; db.mkdir()
            plan = Path(folder) / 'plan.sqlite'
            with patch('db_prune.plan_prune', return_value={'status': 'ready'}), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main(['--db', str(db), 'db-prune-plan', '--plan', str(plan),
                             '--server-stopped', '--progress-display', 'pretty'])
            self.assertEqual(code, 0, err.getvalue())
            result = json.loads(out.getvalue())
            self.assertEqual(result['status'], 'ready')
            self.assertTrue(Path(result['progress_log']).is_file())
            self.assertNotIn('\033', out.getvalue())

    def test_plain_mode_and_dumb_terminal_never_add_escape_sequences(self):
        for mode, term in [('plain', 'xterm'), ('auto', 'dumb')]:
            out, err = TTY(), TTY()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch.dict(os.environ, {'TERM': term}):
                with PruneTerminal(mode) as terminal:
                    self.assertFalse(terminal.enabled)
                    print('output')
            self.assertEqual(out.getvalue(), 'output\n')

    def test_exception_restores_terminal_and_streams(self):
        out, err = TTY(), TTY()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch.dict(os.environ, {'TERM': 'xterm'}), \
                patch('prune_terminal.shutil.get_terminal_size', return_value=os.terminal_size((80, 24))):
            with self.assertRaises(KeyboardInterrupt):
                with PruneTerminal():
                    raise KeyboardInterrupt
            self.assertIs(sys.stdout, out)
            self.assertIs(sys.stderr, err)
        self.assertTrue(out.getvalue().endswith('\0337\033[r\0338'))

    def test_header_text_cannot_move_cursor_or_wrap_on_korean_paths(self):
        self.assertEqual(clipped('가나다', 4), '가나')
        self.assertNotIn('\033', clipped('path\033[2J\nnext', 100))
        self.assertNotIn('\n', clipped('path\nnext', 100))


if __name__ == '__main__':
    unittest.main()
