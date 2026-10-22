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
    commands.add_parser('skills', help='사진·명함·견적서 분석 Skill과 응답 규격 조회')
    skill_save = commands.add_parser('skill-save', help='사용자 페르소나 JSON 등록·버전 갱신')
    skill_save.add_argument('--file', required=True, help='Skill 정의 JSON 경로')
    prepare = commands.add_parser('analysis-prepare', help='Skill별 프롬프트·Ollama 요청 준비 (모델 호출 없음)')
    prepare.add_argument('--media-id', required=True)
    prepare.add_argument('--skill', default='photo_docent')
    prepare.add_argument('--instruction', default='', help='이번 이미지에 대한 추가 요청')
    prepare.add_argument('--model', default='gemma4:31b')
    prepare.add_argument('--include-image', action='store_true', help='해시 검증한 원본 이미지 Base64도 출력')
    result_save = commands.add_parser('analysis-save', help='모델 응답 JSON 검증·별도 저장')
    result_save.add_argument('--request-id', required=True)
    result_save.add_argument('--file', required=True, help='모델이 반환한 결과 객체 JSON 파일')
    results = commands.add_parser('analysis-results', help='사진에 연결된 분석 결과 조회')
    results.add_argument('--media-id', required=True)
    status = commands.add_parser('status', help='소스별 최신 스캔 상태 조회')
    status.add_argument('--source-id', help='특정 소스만 조회')
    compare = commands.add_parser('compare', help='원본·병합 파일 수/용량 및 복사 무결성 비교')
    compare.add_argument('--source-id', help='특정 소스만 비교 (기본 전체)')
    compare.add_argument('--quick', action='store_true', help='SHA-256 없이 크기만 비교')
    backup = commands.add_parser('backup', help='DB와 관리 파일을 검증된 폴더 또는 ZIP으로 백업')
    backup.add_argument('--destination', required=True, help='새 백업 경로 (.zip이면 기본 ZIP 형식)')
    backup.add_argument('--format', choices=['directory', 'zip'], help='백업 형식 (생략 시 .zip 확장자로 자동 선택)')
    check = commands.add_parser('backup-check', help='백업의 파일 목록·크기·SHA-256 검증')
    check.add_argument('--backup', required=True, help='백업 디렉토리 또는 ZIP 파일')
    restore = commands.add_parser('restore', help='백업을 새 장치·경로에 검증 복원')
    restore.add_argument('--backup', required=True, help='백업 디렉토리 또는 ZIP 파일')
    restore.add_argument('--destination', required=True, help='새 복원 디렉토리 (db/managed 생성)')
    merge = commands.add_parser('merge', help='병합 복사 실행 (원본 유지)')
    options = merge.add_mutually_exclusive_group()
    options.add_argument('--preview', action='store_true', help='복사 없이 대상 경로 확인')
    options.add_argument('--resume', metavar='MERGE_ID', help='중지한 병합 이어하기')
    merge.add_argument('--media-id', action='append', help='대상 미디어 ID (여러 번 지정 가능, 기본 전체)')
    args = parser.parse_args(argv)
    if args.command == 'merge' and args.resume and args.media_id:
        parser.error('--resume과 --media-id는 함께 사용할 수 없습니다.')
    try:
        if args.command == 'backup-check':
            from backup import verify_backup
            print(json.dumps(verify_backup(args.backup), ensure_ascii=False, indent=2))
            return 0
        if args.command == 'restore':
            from backup import restore_backup
            print(json.dumps(restore_backup(args.backup, args.destination), ensure_ascii=False, indent=2))
            return 0
        db = Path(args.db).expanduser().resolve()
        if not (db / 'config.json').is_file():
            raise ValueError(f'설정 DB가 없습니다: {db}. 서버에서 설정한 DB 경로를 지정하세요.')
        library = Library(db, Path(args.root).expanduser())
        if args.command in {'skills', 'skill-save', 'analysis-prepare', 'analysis-save', 'analysis-results'}:
            from analysis_skills import AnalysisSkills
            store = AnalysisSkills(library)
            if args.command == 'skills':
                result = {'items': store.list()}
            elif args.command == 'skill-save':
                result = store.save_profile(json.loads(Path(args.file).read_text(encoding='utf-8')))
            elif args.command == 'analysis-prepare':
                result = store.prepare(args.media_id, args.skill, args.instruction, args.model, args.include_image)
            elif args.command == 'analysis-save':
                result = store.save_result(args.request_id, Path(args.file).read_text(encoding='utf-8'))
            else:
                result = {'items': store.results(args.media_id)}
        elif args.command == 'config':
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
        elif args.command == 'backup':
            from backup import create_backup
            result = create_backup(library, args.destination, args.format)
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
    except KeyboardInterrupt:
        print('사용자 요청으로 중단했습니다.', file=sys.stderr)
        return 130
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'오류: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
