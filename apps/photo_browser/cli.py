"""저장된 설정·스캔 상태 조회 및 병합 복사 CLI."""
import argparse
import json
import math
import os
import signal
import sys
import threading
import time
from pathlib import Path

from library import Library
from scan_engine import scan_sessions


def refresh_interval(value):
    try:
        seconds = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError('갱신 간격은 0보다 큰 초 단위 숫자여야 합니다.')
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError('갱신 간격은 0보다 큰 초 단위 숫자여야 합니다.')
    return seconds


def bounded_number(minimum, maximum):
    def parse(value):
        try:
            result = int(value)
        except (TypeError, ValueError):
            raise argparse.ArgumentTypeError('정수를 입력하세요.')
        if not minimum <= result <= maximum:
            raise argparse.ArgumentTypeError(f'{minimum}~{maximum} 범위의 정수를 입력하세요.')
        return result
    return parse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    from version_info import version_info, version_label, version_logging, log_interval, DEFAULT_LOG_INTERVAL
    info = version_info()
    parser.add_argument('--version', action='version', version=version_label(info))
    parser.add_argument('--version-log-interval', type=log_interval, default=DEFAULT_LOG_INTERVAL,
                        help='버전 재출력 간격, 초 (기본 1800, 0이면 시작 시에만 출력)')
    parser.add_argument('--db', default=os.environ.get('PHOTO_BROWSER_DB', str(Path(__file__).parent / 'db')), help='서버와 동일한 JSON DB 경로')
    parser.add_argument('--root', default='/', help='서버와 동일한 허용 루트 (기본 /)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('pair-history', help='소스·DB·관리 폴더 연결 변경 이력 조회 (최근 100건)')
    commands.add_parser('config', help='저장된 설정 조회')
    audit = commands.add_parser('db-audit', help='읽기 전용 DB 분류별 파일 수·JSON 내용 요약·용량 집계')
    audit.add_argument('--format', choices=['table', 'json'], default='table')
    audit.add_argument('--top', type=bounded_number(0, 1000), default=20, help='큰 파일 표시 개수 (기본 20)')
    audit.add_argument('--sizes-only', action='store_true', help='현재 미디어 청크의 내용 요약을 생략하고 파일 크기만 집계')
    audit.add_argument('--max-files', type=bounded_number(1, 1000000000), help='지정 개수까지만 부분 집계')
    audit.add_argument('--max-json-mib', type=bounded_number(1, 1024), default=32, help='현재 청크·인덱스 하나당 JSON 읽기 한도 MiB')
    audit.add_argument('--progress-interval', type=refresh_interval, default=5, help='진행 상황 stderr 출력 간격(초)')
    show = commands.add_parser('db-show', help='DB 내부 JSON/JSONL 내용·크기 미리보기 (읽기 전용)')
    show.add_argument('--file', required=True, help='DB 내부 상대 경로 (예: index.json)')
    show.add_argument('--limit', type=bounded_number(1, 1000), default=3, help='배열·JSONL 레코드 표시 개수')
    show.add_argument('--max-bytes', type=bounded_number(1, 1024 * 1024 * 1024), default=1024 * 1024, help='JSON 읽기 한도 바이트 (기본 1 MiB)')
    prune = commands.add_parser('db-prune-plan', help='현재 DB 정보와 소스·managed SHA-256을 검증해 과거 JSON 삭제 계획 생성')
    prune.add_argument('--plan', help='DB·원본·managed 밖의 새 SQLite 계획 파일')
    prune.add_argument('--count-only', action='store_true', help='JSON 파일 총 개수만 조회. 내용·해시 검사나 삭제·계획 생성 없이 종료 (--plan 생략 가능)')
    prune.add_argument('--server-stopped', action='store_true', help='대상 DB의 내장 서버 확인 및 작업 중지·저장 후 정상 종료 허용')
    prune.add_argument('--server-stop-timeout', type=bounded_number(1, 86400), default=120, help='서버 정상 종료 대기 초 (기본 120)')
    prune.add_argument('--resume', action='store_true', help='삭제 전 동일 계획의 검사를 이어하기')
    prune.add_argument('--under', default='media', help='검사할 media 하위 경로 (DB 상대 경로)')
    prune.add_argument('--max-files', type=bounded_number(1, 1000000000), help='이번 실행에서 새로 검사할 최대 JSON 수')
    prune.add_argument('--max-json-mib', type=bounded_number(1, 1024), default=64)
    prune.add_argument('--progress-interval', type=refresh_interval, default=5)
    apply = commands.add_parser('db-prune-apply', help='다시 검증한 뒤 계획에서 통과한 과거 JSON만 삭제')
    apply.add_argument('--plan', required=True)
    apply.add_argument('--confirm', required=True, help='계획에 표시된 plan_id로 과거 JSON 영구 삭제 확인')
    apply.add_argument('--server-stopped', action='store_true', help='대상 DB의 내장 서버 확인 및 정상 종료 허용')
    apply.add_argument('--server-stop-timeout', type=bounded_number(1, 86400), default=120, help='서버 정상 종료 대기 초 (기본 120)')
    apply.add_argument('--max-files', type=bounded_number(1, 1000000000), help='이번 실행에서 처리할 최대 후보 수')
    apply.add_argument('--progress-interval', type=refresh_interval, default=5)
    for command in (prune, apply):
        command.add_argument('--memory-budget-mib', type=bounded_number(1, 1048576),
                             help='캐시 예산 상한 MiB. 기본 자동 계산, 큰 값을 지정해도 가용 메모리에 맞춰 제한')
        command.add_argument('--progress-display', choices=['auto', 'pretty', 'plain'], default='auto',
                             help='auto: 터미널 상단 고정 stdout, pretty: 명시적 활성화, plain: 기존 stderr 로그')
        command.add_argument('--progress-log', help='자동 진행 로그 경로 (기본: 계획 폴더/photo-db-prune-DB식별자.progress.log)')
        command.add_argument('--progress-log-files', type=int, choices=[1, 5], default=5,
                             help='1: 현재 상태만 덮어쓰기, 5: 최대 5개 순환 로그 (기본 5)')
        command.add_argument('--progress-log-mib', type=bounded_number(1, 64), default=1,
                             help='순환 로그 한 파일 크기 한도 MiB (기본 1)')
    prune_status = commands.add_parser('db-prune-status', help='SQLite 계획의 통과·보존·삭제 수와 사유 조회')
    prune_status.add_argument('--plan', required=True)
    storage_parser = commands.add_parser('storage-usage', help='DB·원본·관리 폴더 사용량과 파일시스템별 여유 공간 조회')
    storage_parser.add_argument('--refresh', action='store_true', help='전체 폴더를 실제 집계하고 캐시 갱신 (대용량 경로는 시간이 걸릴 수 있음)')
    originals = commands.add_parser('original-paths', help='사진 DB의 원본 파일 경로와 현재 접근 상태 조회')
    originals.add_argument('--media-id', required=True)
    health = commands.add_parser('source-health', help='원본 이동·누락 점검 및 미해결·해결 이력 조회')
    health.add_argument('--check', action='store_true', help='현재 경로를 점검하고 이력에 반영')
    health.add_argument('--watch', action='store_true', help='종료할 때까지 원본 경로를 지속 점검')
    health.add_argument('--interval', type=refresh_interval, default=5, help='감시 간격, 초 (기본 5)')
    health.add_argument('--log-interval', type=refresh_interval, default=60, help='미해결 문제 반복 기록 간격, 초 (기본 60)')
    health.add_argument('--resolved', action='store_true', help='해결·참조 종료 이력 조회')
    health.add_argument('--offset', type=int, default=0)
    find_path = commands.add_parser('source-path-find', help='문제 파일과 SHA-256이 같은 파일을 소스 안에서 검색')
    find_path.add_argument('--issue-id', required=True)
    repair_path = commands.add_parser('source-path-repair', help='크기·SHA-256을 검증한 새 원본 경로를 DB에 반영')
    repair_path.add_argument('--issue-id', required=True)
    repair_path.add_argument('--path', required=True)
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
    merge_status_parser = commands.add_parser('merge-status', help='최신 병합 상태·진행률·현재 파일 조회 (서버 없이 가능)')
    merge_status_parser.add_argument('--merge-id', help='특정 병합 ID 조회 (기본 최신 기록)')
    merge_status_parser.add_argument('--watch', action='store_true', help='Ctrl+C까지 주기적으로 갱신')
    merge_status_parser.add_argument('--interval', type=refresh_interval, default=2, help='갱신 간격, 초 단위 (기본 2)')
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
    merge.add_argument('--source-id', help='이 소스의 활성 미디어만 병합 (생략 시 전체 소스)')
    args = parser.parse_args(argv)
    if args.command == 'db-prune-plan' and not args.plan and (not args.count_only or args.resume):
        parser.error('계획 생성 또는 --resume에는 --plan이 필요합니다.')
    with version_logging(info, args.version_log_interval):
        if args.command in {'db-prune-plan', 'db-prune-apply', 'db-prune-status'}:
            import sqlite3
            from db_prune import plan_prune, apply_prune, prune_status, count_prune_json
            from prune_memory import MemoryBudgetError
            try:
                if args.command == 'db-prune-status':
                    result = prune_status(args.plan)
                    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
                else:
                    from prune_progress import PruneProgress
                    from prune_terminal import PruneTerminal
                    count_only = args.command == 'db-prune-plan' and args.count_only
                    operation = 'db-prune-count' if count_only else args.command
                    log_anchor = args.plan or str(Path(args.db).expanduser().resolve().parent / 'photo-db-prune-count.sqlite')
                    with PruneTerminal(args.progress_display) as terminal:
                        with PruneProgress(args.db, log_anchor, operation, args.progress_interval,
                                           args.progress_log, args.progress_log_files, args.progress_log_mib * 1024 * 1024,
                                           terminal=terminal) as monitor:
                            if count_only:
                                result = count_prune_json(args.db, args.under, args.plan, args.resume, args.max_files, monitor)
                            elif args.command == 'db-prune-plan':
                                result = plan_prune(args.db, args.plan, args.server_stopped, args.resume,
                                                    args.max_json_mib * 1024 * 1024, args.max_files, args.under, monitor,
                                                    stop_timeout=args.server_stop_timeout, memory_budget_mib=args.memory_budget_mib)
                            else:
                                result = apply_prune(args.db, args.plan, args.confirm, args.server_stopped, args.max_files, monitor,
                                                     stop_timeout=args.server_stop_timeout, memory_budget_mib=args.memory_budget_mib)
                            monitor.finish(result['status'])
                        result['progress_log'] = str(monitor.path)
                        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
                return 2 if result['status'] in {'partial', 'partial_apply'} else 0
            except KeyboardInterrupt:
                print('검사를 중단했습니다. 계획 상태를 확인하고 이어서 실행하세요.', file=sys.stderr)
                return 130
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, MemoryBudgetError, MemoryError) as exc:
                print('오류: ' + str(exc), file=sys.stderr)
                return 1
        if args.command in {'db-audit', 'db-show'}:
            # Do not construct Library or StorageUsage: inspection must not migrate,
            # create locks/caches, or launch a second traversal of a huge DB.
            try:
                from db_audit import DBAudit, human_bytes, inspect_json, table
                if args.command == 'db-show':
                    result = inspect_json(args.db, args.file, args.limit, args.max_bytes)
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    return 0
                last_progress = [0.0]
                def progress(phase, count, value):
                    clock = time.monotonic()
                    if clock - last_progress[0] >= args.progress_interval:
                        message = f'현재 청크 내용 {count:,}/{value:,}개 확인' if phase == 'contents' else f'파일 {count:,}개 · {human_bytes(value)} 집계 (전체 수는 완료 후 확정)'
                        print(message, file=sys.stderr, flush=True)
                        last_progress[0] = clock
                report = DBAudit(args.db, args.max_json_mib * 1024 * 1024).scan(
                    top=args.top, with_contents=not args.sizes_only, max_files=args.max_files, progress=progress)
                print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == 'json' else table(report), flush=True)
                return 130 if report['interrupted'] else 0 if report['complete'] else 2
            except (OSError, ValueError, TypeError, KeyError) as exc:
                print('오류: ' + str(exc), file=sys.stderr)
                return 1
        from storage_usage import StorageUsage
        storage = StorageUsage(args.db, args.root, persist=args.command == 'storage-usage' and args.refresh)
        try:
            with storage.running():
                uncached = not storage.value.get('checked_at') or storage.value.get('roots') != storage.layout()
                if uncached and (storage.db / 'config.json').is_file() and args.command != 'storage-usage':
                    storage.snapshot()
                    storage.worker.join(timeout=.5)
                    if storage.worker.is_alive(): storage.announce = sys.stderr
                storage.startup()
                return run_command(args, parser, storage)
        except (OSError, ValueError, TypeError) as exc:
            print('오류: ' + str(exc), file=sys.stderr)
            return 1


