"""저장된 설정·스캔 상태 조회 및 병합 복사 CLI."""
import argparse
import json
import os
import signal
import sys
import threading
from pathlib import Path

from library import Library
from scan_engine import scan_sessions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=os.environ.get('PHOTO_BROWSER_DB', str(Path(__file__).parent / 'db')), help='서버와 동일한 JSON DB 경로')
    parser.add_argument('--root', default='/', help='서버와 동일한 허용 루트 (기본 /)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('config', help='저장된 설정 조회')
    status = commands.add_parser('status', help='소스별 최신 스캔 상태 조회')
    status.add_argument('--source-id', help='특정 소스만 조회')
    compare = commands.add_parser('compare', help='원본·병합 파일 수/용량 및 복사 무결성 비교')
    compare.add_argument('--source-id', help='특정 소스만 비교 (기본 전체)')
    compare.add_argument('--quick', action='store_true', help='SHA-256 없이 크기만 비교')
    merge = commands.add_parser('merge', help='병합 복사 실행 (원본 유지)')
    options = merge.add_mutually_exclusive_group()
    options.add_argument('--preview', action='store_true', help='복사 없이 대상 경로 확인')
    options.add_argument('--resume', metavar='MERGE_ID', help='중지한 병합 이어하기')
    merge.add_argument('--media-id', action='append', help='대상 미디어 ID (여러 번 지정 가능, 기본 전체)')
    args = parser.parse_args(argv)
    if args.command == 'merge' and args.resume and args.media_id:
        parser.error('--resume과 --media-id는 함께 사용할 수 없습니다.')
    try:
        db = Path(args.db).expanduser().resolve()
        if not (db / 'config.json').is_file():
            raise ValueError(f'설정 DB가 없습니다: {db}. 서버에서 설정한 DB 경로를 지정하세요.')
        library = Library(db, Path(args.root).expanduser())
        if args.command == 'config':
            result = {'db': str(db), 'allowed_root': str(library.boundary), 'config': library.config()}
        elif args.command == 'status':
            sources = library.config()['sources']
            if args.source_id:
                sources = [s for s in sources if s['source_id'] == args.source_id]
                if not sources:
                    raise ValueError('등록된 소스를 찾지 못했습니다.')
            sessions = {s['source_id']: s for s in scan_sessions(library)}
            result = {'db': str(db), 'items': []}
            for source in sources:
                state = sessions.get(source['source_id'])
                result['items'].append({
                    'source_id': source['source_id'],
                    'status': state['status'] if state else 'not_scanned',
                    'scan_complete': bool(state and state['status'] == 'completed' and state.get('published')),
                    'error_count': len(state.get('errors', [])) if state else 0,
                    'scan': state,
                })
        elif args.command == 'compare':
            from copy_check import compare_copies
            result = compare_copies(library, args.source_id, args.quick)
        else:
            stop = threading.Event()
            previous = signal.signal(signal.SIGINT, lambda *_: stop.set())
            try:
                result = library.merge(ids=args.media_id, preview=args.preview, stopped=stop.is_set, resume=args.resume)
            finally:
                signal.signal(signal.SIGINT, previous)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == 'compare':
            return 0 if result['ok'] else 1
        if args.command == 'merge':
            return 1 if result['status'] != 'completed' or any(op['status'] == 'error' for op in result['operations']) else 0
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f'오류: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
