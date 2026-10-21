import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from app import create_app
from library import metadata, read_json


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'photos'
        self.source.mkdir()
        self.app = create_app(self.root, self.root, self.root / 'db')
        self.client = self.app.test_client()
        self.library = self.app.extensions['photo_library']
        self.config = {'managed_root': str(self.root / 'organized'), 'sources': [{'source_id': 'local', 'protocol': 'file', 'root': str(self.source), 'category': 'family', 'owner_id': 'alice', 'recursive': True}]}
        self.library.save_config(self.config)
        self.headers = {'X-Photo-Browser': '1'}

    def tearDown(self):
        self.temporary.cleanup()

    def photo(self, name='photo.jpg', color='red'):
        path = self.source / name
        exif = Image.Exif()
        # Top-level DateTimeOriginal is accepted in addition to nested EXIF IFD.
        exif[36867] = '2024:03:05 12:30:00'
        Image.new('RGB', (8, 8), color).save(path, exif=exif)
        return path

    def post(self, path, data):
        return self.client.post(path, json=data, headers=self.headers)

    def test_month_chunks_and_incremental_edit_preservation(self):
        path = self.photo()
        for i in range(100):
            (self.source / f'copy{i}.jpg').write_bytes(path.read_bytes())
        report = self.library.scan('local')
        self.assertEqual(report['added'], 101)
        index = read_json(self.root / 'db/index.json')
        self.assertEqual([c['count'] for c in index['chunks']], [100, 1])
        for chunk in index['chunks']:
            self.assertEqual(Path(chunk['path']).parent.as_posix(), 'media/family/alice/2024/03')
        item = self.library.items()[0]
        self.library.edit([item['media_id']], {'events': ['제주 여행'], 'tags': ['바다'], 'person_ids': ['bob']})
        self.assertEqual(self.library.scan('local')['updated'], 0)
        response = self.client.get('/api/library?event=제주 여행&tag=바다&person=bob&from=2024-03-05&to=2024-03-05').json
        self.assertEqual(response['total'], 1)
        self.assertEqual(response['items'][0]['media_id'], item['media_id'])
        self.assertEqual(len(self.library.duplicates()['exact'][0]['members']), 101)

    def test_merge_verified_shared_trash_restore_and_purge(self):
        first = self.photo()
        (self.source / 'nested').mkdir()
        (self.source / 'nested' / first.name).write_bytes(first.read_bytes())
        self.library.scan('local')
        ids = [i['media_id'] for i in self.library.items()]
        self.assertTrue(all(o['status'] == 'planned' for o in self.library.merge(preview=True)['operations']))
        self.assertFalse((self.root / 'organized').exists())
        result = self.library.merge()
        self.assertEqual([o['status'] for o in result['operations']], ['copied', 'reused'])
        target = Path(result['operations'][0]['destination'])
        self.assertEqual(target.parent.relative_to(self.root / 'organized').as_posix(), 'family/alice/2024/03')
        trash1 = self.library.trash([ids[0]])
        self.assertTrue(target.exists())
        trash2 = self.library.trash([ids[1]])
        self.assertFalse(target.exists())
        # Restore an earlier logical delete whose shared bytes were moved later.
        self.library.restore(trash1['trash_id'])
        self.assertTrue(target.exists())
        self.library.restore(trash2['trash_id'])
        trash = self.library.trash(ids)
        self.assertTrue(first.exists())
        self.assertEqual(self.library.scan('local')['added'], 0)
        self.assertEqual(self.client.get('/api/library').json['total'], 0)
        self.assertEqual(self.post(f"/api/trash/{trash['trash_id']}/purge", {}).status_code, 400)
        prepared = self.post(f"/api/trash/{trash['trash_id']}/prepare", {}).json
        purged = self.post(f"/api/trash/{trash['trash_id']}/purge", {'token': prepared['token'], 'phrase': prepared['phrase']})
        self.assertEqual(purged.json['status'], 'purged')
        self.assertTrue(first.exists())
        with self.assertRaises(ValueError):
            self.library.restore(trash['trash_id'])

    def test_merge_preserves_all_different_contents_with_duplicate_suffix(self):
        original = self.photo('가족 사진.JPG')
        (self.source / 'nested').mkdir()
        other = self.source / 'nested' / original.name
        with Image.open(original) as image:
            exif = image.getexif()
        Image.new('RGB', (8, 8), 'blue').save(other, exif=exif)
        self.library.scan('local')
        preview = self.library.merge(preview=True)
        self.assertEqual({Path(op['destination']).name for op in preview['operations']}, {'가족 사진.JPG', '가족 사진_중복.JPG'})
        self.assertEqual(preview['destination_conflicts'], [])
        self.assertEqual(preview['renamed_count'], 1)
        result = self.library.merge()
        self.assertEqual([op['status'] for op in result['operations']], ['copied', 'copied'])
        self.assertEqual([op['destination'] for op in result['operations']], [op['destination'] for op in preview['operations']])
        self.assertEqual({Path(op['destination']).read_bytes() for op in result['operations']}, {original.read_bytes(), other.read_bytes()})
        self.assertEqual([op['status'] for op in self.library.merge()['operations']], ['reused', 'reused'])
        self.assertEqual(len(list(Path(self.config['managed_root']).rglob('*.JPG'))), 2)
        for item in self.library.items():
            managed = next(loc for loc in item['locations'] if loc['role'] == 'managed')
            source = Path(item['locations'][0]['path'])
            self.assertEqual(Path(managed['path']).read_bytes(), source.read_bytes())

    def test_item_lookup_reads_only_target_chunk_and_refreshes(self):
        self.photo()
        self.library.scan('local')
        item = self.library.items()[0]
        media_id = item['media_id']
        self.assertEqual(self.library.item(media_id), item)
        with patch('library.read_json', wraps=read_json) as reads, patch.object(self.library, 'items', side_effect=AssertionError('full collection loaded')):
            with self.client.get(f'/api/library/{media_id}/file') as response:
                self.assertEqual(response.status_code, 200)
            self.assertEqual(reads.call_count, 2)  # manifest + one media chunk
            self.assertEqual(self.client.get(f'/api/library/{media_id}').json['media_id'], media_id)
            self.assertEqual(self.client.get('/api/library/missing/file').status_code, 404)
        item['classification']['tags'] = ['updated']
        self.library.commit([item])
        self.assertEqual(self.library.item(media_id)['classification']['tags'], ['updated'])
        item['lifecycle']['status'] = 'trashed'
        self.library.commit([item])
        self.assertEqual(self.client.get(f'/api/library/{media_id}/file').status_code, 404)
        self.library.commit([])
        self.assertIsNone(self.library.item(media_id))

    def test_concurrent_item_lookup_builds_one_index(self):
        from concurrent.futures import ThreadPoolExecutor
        self.photo()
        self.library.scan('local')
        item = self.library.items()[0]
        with patch('library.read_json', wraps=read_json) as reads:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(self.library.item, [item['media_id']] * 8))
            self.assertTrue(all(result == item for result in results))
            self.assertEqual(reads.call_count, 17)  # 8 manifests + 8 target chunks + one index build

    def test_merge_preview_reports_intermediate_progress_without_copying(self):
        import copy
        self.photo()
        self.library.scan('local')
        sample = self.library.items()[0]
        items = []
        for index in range(205):
            item = copy.deepcopy(sample)
            item['media_id'] = str(index)
            item['name'] = f'{index}.jpg'
            items.append(item)
        self.library.commit(items)
        updates = []
        result = self.library.merge(preview=True, progress=updates.append)
        self.assertEqual(updates[0]['phase'], 'loading')
        self.assertEqual([p['processed'] for p in updates[1:]], [0, 100, 200, 205])
        self.assertEqual(updates[-1]['percent'], 100)
        self.assertTrue(updates[-1]['current_file'].endswith('.jpg'))
        self.assertEqual(len(result['operations']), 205)
        self.assertFalse(Path(self.config['managed_root']).exists())
        response = self.post('/api/merge', {'preview': True})
        self.assertEqual(response.status_code, 202)
        for _ in range(200):
            status = self.client.get('/api/jobs/' + response.json['job_id']).json
            if status['status'] not in ('queued', 'running'):
                break
            time.sleep(0.01)
        self.assertEqual(status['kind'], 'merge_preview')
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['progress']['percent'], 100)

    def test_apply_source_classification_and_refresh_merge_paths(self):
        self.photo()
        self.library.scan('local')
        original = self.library.items()[0]
        self.library.edit([original['media_id']], {'tags': ['keep'], 'events': ['trip']})
        old_plan = self.library.merge(preview=True)
        self.assertIn('/family/alice/', Path(old_plan['operations'][0]['destination']).as_posix())
        config = self.library.config()
        config['sources'][0].update(category='photo_save', owner_id='tinyos')
        self.library.save_config(config)
        result = self.library.apply_source_classification('local')
        self.assertEqual(result['updated'], 1)
        item = self.library.items()[0]
        self.assertEqual(item['classification']['tags'], ['keep'])
        self.assertEqual(item['classification']['events'], ['trip'])
        self.assertEqual(item['locations'], original['locations'])
        refreshed = self.library.merge(preview=True)
        self.assertIn('/photo_save/tinyos/', Path(refreshed['operations'][0]['destination']).as_posix())
        self.assertEqual(refreshed['operations'][0]['classification']['category_id'], 'photo_save')
        self.assertEqual(refreshed['settings']['managed_root'], config['managed_root'])
        self.assertEqual(refreshed['destination_conflicts'], [])
        self.assertFalse(Path(refreshed['operations'][0]['destination']).exists())
        self.assertEqual(self.library.apply_source_classification('local')['updated'], 0)
        with self.assertRaises(ValueError):
            self.library.apply_source_classification('missing')

    def test_source_classification_only_changes_matching_active_items(self):
        import copy
        self.photo()
        self.library.scan('local')
        active = self.library.items()[0]
        other = copy.deepcopy(active)
        other['media_id'] = 'other'
        other['locations'][0]['source_id'] = 'different'
        trashed = copy.deepcopy(active)
        trashed['media_id'] = 'trashed'
        trashed['lifecycle']['status'] = 'trashed'
        self.library.commit([active, other, trashed])
        config = self.library.config()
        config['sources'][0]['category'] = 'photo_save'
        self.library.save_config(config)
        result = self.library.apply_source_classification('local')
        self.assertEqual(result['matched'], 1)
        self.assertEqual(self.library.item('other')['classification']['category_id'], 'family')
        self.assertEqual(self.library.item('trashed')['classification']['category_id'], 'family')

    def test_facets_summary_and_legacy_streaming_cache(self):
        import copy
        self.photo()
        self.library.scan('local')
        active = self.library.items()[0]
        active['classification']['tags'] = ['visible']
        trashed = copy.deepcopy(active)
        trashed['media_id'] = 'trashed'
        trashed['lifecycle']['status'] = 'trashed'
        trashed['classification']['tags'] = ['hidden']
        self.library.commit([active, trashed])
        with patch.object(self.library, 'items', side_effect=AssertionError('full DB read')), patch('library.read_json', wraps=read_json) as reads:
            response = self.client.get('/api/facets')
            self.assertEqual(response.json['tags'], ['visible'])
            self.assertEqual(reads.call_count, 1)
        index_path = self.library.db / 'index.json'
        index = read_json(index_path)
        index.pop('active_facets')
        index_path.write_text(json.dumps(index), encoding='utf-8')
        with patch.object(self.library, 'items', side_effect=AssertionError('full DB read')):
            self.assertEqual(self.library.facets()['tags'], ['visible'])
            with patch('library.read_json', wraps=read_json) as reads:
                self.assertEqual(self.library.facets()['tags'], ['visible'])
                self.assertEqual(reads.call_count, 1)
        active['classification']['tags'] = ['new']
        self.library.commit([active])
        self.assertEqual(self.library.facets()['tags'], ['new'])
        self.library.commit([])
        self.assertEqual(self.library.facets()['tags'], [])

    def test_save_existing_source_category_is_returned_and_persisted(self):
        config = self.client.get('/api/config').json
        config['sources'][0]['category'] = 'photobox'
        self.assertEqual(self.client.put('/api/config', json=config, headers=self.headers).status_code, 200)
        config = self.client.get('/api/config').json
        config['sources'][0]['category'] = 'photo_box'
        response = self.client.put('/api/config', json=config, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['sources'][0]['category'], 'photo_box')
        self.assertEqual(self.client.get('/api/config').json['sources'][0]['category'], 'photo_box')
        self.assertEqual(read_json(self.library.db / 'config.json')['sources'][0]['category'], 'photo_box')

    def test_duplicate_sources_compare_and_unregister_without_deleting_files(self):
        import shutil
        original = self.photo()
        backup = self.root / 'backup'
        backup.mkdir()
        shutil.copy2(original, backup / original.name)
        config = self.library.config()
        config['sources'].append(dict(config['sources'][0], source_id='backup', root=str(backup)))
        self.library.save_config(config)
        self.library.scan('local')
        self.library.scan('backup')
        report = self.client.get('/api/duplicate-sources').json
        self.assertEqual(len(report['groups']), 1)
        group = report['groups'][0]
        self.assertTrue(group['same_content'])
        self.assertEqual(group['file_count'], 1)
        self.assertEqual(group['total_bytes'], original.stat().st_size)
        self.assertEqual(group['files'][0]['relative_path'], original.name)
        rejected = self.post('/api/duplicate-sources/unregister', {'source_id': 'backup', 'keep_id': 'local', 'fingerprint': 'stale'})
        self.assertEqual(rejected.status_code, 400)
        count = len(self.library.items())
        removed = self.post('/api/duplicate-sources/unregister', {'source_id': 'backup', 'keep_id': 'local', 'fingerprint': group['fingerprint']})
        self.assertEqual(removed.status_code, 200)
        self.assertEqual([s['source_id'] for s in self.library.config()['sources']], ['local'])
        self.assertTrue(original.exists())
        self.assertTrue((backup / original.name).exists())
        self.assertEqual(len(self.library.items()), count)
        self.assertEqual(self.library.duplicate_sources()['groups'], [])

    def test_duplicate_source_cleanup_removes_only_exclusive_managed_files(self):
        import shutil
        original = self.photo()
        backup = self.root / 'backup'
        backup.mkdir()
        shutil.copy2(original, backup / original.name)
        config = self.library.config()
        backup_config = dict(config['sources'][0], source_id='backup', root=str(backup))
        config['sources'].append(backup_config)
        self.library.save_config(config)
        self.library.scan('local')
        self.library.scan('backup')
        root = Path(config['managed_root'])
        root.mkdir()
        own, shared = root / 'exclusive.jpg', root / 'shared.jpg'
        shutil.copy2(original, own)
        shutil.copy2(original, shared)
        items = self.library.items()
        for item in items:
            item['locations'].append({'role': 'managed', 'protocol': 'file', 'path': str(shared), 'status': 'available'})
            if item['locations'][0]['source_id'] == 'backup':
                item['locations'].append({'role': 'managed', 'protocol': 'file', 'path': str(own), 'status': 'available'})
        self.library.commit(items)
        group = self.library.duplicate_sources()['groups'][0]
        result = self.library.unregister_duplicate_source('backup', 'local', group['fingerprint'])
        self.assertEqual(result['deleted_managed_files'], 1)
        self.assertEqual(result['retained_shared_files'], 1)
        self.assertFalse(own.exists())
        self.assertTrue(shared.exists())
        self.assertTrue(original.exists())
        self.assertTrue((backup / original.name).exists())
        removed = next(item for item in self.library.items() if item['locations'][0]['source_id'] == 'backup')
        self.assertEqual(removed['lifecycle']['status'], 'source_unregistered')
        archive = read_json(self.library.db / 'source_cleanup' / (result['cleanup_id'] + '.json'))
        self.assertTrue(any(loc.get('path') == str(own) for item in archive['items_before'] for loc in item['locations']))
        config = self.library.config()
        config['sources'].append(backup_config)
        self.library.save_config(config)
        self.library.scan('backup')
        restored = next(item for item in self.library.items() if item['media_id'] == removed['media_id'])
        self.assertEqual(restored['lifecycle']['status'], 'active')

    def test_duplicate_sources_distinguishes_contents_and_file_lists(self):
        import copy
        self.photo()
        self.library.scan('local')
        first = self.library.items()[0]
        second = copy.deepcopy(first)
        second['media_id'] = 'second'
        second['sha256'] = 'different'
        backup = self.root / 'backup'
        config = self.library.config()
        config['sources'].append(dict(config['sources'][0], source_id='backup', root=str(backup)))
        self.library.save_config(config)
        second['locations'][0].update(source_id='backup', path=str(backup / first['name']), uri=(backup / first['name']).as_uri())
        self.library.commit([first, second])
        self.assertFalse(self.library.duplicate_sources()['groups'][0]['same_content'])
        second['locations'][0]['path'] = str(backup / 'another.jpg')
        self.library.commit([first, second])
        self.assertEqual(self.library.duplicate_sources()['groups'], [])
        second['locations'][0]['path'] = str(backup / first['name'])
        second['size_bytes'] += 1
        self.library.commit([first, second])
        self.assertEqual(self.library.duplicate_sources()['groups'], [])

    def test_duplicate_source_path_and_rename(self):
        self.photo()
        self.library.scan('local')
        before = self.library.items()[0]['media_id']
        duplicate = dict(self.config, sources=self.config['sources'] + [dict(self.config['sources'][0], source_id='other', root=str(self.source / '.'))])
        with self.assertRaisesRegex(ValueError, '기존 소스 ID: local'):
            self.library.save_config(duplicate)
        check = self.post('/api/sources/check', {'root': str(self.source / '.'), 'protocol': 'file'})
        self.assertEqual(check.json['existing']['source_id'], 'local')
        renamed = self.post('/api/sources/rename', {'old_id': 'local', 'new_id': 'family_photos'})
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(self.library.items()[0]['locations'][0]['source_id'], 'family_photos')
        self.library.scan('family_photos')
        self.assertEqual(len(self.library.items()), 1)
        self.assertEqual(self.library.items()[0]['media_id'], before)

    def test_source_rename_background_job(self):
        self.photo()
        self.library.scan('local')
        original_id = self.library.items()[0]['media_id']
        response = self.post('/api/sources/rename', {'old_id': 'local', 'new_id': '134server', 'background': True})
        self.assertEqual(response.status_code, 202)
        job_id = response.json['job_id']
        for _ in range(200):
            status = self.client.get(f'/api/jobs/{job_id}').json
            if status['status'] not in ('queued', 'running'):
                break
            time.sleep(0.01)
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['result']['sources'][0]['source_id'], '134server')
        self.assertEqual(self.library.config()['sources'][0]['source_id'], '134server')
        item = self.library.items()[0]
        self.assertEqual(item['media_id'], original_id)
        self.assertEqual(item['locations'][0]['source_id'], '134server')

    def test_background_rename_rejects_overlapping_jobs(self):
        started, release = threading.Event(), threading.Event()
        def slow_rename(old, new):
            started.set()
            release.wait(5)
            return self.config
        with patch.object(self.library, 'rename_source', side_effect=slow_rename):
            response = self.post('/api/sources/rename', {'old_id': 'local', 'new_id': 'new', 'background': True})
            self.assertEqual(response.status_code, 202)
            try:
                self.assertTrue(started.wait(2))
                overlap = self.post('/api/sources/rename', {'old_id': 'local', 'new_id': 'other', 'background': True})
                self.assertEqual(overlap.status_code, 400)
                scan = self.post('/api/scan', {'source_id': 'local'})
                self.assertEqual(scan.status_code, 400)
            finally:
                release.set()
                for _ in range(200):
                    status = self.client.get('/api/jobs/' + response.json['job_id']).json
                    if status['status'] == 'completed':
                        break
                    time.sleep(0.01)

    def test_merge_low_space_blocks_before_copy_or_db_commit(self):
        from types import SimpleNamespace
        self.photo()
        self.library.scan('local')
        index = (self.library.db / 'index.json').read_bytes()
        with patch('library.shutil.disk_usage', return_value=SimpleNamespace(free=0)), patch('library.shutil.copy2') as copy_file:
            result = self.library.merge()
        self.assertEqual(result['status'], 'blocked_low_space')
        self.assertFalse(result['disk_space']['ok'])
        self.assertGreater(result['disk_space']['copy_bytes'], 0)
        self.assertEqual(result['operations'], [])
        copy_file.assert_not_called()
        self.assertFalse(Path(self.config['managed_root']).exists())
        self.assertEqual((self.library.db / 'index.json').read_bytes(), index)
        self.assertFalse((self.library.db / 'merges').exists())

    def test_merge_space_counts_unique_targets_and_excludes_existing_files(self):
        import copy
        from types import SimpleNamespace
        self.photo()
        self.library.scan('local')
        item = self.library.items()[0]
        duplicate = copy.deepcopy(item)
        duplicate['media_id'] = 'duplicate'
        root = Path(self.config['managed_root'])
        with patch('library.shutil.disk_usage', return_value=SimpleNamespace(free=10**12)):
            space = self.library.merge_space(root, [item, duplicate], [item, duplicate], lambda p: None)
            self.assertTrue(space['ok'])
            self.assertEqual(space['copy_files'], 1)
            self.assertEqual(space['copy_bytes'], item['size_bytes'])
            self.assertEqual(len(space['volumes']), 1)
            self.assertEqual(space['volumes'][0]['required_bytes'], space['copy_bytes'] + space['db_estimated_bytes'] + space['volumes'][0]['reserve_bytes'])
            target = self.library.merge_target(root, item)
            target.parent.mkdir(parents=True)
            target.write_bytes((self.source / 'photo.jpg').read_bytes())
            space = self.library.merge_space(root, [item], [item], lambda p: None)
            self.assertEqual(space['copy_bytes'], 0)
            self.assertEqual(space['copy_files'], 0)
            target.write_bytes(b'different existing contents')
            space = self.library.merge_space(root, [item], [item], lambda p: None)
            self.assertEqual(space['copy_bytes'], item['size_bytes'])
            self.assertEqual(space['copy_files'], 1)

    def test_merge_skips_occupied_duplicate_names_and_reuses_matching_suffix(self):
        self.photo('사진1.jpg')
        self.library.scan('local')
        item = self.library.items()[0]
        target = self.library.merge_target(Path(self.config['managed_root']), item)
        target.parent.mkdir(parents=True)
        target.write_bytes(b'original occupied')
        target.with_name('사진1_중복.jpg').write_bytes(b'first suffix occupied')
        target.with_name('사진1_중복_2.jpg').mkdir()
        report = self.library.merge()
        destination = Path(report['operations'][0]['destination'])
        self.assertEqual(destination.name, '사진1_중복_3.jpg')
        self.assertEqual(report['operations'][0]['rename_reason'], 'name_collision')
        self.assertEqual(target.read_bytes(), b'original occupied')
        self.assertEqual(target.with_name('사진1_중복.jpg').read_bytes(), b'first suffix occupied')
        self.assertEqual(self.library.merge()['operations'][0]['status'], 'reused')
        self.assertEqual(destination.read_bytes(), (self.source / '사진1.jpg').read_bytes())

    def test_merge_late_filename_collision_never_overwrites(self):
        self.photo()
        self.library.scan('local')
        original_publish = self.library.publish_merge_copy
        calls = []
        def collision(temporary, target):
            if not calls:
                calls.append(target)
                target.write_bytes(b'late external file')
                raise FileExistsError(str(target))
            original_publish(temporary, target)
        with patch.object(self.library, 'publish_merge_copy', side_effect=collision):
            report = self.library.merge()
        self.assertEqual(report['operations'][0]['status'], 'copied')
        self.assertEqual(Path(report['operations'][0]['destination']).name, 'photo_중복.jpg')
        self.assertEqual(calls[0].read_bytes(), b'late external file')
        self.assertEqual(Path(report['operations'][0]['destination']).read_bytes(), (self.source / 'photo.jpg').read_bytes())

    def test_merge_identical_same_names_share_a_single_copy(self):
        source = self.photo()
        (self.source / 'nested').mkdir()
        (self.source / 'nested/photo.jpg').write_bytes(source.read_bytes())
        self.library.scan('local')
        preview = self.library.merge(preview=True)
        self.assertEqual(len({op['destination'] for op in preview['operations']}), 1)
        result = self.library.merge()
        self.assertEqual([op['status'] for op in result['operations']], ['copied', 'reused'])
        self.assertEqual(result['renamed_count'], 0)

    def test_merge_late_identical_file_is_reused(self):
        source = self.photo()
        self.library.scan('local')
        def appeared(temporary, target):
            target.write_bytes(source.read_bytes())
            raise FileExistsError(str(target))
        with patch.object(self.library, 'publish_merge_copy', side_effect=appeared):
            report = self.library.merge()
        self.assertEqual(report['operations'][0]['status'], 'reused')
        self.assertEqual(report['renamed_count'], 0)

    def test_exclusive_publication_fallback_does_not_replace_late_file(self):
        temporary = self.root / 'verified.part'
        target = self.root / 'occupied.jpg'
        temporary.write_bytes(b'verified bytes')
        target.write_bytes(b'existing bytes')
        with patch('library.os.link', side_effect=OSError('unsupported')):
            with self.assertRaises(FileExistsError):
                self.library.publish_merge_copy(temporary, target)
        self.assertEqual(target.read_bytes(), b'existing bytes')

    def test_merge_exclusive_copy_on_filesystem_without_hardlinks(self):
        self.photo()
        self.library.scan('local')
        with patch('library.os.link', side_effect=OSError('hardlinks unsupported')):
            report = self.library.merge()
        self.assertEqual(report['operations'][0]['status'], 'copied')
        self.assertEqual(Path(report['operations'][0]['destination']).read_bytes(), (self.source / 'photo.jpg').read_bytes())

    def test_merge_stop_resume_preserves_collision_renames(self):
        self.photo('photo.jpg')
        for name, color in [('one', 'blue'), ('two', 'green')]:
            folder = self.source / name
            folder.mkdir()
            with Image.open(self.source / 'photo.jpg') as image:
                exif = image.getexif()
            Image.new('RGB', (8, 8), color).save(folder / 'photo.jpg', exif=exif)
        self.library.scan('local')
        stop = [False]
        def progress(state):
            if state.get('processed', 0) >= 1:
                stop[0] = True
        report = self.library.merge(progress=progress, stopped=lambda: stop[0])
        self.assertEqual(report['status'], 'stopped')
        report = self.library.merge(resume=report['merge_id'])
        self.assertEqual([op['status'] for op in report['operations']], ['copied'] * 3)
        self.assertEqual({Path(op['destination']).name for op in report['operations']}, {'photo.jpg', 'photo_중복.jpg', 'photo_중복_2.jpg'})

    def test_merge_stop_and_resume_after_restart(self):
        for index in range(4):
            self.photo(f'photo{index}.jpg')
        self.library.scan('local')
        stop = [False]
        def progress(state):
            if state['processed'] >= 1:
                stop[0] = True
        result = self.library.merge(progress=progress, stopped=lambda: stop[0])
        self.assertEqual(result['status'], 'stopped')
        self.assertEqual(result['processed'], 1)
        self.assertEqual(len(list((self.root / 'organized').rglob('*.jpg'))), 1)
        from library import Library
        restarted = Library(self.root / 'db', self.root)
        result = restarted.merge(resume=result['merge_id'])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['processed'], 4)
        self.assertTrue(all(op['status'] == 'copied' for op in result['operations']))
        self.assertEqual(len(list((self.root / 'organized').rglob('*.jpg'))), 4)

    def test_changed_original_no_overwrite_and_integrity(self):
        source = self.photo()
        self.library.scan('local')
        item = self.library.items()[0]
        source.write_bytes(b'changed source')
        result = self.library.merge()
        self.assertEqual(result['operations'][0]['status'], 'error')
        self.library.verify([item['media_id']], True)
        self.assertEqual(self.library.items()[0]['verification']['results'][0]['status'], 'changed')
        source.unlink()
        self.library.scan('local')
        self.assertEqual(self.library.items()[0]['locations'][0]['status'], 'missing')

    def test_restore_conflict_keeps_trash(self):
        self.photo()
        self.library.scan('local')
        self.library.merge()
        entry = self.library.trash([self.library.items()[0]['media_id']])
        Path(entry['moves'][0]['original']).write_bytes(b'conflict')
        with self.assertRaises(ValueError):
            self.library.restore(entry['trash_id'])
        self.assertTrue(Path(entry['moves'][0]['trash']).exists())

    def test_purging_shared_trash_preserves_other_undo(self):
        source = self.photo()
        (self.source / 'nested').mkdir()
        (self.source / 'nested' / source.name).write_bytes(source.read_bytes())
        self.library.scan('local')
        self.library.merge()
        ids = [i['media_id'] for i in self.library.items()]
        first = self.library.trash([ids[0]])
        second = self.library.trash([ids[1]])
        self.library.purge(second['trash_id'])
        self.assertTrue(Path(second['moves'][0]['trash']).exists())
        self.library.restore(first['trash_id'])
        self.assertTrue(Path(second['moves'][0]['original']).exists())

    def test_last_shared_trash_purge_removes_retained_bytes(self):
        source = self.photo()
        (self.source / 'nested').mkdir()
        (self.source / 'nested' / source.name).write_bytes(source.read_bytes())
        self.library.scan('local')
        self.library.merge()
        ids = [i['media_id'] for i in self.library.items()]
        first = self.library.trash([ids[0]])
        second = self.library.trash([ids[1]])
        self.library.purge(second['trash_id'])
        self.library.purge(first['trash_id'])
        self.assertFalse(Path(second['moves'][0]['trash']).exists())

    def test_boundaries_write_guard_auth_and_config_validation(self):
        self.assertEqual(self.client.put('/api/config', json=self.config).status_code, 403)
        self.assertEqual(self.client.put('/api/config', json=self.config, headers={**self.headers, 'Origin': 'https://evil.example'}).status_code, 403)
        invalid = {**self.config, 'managed_root': str(self.root.parent / 'outside')}
        self.assertEqual(self.client.put('/api/config', json=invalid, headers=self.headers).status_code, 400)
        for category in ['../escape', 'CON', 'family/name']:
            with self.assertRaises(ValueError):
                self.library.save_config({**self.config, 'sources': [{**self.config['sources'][0], 'category': category}]})
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': 'test-password'}):
            self.assertEqual(self.client.get('/api/config').status_code, 401)
            self.assertEqual(self.client.get('/api/config', auth=('user', 'test-password')).status_code, 200)
        for url in ['http://evil.example/a.jpg', 'http://localhost/other/a.jpg', 'http://localhost/photos/%2e%2e/a.jpg']:
            with self.assertRaises(ValueError):
                self.library.remote_open({'root': 'http://localhost/photos/'}, url)

    def test_job_api_and_original_media(self):
        self.photo()
        response = self.post('/api/scan', {'source_id': 'local'})
        self.assertEqual(response.status_code, 202)
        for _ in range(100):
            result = self.client.get('/api/jobs/' + response.json['job_id']).json
            if result['status'] not in {'queued', 'running'}:
                break
            time.sleep(0.02)
        self.assertEqual(result['status'], 'completed')
        item = self.client.get('/api/library').json['items'][0]
        response = self.client.get(f"/api/library/{item['media_id']}/file")
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual(self.client.get(f"/api/library/{item['media_id']}").json['name'], 'photo.jpg')

    def test_interrupted_trash_can_restore(self):
        self.photo()
        self.library.scan('local')
        self.library.merge()
        with patch.object(self.library, 'commit', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.library.trash([self.library.items()[0]['media_id']])
        entry = self.library.trash_entries()[0]
        self.assertEqual(entry['status'], 'recovery_required')
        self.library.restore(entry['trash_id'])
        self.assertTrue(Path(entry['moves'][0]['original']).exists())

    def test_http_and_webdav_sources(self):
        image = self.photo().read_bytes()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == '/photos/manifest.json':
                    payload = json.dumps({'files': [{'path': 'remote.jpg', 'modified': '2023-02-10T12:00:00Z'}]}).encode()
                else:
                    payload = image
                self.send_response(200)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_PROPFIND(self):
                payload = b'<d:multistatus xmlns:d="DAV:"><d:response><d:href>/photos/remote.jpg</d:href><d:propstat><d:prop><d:getcontentlength>100</d:getcontentlength></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>'
                self.send_response(207)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for protocol in ['http', 'webdav']:
                source = {'source_id': protocol, 'protocol': protocol, 'root': f'http://127.0.0.1:{server.server_port}/photos/', 'category': 'family', 'owner_id': 'alice'}
                self.config['sources'].append(source)
                self.library.save_config(self.config)
                report = self.library.scan(protocol)
                self.assertEqual(report['errors'], [])
                self.assertEqual(report['added'], 1)
            result = self.library.merge()
            self.assertTrue(all(op['status'] != 'error' for op in result['operations']))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_date_window_uses_half_browse_limit_and_starts_on_date(self):
        import copy
        self.photo()
        self.library.scan('local')
        sample = self.library.items()[0]
        items = []
        for index, day in enumerate(('01', '02', '03', '04', '04', '05', '06', '07')):
            item = copy.deepcopy(sample)
            item['media_id'] = str(index)
            item['capture'].update(date_key=f'2024-03-{day}', captured_at=f'2024-03-{day}T12:00:00Z')
            items.append(item)
        self.app.config['PHOTO_BROWSER_LIMIT'] = 4
        with patch.object(self.library, 'items', return_value=items):
            result = self.client.get('/api/library?date=2024-03-04').json
            self.assertEqual(result['total'], 6)
            self.assertEqual(result['offset'], 2)
            self.assertEqual(result['window']['per_side'], 2)
            self.assertEqual(result['window']['on_date'], 2)
            self.assertEqual(result['window']['before_total'], 3)
            self.assertEqual(result['window']['after_total'], 3)
            self.assertEqual([i['capture']['date_key'] for i in result['items']], ['2024-03-04'] * 2 + ['2024-03-03', '2024-03-02'])
            newer = self.client.get('/api/library?date=2024-03-04&offset=0&limit=2').json
            self.assertEqual([i['capture']['date_key'] for i in newer['items']], ['2024-03-06', '2024-03-05'])
            missing = self.client.get('/api/library?date=2024-03-08').json
            self.assertEqual(missing['window']['on_date'], 0)
            self.assertEqual(len(missing['items']), 2)
            filtered = self.client.get('/api/library?date=2024-03-04&from=2024-03-04&to=2024-03-04').json
            self.assertEqual(filtered['total'], 2)
            self.app.config['PHOTO_BROWSER_LIMIT'] = 1
            small = self.client.get('/api/library?date=2024-03-04').json
            self.assertEqual(small['total'], 2)
        self.assertEqual(self.client.get('/api/library?date=bad').status_code, 400)

    def test_all_formats_scan_and_merge(self):
        for extension in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
            Image.new('RGB', (8, 8), 'red').save(self.source / f'photo.{extension}')
        for extension in ('mp4', 'mov', 'avi'):
            (self.source / f'clip.{extension.upper()}').write_bytes(extension.encode())
        payload = {'format': {'duration': '2'}, 'streams': [{'codec_type': 'video', 'width': 16, 'height': 16}]}
        with patch('library.subprocess.run', return_value=type('Probe', (), {'stdout': json.dumps(payload)})()) as probe:
            self.library.scan('local')
        self.assertEqual(probe.call_count, 3)
        items = self.library.items()
        self.assertEqual(len(items), 8)
        for item in items:
            expected = 'video' if Path(item['name']).suffix.lower() in {'.mp4', '.mov', '.avi'} else 'image'
            self.assertEqual(item['media_type'], expected)
        result = self.library.merge()
        self.assertEqual(len(result['operations']), 8)
        for operation in result['operations']:
            self.assertEqual(operation['status'], 'copied')
            destination = Path(operation['destination'])
            self.assertEqual(destination.read_bytes(), (self.source / destination.name).read_bytes())

    def test_video_capture_metadata(self):
        video = self.source / 'clip.mp4'
        video.write_bytes(b'video')
        payload = {'format': {'tags': {'creation_time': '2024-04-05T06:07:08Z', 'location': '+37.5665+126.9780/'}, 'duration': '12.5'}, 'streams': [{'codec_type': 'video', 'width': 1920, 'height': 1080}]}
        with patch('library.subprocess.run', return_value=type('Probe', (), {'stdout': json.dumps(payload)})()):
            info = metadata(video)
        self.assertEqual(info['date_key'], '2024-04-05')
        self.assertEqual(info['duration_seconds'], 12.5)
        self.assertEqual(info['location']['latitude'], 37.5665)
        self.assertEqual(info['width'], 1920)

    def test_restore_rejects_tampered_path_and_purge_requires_fresh_token(self):
        self.photo()
        self.library.scan('local')
        self.library.merge()
        entry = self.library.trash([self.library.items()[0]['media_id']])
        prepared = self.post(f"/api/trash/{entry['trash_id']}/prepare", {}).json
        wrong = self.post(f"/api/trash/{entry['trash_id']}/purge", {'token': prepared['token'], 'phrase': 'wrong'})
        self.assertEqual(wrong.status_code, 400)
        retry = self.post(f"/api/trash/{entry['trash_id']}/purge", {'token': prepared['token'], 'phrase': prepared['phrase']})
        self.assertEqual(retry.status_code, 400)
        path = self.root / 'db/trash' / (entry['trash_id'] + '.json')
        entry['moves'][0]['original'] = str(self.source / 'injected.jpg')
        path.write_text(json.dumps(entry), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.library.restore(entry['trash_id'])


if __name__ == '__main__':
    unittest.main()