def run_command(args, parser, storage=None):
    if args.command == 'merge' and args.resume and args.media_id:
        parser.error('--resume과 --media-id는 함께 사용할 수 없습니다.')
    try:
        if storage is None:
            from storage_usage import StorageUsage
            storage = StorageUsage(args.db, args.root)
        if args.command == 'storage-usage':
            result = storage.measure() if args.refresh else storage.current()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == 'backup-check':
            from backup import verify_backup
            print(json.dumps(verify_backup(args.backup), ensure_ascii=False, indent=2))
            return 0
        if args.command == 'restore':
            from backup import restore_backup
            print(json.dumps(restore_backup(args.backup, args.destination), ensure_ascii=False, indent=2))
            return 0
        db = Path(args.db).expanduser().resolve()
        if args.command == 'merge-status':
            from merge_status import merge_status
            while True:
                print(json.dumps(merge_status(db, args.merge_id), ensure_ascii=False, indent=2), flush=True)
                if not args.watch:
                    return 0
                time.sleep(args.interval)
        if not (db / 'config.json').is_file():
            raise ValueError(f'설정 DB가 없습니다: {db}. 서버에서 설정한 DB 경로를 지정하세요.')
        library = Library(db, Path(args.root).expanduser())
        if args.command in {'original-paths', 'source-health', 'source-path-find', 'source-path-repair'}:
            from source_health import SourceHealth
            monitor = SourceHealth(library, stream=sys.stderr)
            if args.command == 'original-paths':
                result = monitor.origins(args.media_id)
            elif args.command == 'source-path-find':
                result = monitor.find(args.issue_id)
            elif args.command == 'source-path-repair':
                result = monitor.repair(args.issue_id, args.path)
            else:
                with monitor.runtime_lock:
                    monitor.runtime.update(monitoring=bool(args.watch), interval=args.interval)
                while True:
                    if args.check or args.watch: monitor.check(args.log_interval)
                    result = {'summary': monitor.summary(), **monitor.page('resolved' if args.resolved else 'open', args.offset)}
                    if not args.watch: break
                    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
                    time.sleep(args.interval)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
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
        elif args.command == 'pair-history':
            result = library.pair_history()
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
                result = library.merge(ids=args.media_id, preview=args.preview, stopped=stop.is_set, resume=args.resume, source_id=args.source_id)
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
