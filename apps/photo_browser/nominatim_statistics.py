"""Photo tag coverage from the current catalog, cached by immutable generation."""
import threading
from collections import Counter

from library import gps_coordinates, item_location_tags, now, read_json
from location_rescan import missing_place


class PhotoTagStatistics:
    def __init__(self, library):
        self.library = library
        self.lock = threading.Lock()
        self.generation = None
        self.cached = None

    def snapshot(self, refresh=False):
        manifest = read_json(self.library.db / 'index.json', {'chunks': []})
        generation = (manifest.get('updated_at'), tuple(c['path'] for c in manifest['chunks']))
        with self.lock:
            if not refresh and generation == self.generation:
                return {**self.cached, 'cached': True}
            counts = {'location_tags': Counter(), 'tags': Counter()}
            empty = dict.fromkeys(counts, 0)
            seen = set()
            total = missing_names = missing_gps = 0
            for chunk in manifest['chunks']:
                data = read_json(self.library.db / chunk['path'])
                if not isinstance(data, dict) or not isinstance(data.get('items'), list):
                    raise ValueError(f'현재 DB 청크를 읽지 못했습니다: {chunk["path"]}')
                for item in data['items']:
                    if item['lifecycle']['status'] != 'active' or item['media_type'] != 'image':
                        continue
                    if item['media_id'] in seen:
                        continue
                    seen.add(item['media_id'])
                    total += 1
                    missing_gps += int(gps_coordinates(item['capture']) is None)
                    missing_names += int(missing_place(item))
                    for kind, values in (('location_tags', item_location_tags(item)),
                                         ('tags', item['classification'].get('tags', []))):
                        tags = {v.strip() for v in values if isinstance(v, str) and v.strip()}
                        counts[kind].update(tags)
                        if not tags:
                            empty[kind] += 1

            def percent(count):
                return round(count * 100 / total, 2) if total else 0

            groups = {}
            for kind, counter in counts.items():
                groups[kind] = {'tag_count': len(counter), 'empty_photo_count': empty[kind],
                                'empty_percent': percent(empty[kind]),
                                'items': [{'tag': tag, 'photo_count': count, 'percent': percent(count),
                                           'missing_photo_count': total - count,
                                           'missing_percent': percent(total - count)}
                                          for tag, count in sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))]}
            self.cached = {'total_photos': total, 'missing_place_photo_count': missing_names,
                           'missing_gps_photo_count': missing_gps, 'missing_gps_percent': percent(missing_gps),
                           'tag_count': len(set(counts['location_tags']) | set(counts['tags'])),
                           'groups': groups, 'observed_at': now(), 'index_updated_at': manifest.get('updated_at')}
            self.generation = generation
            return {**self.cached, 'cached': False}
