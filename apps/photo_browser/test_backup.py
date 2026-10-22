import contextlib
import io
import json
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image

from backup import create_backup, restore_backup, verify_backup
from cli import main
from library import Library, atomic_json, digest, read_json


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        source = self.root / 'incoming'
        source.mkdir()
        Image.new('RGB', (8, 8)).save(source / 'photo.jpg')
        self.library = Library(self.root / 'db', self.root)
        self.library.save_config({'managed_root': str(self.root / 'managed'), 'scan_min_free_mb': 32,
                                  'sources': [{'source_id': 'photos', 'root': str(source), 'protocol': 'file'}]})
        self.library.scan('photos')
        self.library.edit([self.library.items()[0]['media_id']], {'events': ['가족여행'], 'tags': ['바다']})
        self.library.merge()
        self.bundle = self.root / 'backup'
        self.target = self.root / 'restored'

    def test_roundtrip_relocates_photos_and_preserves_tags_and_time(self):
        original = self.library.items()[0]
        location = original['locations'][-1]
        stat = Path(location['path']).stat()
        result = create_backup(self.library, self.bundle)
        self.assertEqual(result['status'], 'completed')
        self.assertFalse((self.bundle / 'db' / '.write.lock').exists())
        report = restore_backup(self.bundle, self.target)
        restored = Library(report['db'], report['root'])
        item = restored.items()[0]
        self.assertEqual(item['classification'], original['classification'])
        self.assertEqual(item['capture'], original['capture'])
        copy = item['locations'][-1]
        path = Path(copy['path'])
        self.assertTrue(path.is_relative_to(self.target / 'managed'))
        self.assertEqual(copy['uri'], path.as_uri())
        self.assertEqual(digest(path), original['sha256'])
        self.assertEqual(path.stat().st_mtime_ns, stat.st_mtime_ns)
        self.assertEqual(restored.config()['sources'], self.library.config()['sources'])
        self.assertEqual(restored.config()['managed_root'], str(self.target / 'managed'))
        self.assertTrue((self.bundle / 'manifest.json').is_file())

    def test_trash_can_be_restored_after_relocation(self):
        item = self.library.items()[0]
        trashed = self.library.trash([item['media_id']])
        create_backup(self.library, self.bundle)
        report = restore_backup(self.bundle, self.target)
        restored = Library(report['db'], report['root'])
        restored.restore(trashed['trash_id'])
        location = restored.items()[0]['locations'][-1]
        self.assertTrue(Path(location['path']).is_file())
        self.assertTrue(Path(location['path']).is_relative_to(self.target))

    def test_corrupt_file_is_rejected_without_partial_restore(self):
        create_backup(self.library, self.bundle)
        self.assertEqual(verify_backup(self.bundle)['status'], 'verified')
        path = next((self.bundle / 'managed').rglob('*.jpg'))
        path.write_bytes(b'x' * path.stat().st_size)
        with self.assertRaisesRegex(ValueError, '무결성'):
            verify_backup(self.bundle)
        with self.assertRaisesRegex(ValueError, '무결성'):
            restore_backup(self.bundle, self.target)
        self.assertFalse(self.target.exists())

    def test_no_overwrite_overlap_or_concurrent_backup(self):
        with self.library.writing(), self.assertRaisesRegex(ValueError, '다른 작업'):
            create_backup(self.library, self.bundle)
        with self.assertRaises(ValueError):
            create_backup(self.library, self.library.db / 'backup')
        create_backup(self.library, self.bundle)
        with self.assertRaises(ValueError):
            create_backup(self.library, self.bundle)
        self.target.mkdir()
        with self.assertRaises(ValueError):
            restore_backup(self.bundle, self.target)

    def test_manifest_traversal_extra_files_and_symlinks_rejected(self):
        create_backup(self.library, self.bundle)
        path = self.bundle / 'manifest.json'
        manifest = read_json(path)
        changed = json.loads(json.dumps(manifest))
        changed['files'][0]['path'] = 'db/../../escape'
        atomic_json(path, changed)
        with self.assertRaises(ValueError):
            restore_backup(self.bundle, self.target)
        atomic_json(path, manifest)
        extra = self.bundle / 'managed' / 'extra.jpg'
        extra.write_bytes(b'extra')
        with self.assertRaises(ValueError):
            restore_backup(self.bundle, self.target)
        extra.unlink()
        extra.symlink_to(self.root / 'incoming' / 'photo.jpg')
        with self.assertRaises(ValueError):
            restore_backup(self.bundle, self.target)

    def test_copy_failure_removes_only_new_output(self):
        with patch('backup.shutil.copy2', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                create_backup(self.library, self.bundle)
        self.assertFalse(self.bundle.exists())
        self.assertTrue(self.library.items())

    def test_cli_restore_does_not_require_existing_db(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(['--db', str(self.library.db), '--root', str(self.root), 'backup', '--destination', str(self.bundle)])
        self.assertEqual(code, 0)
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(['--db', str(self.root / 'absent'), 'restore', '--backup', str(self.bundle), '--destination', str(self.target)])
        self.assertEqual(code, 0)
        self.assertFalse((self.root / 'absent').exists())

    def test_managed_file_can_be_served_without_original_source(self):
        from app import create_app
        item = self.library.items()[0]
        create_backup(self.library, self.bundle)
        result = restore_backup(self.bundle, self.target)
        (self.root / 'incoming' / 'photo.jpg').unlink()
        client = create_app(self.target, self.target, result['db']).test_client()
        response = client.get('/api/library/' + item['media_id'] + '/file')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, Path(item['locations'][-1]['path']).read_bytes())
        response.close()

    def test_backup_detects_file_added_during_copy(self):
        from backup import copy_verified
        changed = [False]
        def copying(*args, **kwargs):
            value = copy_verified(*args, **kwargs)
            if not changed[0]:
                changed[0] = True
                (self.library.db / 'new.json').write_text('{}')
            return value
        with patch('backup.copy_verified', side_effect=copying):
            with self.assertRaisesRegex(ValueError, '변경'):
                create_backup(self.library, self.bundle)
        self.assertFalse(self.bundle.exists())

    def test_unmerged_item_is_reported_and_damaged_managed_copy_rejected(self):
        item = self.library.items()[0]
        photo = Path(item['locations'][-1]['path'])
        photo.write_bytes(b'damaged')
        with self.assertRaisesRegex(ValueError, '손상'):
            create_backup(self.library, self.bundle)
        self.assertFalse(self.bundle.exists())
        item['locations'] = item['locations'][:1]
        self.library.commit([item])
        result = create_backup(self.library, self.bundle)
        self.assertEqual(result['active_items_without_managed_copy'], 1)

    def test_torn_scan_journal_can_resume_after_restore(self):
        from scan_engine import scan_sessions
        state = scan_sessions(self.library)[0]
        state['status'] = 'stopped'
        directory = self.library.db / 'scans' / 'sessions' / state['scan_id']
        atomic_json(directory / 'state.json', state)
        with (directory / 'results.jsonl').open('ab') as stream:
            stream.write(b'{"ordinal":')
        create_backup(self.library, self.bundle)
        result = restore_backup(self.bundle, self.target)
        restored = Library(result['db'], self.root)
        self.assertEqual(restored.scan('photos', mode='resume')['status'], 'completed')
        self.assertTrue(Path(restored.items()[0]['locations'][-1]['path']).is_relative_to(self.target))

    def test_zip_roundtrip_compresses_and_records_original_paths(self):
        bundle = self.root / '가족사진.zip'
        (self.library.db / 'notes.txt').write_text('event metadata\n' * 10000)
        extra = self.root / 'managed' / '추가 사진.jpg'
        extra.write_bytes(b'original media')
        original = self.library.items()[0]
        photo = Path(original['locations'][-1]['path'])
        mtime = photo.stat().st_mtime_ns
        result = create_backup(self.library, bundle)
        self.assertEqual(result['container'], 'zip')
        self.assertLess(result['archive_bytes'], result['total_bytes'])
        self.assertEqual(verify_backup(bundle)['status'], 'verified')
        with zipfile.ZipFile(bundle) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['original_db'], str(self.library.db))
            self.assertEqual(manifest['original_managed_root'], str(self.root / 'managed'))
            self.assertEqual(manifest['original_allowed_root'], str(self.root))
            self.assertEqual(manifest['source_roots'][0]['root'], str(self.root / 'incoming'))
            self.assertIn('managed/추가 사진.jpg', archive.namelist())
            self.assertTrue(all(info.compress_type == zipfile.ZIP_DEFLATED for info in archive.infolist()))
        result = restore_backup(bundle, self.target)
        restored = Library(result['db'], result['root'])
        item = restored.items()[0]
        self.assertEqual(item['classification'], original['classification'])
        self.assertEqual(item['capture'], original['capture'])
        path = Path(item['locations'][-1]['path'])
        self.assertTrue(path.is_relative_to(self.target / 'managed'))
        self.assertEqual(item['locations'][-1]['uri'], path.as_uri())
        self.assertEqual(digest(path), original['sha256'])
        self.assertEqual(path.stat().st_mtime_ns, mtime)
        self.assertEqual((self.target / 'managed' / extra.name).read_bytes(), extra.read_bytes())
        self.assertEqual(read_json(self.target / 'restore.json')['backup'], str(bundle))

    def test_zip_cli_without_old_database(self):
        bundle = self.root / 'library.archive'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--db', str(self.library.db), '--root', str(self.root), 'backup',
                                   '--format', 'zip', '--destination', str(bundle)]), 0)
            self.assertEqual(main(['backup-check', '--backup', str(bundle)]), 0)
            self.assertEqual(main(['--db', str(self.root / 'absent'), 'restore', '--backup', str(bundle),
                                   '--destination', str(self.target)]), 0)
        self.assertFalse((self.root / 'absent').exists())

    def test_zip_corruption_and_untrusted_entries_rejected(self):
        bundle = self.root / 'valid.zip'
        create_backup(self.library, bundle)
        with zipfile.ZipFile(bundle) as archive:
            data = [(info, archive.read(info)) for info in archive.infolist()]
        for attack in ('content', 'traversal', 'extra', 'duplicate', 'symlink', 'invalid-size'):
            with self.subTest(attack=attack):
                damaged = self.root / (attack + '.zip')
                with warnings.catch_warnings(), zipfile.ZipFile(damaged, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                    warnings.simplefilter('ignore', UserWarning)
                    for info, value in data:
                        if info.filename == 'manifest.json' and attack in {'traversal', 'invalid-size'}:
                            manifest = json.loads(value)
                            if attack == 'traversal':
                                manifest['files'][0]['path'] = 'db/../../escape'
                            else:
                                manifest['files'][0]['size_bytes'] = -1
                            value = json.dumps(manifest).encode()
                        if info.filename.endswith('photo.jpg') and attack == 'content':
                            value = b'x' * len(value)
                        archive.writestr(info, value)
                    if attack in {'extra', 'duplicate', 'symlink'}:
                        info = zipfile.ZipInfo('evil.jpg' if attack != 'duplicate' else 'manifest.json')
                        if attack == 'symlink':
                            info.create_system = 3
                            info.external_attr = (stat.S_IFLNK | 0o777) << 16
                        archive.writestr(info, b'outside')
                with self.assertRaises(ValueError):
                    verify_backup(damaged)
                with self.assertRaises(ValueError):
                    restore_backup(damaged, self.target)
                self.assertFalse(self.target.exists())
                self.assertFalse((self.root / 'escape').exists())
        damaged.write_bytes(b'PK truncated')
        with self.assertRaises(ValueError):
            verify_backup(damaged)

    def test_zip_no_overwrite_overlap_or_partial_output_on_failure(self):
        bundle = self.root / 'photos.zip'
        with self.library.writing(), self.assertRaises(ValueError):
            create_backup(self.library, bundle)
        with self.assertRaises(ValueError):
            create_backup(self.library, self.library.db / 'backup.zip')
        with patch('backup.shutil.disk_usage', return_value=SimpleNamespace(free=0)), self.assertRaises(ValueError):
            create_backup(self.library, bundle)
        self.assertFalse(bundle.exists())
        with patch('backup.verify_backup', side_effect=ValueError('verification failed')), self.assertRaises(ValueError):
            create_backup(self.library, bundle)
        self.assertFalse(bundle.exists())
        create_backup(self.library, bundle)
        saved = bundle.read_bytes()
        with self.assertRaises(ValueError):
            create_backup(self.library, bundle)
        self.assertEqual(bundle.read_bytes(), saved)
        with patch('backup.shutil.disk_usage', return_value=SimpleNamespace(free=0)), self.assertRaises(ValueError):
            restore_backup(bundle, self.target)
        self.assertFalse(self.target.exists())


if __name__ == '__main__':
    unittest.main()
