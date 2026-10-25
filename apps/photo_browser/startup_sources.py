"""Register repeated --directory inputs and report their integration scope."""
import hashlib
from pathlib import Path

from library import VIDEO_EXTENSIONS
from scan_engine import local_media_files, scan_sessions


def register_directories(library, directories):
    config = library.config()
    managed = library.local(config['managed_root'])
    paths = []
    for value in directories:
        path = library.local(value)
        if not path.is_dir():
            raise ValueError(f'소스 디렉토리가 없거나 폴더가 아닙니다: {path}')
        if path.is_relative_to(managed) or path.is_relative_to(library.db):
            raise ValueError(f'관리 디렉토리 또는 DB를 소스로 지정할 수 없습니다: {path}')
        if path not in paths:
            paths.append(path)
    existing = {library.source_key(source): source for source in config['sources']}
    ids = {source['source_id'] for source in config['sources']}
    reports = []
    for path in paths:
        source = existing.get(('file', str(path)))
        added = source is None
        if added:
            base = 'directory_' + hashlib.sha256(str(path).encode('utf-8')).hexdigest()[:12]
            source_id, suffix = base, 2
            while source_id in ids:
                source_id = f'{base}_{suffix}'
                suffix += 1
            ids.add(source_id)
            source = {'source_id': source_id, 'protocol': 'file', 'root': str(path),
                      'category': 'family', 'owner_id': 'default', 'recursive': True}
            config['sources'].append(source)
        reports.append({'source': source, 'added': added})
    if any(report['added'] for report in reports):
        library.save_config(config)
    return reports


def print_directory_summary(library, reports):
    def output(message):
        print(message, flush=True)
    output('\n여러 --directory 소스의 사진·동영상을 하나의 라이브러리로 통합합니다.')
    output(f"통합 관리 디렉토리: {library.config()['managed_root']}")
    output('지금은 소스 등록과 파일 수·용량 집계를 수행합니다. 소스별 스캔 후 병합을 실행하면 관리 디렉토리로 복사됩니다.')
    output('기존 등록 여부는 현재 DB 기준이며, 등록만으로 스캔·병합 완료를 의미하지 않습니다.')
    try:
        sessions = {state['source_id']: state for state in scan_sessions(library)}
        history_error = None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        sessions, history_error = {}, str(exc)
    total_files = total_bytes = errors = 0
    for report in reports:
        source = report['source']
        label = '신규 추가' if report['added'] else '기존 등록'
        output(f"\n[{label}] {source['root']} (소스 ID: {source['source_id']})")
        output('  파일 집계 중…' + (' 하위 폴더 포함' if source.get('recursive', True) else ' 현재 폴더만'))
        images = videos = size = 0
        failures = []
        try:
            for _, info in local_media_files(library, source):
                path = Path(info['path'])
                try:
                    file_size = path.stat().st_size
                except OSError as exc:
                    failures.append(str(exc))
                    continue
                size += file_size
                if path.suffix.lower() in VIDEO_EXTENSIONS:
                    videos += 1
                else:
                    images += 1
        except OSError as exc:
            failures.append(str(exc))
        output(f'  지원 미디어 파일: {images + videos:,}개 (사진 {images:,}개, 동영상 {videos:,}개)'
               f' · 총 용량 {size:,}바이트 ({size / 1048576:,.2f} MiB)'
               + (' · 불완전한 집계' if failures else ''))
        state = sessions.get(source['source_id'])
        if history_error:
            output(f'  이전 스캔 기록 조회 실패: {history_error}')
        elif state:
            output(f"  이전 스캔: {state['status']} · 처리 {state.get('processed', 0):,}/{state.get('total', 0):,}개"
                   + (' · DB 반영 완료' if state.get('published') else ' · DB 반영 미완료'))
        else:
            output('  이전 스캔: 기록 없음 (스캔 필요)')
        for failure in failures:
            output(f'  집계 오류: {failure}')
        total_files += images + videos
        total_bytes += size
        errors += len(failures)
    output(f'\n통합 대상: {len(reports):,}개 소스 · 지원 미디어 {total_files:,}개 · {total_bytes:,}바이트'
           + (f' · 집계 오류 {errors:,}건' if errors else ''))
    output('소스별 합계는 중복 제거 전 수치입니다. 경로가 겹치거나 같은 파일 내용이 있으면 중복 집계될 수 있습니다.\n')
