import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app, main
from startup_sources import print_directory_summary, register_directories


class StartupSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.first, self.second = self.root / '기존 사진', self.root / '새 사진'
        self.first.mkdir()
        self.second.mkdir()
        Image.new('RGB', (8, 8)).save(self.first / 'photo.JPG')
        (self.second / 'nested').mkdir()
        (self.second / 'nested' / 'clip.MP4').write_bytes(b'video')
        (self.second / 'ignored.txt').write_text('ignored')
        (self.first / 'nested').mkdir()
        (self.first / 'nested' / 'not-recursive.jpg').write_bytes(b'excluded')
        self.app = create_app(self.root, self.first, self.root / 'db')
        self.library = self.app.extensions['photo_library']
        config = self.library.config()
        config['sources'] = [{'source_id': 'existing', 'root': str(self.first),
                              'category': 'work', 'owner_id': 'alice', 'recursive': False}]
        self.library.save_config(config)

    def test_reuses_existing_adds_new_and_reports_scan_history_and_counts(self):
        self.library.scan('existing')
        original = self.library.config()['sources'][0]
        reports = register_directories(self.library, [self.first, self.second])
        self.assertEqual([report['added'] for report in reports], [False, True])
        self.assertEqual(self.library.config()['sources'][0], original)
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            print_directory_summary(self.library, reports)
        output = stream.getvalue()
        for text in ('하나의 라이브러리로 통합', '[기존 등록]', '[신규 추가]',
                     '사진 1개, 동영상 0개', '사진 0개, 동영상 1개',
                     '총 용량 5바이트', '이전 스캔: completed', '이전 스캔: 기록 없음',
                     '2개 소스 · 지원 미디어 2개', '중복 제거 전'):
            self.assertIn(text, output)
        # Registration/inventory must not scan or copy the new source's files.
        self.assertEqual(len(self.library.items()), 1)
        self.assertFalse(any(Path(self.library.config()['managed_root']).rglob('*.MP4')))
        repeated = register_directories(self.library, [self.first, self.second / '.', self.second])
        self.assertEqual([report['added'] for report in repeated], [False, False])
        self.assertEqual(len(self.library.config()['sources']), 2)

    def test_invalid_directory_does_not_partially_register_sources(self):
        original = self.library.config()
        for invalid in (self.root / 'missing', self.root.parent, self.first / 'photo.JPG',
                        self.library.db, original['managed_root']):
            with self.subTest(path=invalid), self.assertRaises(ValueError):
                register_directories(self.library, [self.second, invalid])
            self.assertEqual(self.library.config(), original)

    def test_inventory_excludes_db_managed_and_symlinks(self):
        reports = register_directories(self.library, [self.root])
        (self.library.db / 'not-source.jpg').write_bytes(b'db')
        (Path(self.library.config()['managed_root']) / 'not-source.jpg').write_bytes(b'managed')
        (self.root / 'linked.jpg').symlink_to(self.first / 'photo.JPG')
        (self.root / 'linked-directory').symlink_to(self.first, target_is_directory=True)
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            print_directory_summary(self.library, reports)
        # Two images and one video in the actual source tree; links and internals excluded.
        self.assertIn('사진 2개, 동영상 1개', stream.getvalue())

    def test_count_errors_are_visible_as_partial_results(self):
        reports = register_directories(self.library, [self.first, self.second])
        with patch('startup_sources.local_media_files', side_effect=PermissionError('unreadable')):
            with contextlib.redirect_stdout(io.StringIO()) as stream:
                print_directory_summary(self.library, reports)
        self.assertIn('불완전한 집계', stream.getvalue())
        self.assertIn('집계 오류 2건', stream.getvalue())

    def test_cli_multiple_directories_persist_and_second_run_reports_existing(self):
        args = ['--root', str(self.root), '--db', str(self.library.db),
                '--directory', str(self.first), '--directory', str(self.second)]
        for expected in ('[신규 추가]', '[기존 등록]'):
            with patch('app.Flask.run') as run, contextlib.redirect_stdout(io.StringIO()) as stream:
                main(args)
            run.assert_called_once()
            self.assertIn(expected, stream.getvalue())
            if expected == '[기존 등록]':
                self.assertNotIn('[신규 추가]', stream.getvalue())
            self.assertIn(f'시작 디렉토리: {self.first}', stream.getvalue())
        self.assertEqual(len(self.library.config()['sources']), 2)

    def test_cli_single_directory_keeps_browse_only_behavior(self):
        with patch('app.Flask.run'), contextlib.redirect_stdout(io.StringIO()) as stream:
            main(['--root', str(self.root), '--db', str(self.library.db), '--directory', str(self.second)])
        self.assertNotIn('하나의 라이브러리로 통합', stream.getvalue())
        self.assertIn(f'시작 디렉토리: {self.second}', stream.getvalue())
        self.assertEqual(len(self.library.config()['sources']), 1)


if __name__ == '__main__':
    unittest.main()
