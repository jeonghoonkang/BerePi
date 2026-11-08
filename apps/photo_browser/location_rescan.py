"""Fill missing place names for catalog photos without walking whole sources."""
import os
import shutil

from library import gps_coordinates, metadata
from place_lookup import PlaceLookup


def missing_place(item):
    names = (item.get('capture', {}).get('place') or {}).get('names') or []
    return (item['lifecycle']['status'] == 'active' and item['media_type'] == 'image'
            and not any(isinstance(name, str) and name.strip() for name in names))


def scan_missing_places(library, progress, stopped):
    places = PlaceLookup(library.db, os.environ.get('PHOTO_BROWSER_REVERSE_GEOCODER_URL', ''))
    if not places.endpoint:
        raise ValueError('사용 가능한 Nominatim 조회 주소가 없습니다.')
    with library.writing():
        items = library.items()
        pending = [item for item in items if missing_place(item)]
        state = {'status': 'running', 'total': len(pending), 'processed': 0, 'updated': 0,
                 'no_gps': 0, 'unresolved': 0, 'errors': [], 'current_file': None}
        dirty = 0

        def emit():
            state['percent'] = round(state['processed'] * 100 / state['total'], 1) if state['total'] else 100
            progress(state.copy())

        emit()
        for item in pending:
            if stopped():
                state['status'] = 'stopped'
                break
            state['current_file'] = item['name']
            emit()
            try:
                capture = item['capture']
                changed = False
                if gps_coordinates(capture) is None:
                    failures = []
                    for location in sorted(item['locations'], key=lambda loc: loc.get('role') != 'source'):
                        if location.get('status') in {'missing', 'inactive'}:
                            continue
                        state['current_file'] = location.get('path') or location.get('uri') or item['name']
                        emit()
                        try:
                            with library.materialize(location) as path:
                                fresh = metadata(path)
                            if gps_coordinates(fresh) is not None:
                                capture['location'] = fresh['location']
                                changed = True
                            break
                        except (OSError, ValueError, KeyError) as exc:
                            failures.append(str(exc))
                    else:
                        raise ValueError('사진 파일을 읽지 못했습니다: ' + '; '.join(failures))
                if gps_coordinates(capture) is None:
                    state['no_gps'] += 1
                else:
                    # An empty place object may already carry the language policy;
                    # query it explicitly instead of enrich() skipping it.
                    place = places.lookup(gps_coordinates(capture))
                    if place and place.get('names'):
                        capture['place'] = place
                        changed = True
                        state['updated'] += 1
                    else:
                        state['unresolved'] += 1
                if changed:
                    item['revision'] += 1
                    dirty += 1
            except (OSError, ValueError, KeyError) as exc:
                state['errors'].append({'media_id': item['media_id'], 'file': state['current_file'], 'error': str(exc)})
            state['processed'] += 1
            emit()
        if dirty:
            minimum = int(library.config().get('scan_min_free_mb', 512)) * 1024 * 1024
            if shutil.disk_usage(library.db).free < minimum + len(items) * 16384:
                raise ValueError('DB 저장 공간이 부족합니다. 공간 확보 후 다시 실행하세요. 조회 캐시는 유지됩니다.')
            library.commit(items)
        if state['status'] == 'running':
            state['status'] = 'completed'
        state['warning'] = places.warning
        state['error_count'] = len(state['errors'])
        state['current_file'] = None
        emit()
        return state
