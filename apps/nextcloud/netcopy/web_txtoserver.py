#!/usr/bin/env python3
"""Web UI for txtoserver. Run: python3 web_txtoserver.py --port 8080."""
from __future__ import annotations

import argparse
import configparser
import datetime as dt
import hashlib
import json
import math
import re
import base64
import html
import os
import posixpath
import secrets
import threading
import tempfile
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, quote

import txtoserver as transfer

FIELDS = ('webdav_hostname', 'webdav_root', 'port', 'username', 'password', 'root')
ACTIVE = {'checking', 'running', 'pausing'}


def parse_config(data):
    config = configparser.ConfigParser(interpolation=None)
    for name in ('source', 'destination'):
        values = data.get(name, {})
        config[name] = {key: str(values.get(key, '')).strip() if key != 'password'
                        else str(values.get(key, '')) for key in FIELDS}
        section = config[name]
        url = urlsplit(section['webdav_hostname'])
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
            raise ValueError(f'{name}: 올바른 http/https 서버 URL을 입력하세요.')
        if not section['username'] or not section['password']:
            raise ValueError(f'{name}: 사용자 이름과 비밀번호가 필요합니다.')
        if section['port'] and not 1 <= int(section['port']) <= 65535:
            raise ValueError('포트는 1~65535 사이여야 합니다.')
        for key in ('root', 'webdav_root'):
            if any(part in ('.', '..') for part in section[key].split('/')):
                raise ValueError('디렉토리에는 . 또는 ..를 사용할 수 없습니다.')
    limit = float(data.get('speed_limit_mbps', 0) or 0)
    if not math.isfinite(limit) or limit < 0:
        raise ValueError('전송 속도 제한은 0 이상의 숫자여야 합니다.')
    config['settings'] = {'speed_limit_mbps': str(limit), 'verify_ssl': 'true' if data.get('verify_ssl', True) else 'false'}
    if all(config['source'][k] == config['destination'][k]
           for k in ('webdav_hostname', 'webdav_root', 'port', 'root', 'username')):
        raise ValueError('source와 destination이 동일합니다.')
    return config


def identity(config):
    # Password changes must not discard previously verified transfers.
    values = {name: {k: config[name][k] for k in FIELDS if k != 'password'}
              for name in ('source', 'destination')}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


class ConfigHistory:
    """Last 100 submitted settings; passwords are replaced by a fixed mask."""
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.entries = []
        if self.path.exists():
            entries = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(entries, list):
                raise ValueError('설정 히스토리 파일은 JSON 배열이어야 합니다.')
            # Re-sanitize loaded entries as well, including files edited externally.
            self.entries = [dict(self.sanitize(item), saved_at=str(item.get('saved_at', '')))
                            for item in entries[:100]]

    @staticmethod
    def sanitize(data):
        result = {'verify_ssl': bool(data.get('verify_ssl', True)),
                  'speed_limit_mbps': str(data.get('speed_limit_mbps', 0))}
        for name in ('source', 'destination'):
            section = data.get(name, {})
            result[name] = {key: str(section.get(key, '')) for key in FIELDS if key != 'password'}
            result[name]['password'] = '********' if section.get('password') else ''
        return result

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.entries))

    def add(self, config):
        data = {name: dict(config[name]) for name in ('source', 'destination')}
        data['speed_limit_mbps'] = config.get('settings', 'speed_limit_mbps', fallback='0')
        data['verify_ssl'] = config.getboolean('settings', 'verify_ssl')
        entry = dict(self.sanitize(data), saved_at=dt.datetime.now().astimezone().isoformat(timespec='seconds'))
        with self.lock:
            entries = [entry, *self.entries][:100]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=self.path.name + '.', dir=self.path.parent)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(entries, stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            self.entries = entries


class Manager:
    def __init__(self, state_file, history_file=None, failed_file=None):
        self.lock = threading.RLock()
        self.state_file = Path(state_file)
        self.history = ConfigHistory(history_file or self.state_file.with_suffix('.history.json'))
        self.failed_file = Path(failed_file or self.state_file.with_suffix('.failed.txt'))
        self.failure_records = {}
        if self.failed_file.exists():
            for line in self.failed_file.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    record = json.loads(line)
                    self.failure_records[(record['key'], record['source'])] = record
        self.active_plan = None
        self.pause = threading.Event()
        self.logs = deque(maxlen=150)
        self.status = 'idle'
        self.error = ''
        self.plan = []
        self.config = None
        self.key = None
        self.current = ''
        self.done = {}
        self.failed = {}
        self.skipped = 0
        self.worker = None
        self.saved = {}
        if self.state_file.exists():
            self.saved = json.loads(self.state_file.read_text(encoding='utf-8'))
            self.status = 'paused'
            self.log('저장된 체크포인트가 있습니다. 같은 설정으로 실행 전 확인을 하세요.')

    def log(self, message):
        with self.lock:
            self.logs.append(time.strftime('%H:%M:%S') + ' ' + message)

    def snapshot(self):
        with self.lock:
            plan = self.active_plan if self.active_plan is not None else self.plan
            total = len(plan)
            completed = sum(item['id'] in self.done for item in plan)
            return dict(status=self.status, error=self.error, current=self.current,
                        total_files=total, completed_files=completed,
                        total_bytes=sum(item['size'] for item in plan),
                        completed_bytes=sum(item['size'] for item in plan if item['id'] in self.done),
                        percent=round(completed * 100 / total, 1) if total else (100 if self.status == 'completed' else 0),
                        skipped=self.skipped, failed=len(self.failed),
                        previous_failed=sum(key == self.key for key, path in self.failure_records),
                        logs=list(self.logs))

    def save_failures(self):
        """UTF-8 TXT, one JSON object per line with sanitized diagnostic details."""
        self.failed_file.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=self.failed_file.name + '.', dir=self.failed_file.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                for record in self.failure_records.values():
                    stream.write(json.dumps(record, ensure_ascii=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.failed_file)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def redact(self, value):
        text = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else str(value)
        if self.config is not None:
            for name in ('source', 'destination'):
                password = self.config[name].get('password', '')
                if password:
                    credentials = self.config[name].get('username', '') + ':' + password
                    for secret in (password, quote(password, safe=''), html.escape(password),
                                   base64.b64encode(credentials.encode()).decode()):
                        text = text.replace(secret, '[REDACTED]')
        text = re.sub(r'(?i)(https?://)[^/\s@]+@', r'\1[REDACTED]@', text)
        text = re.sub(r'(?i)(authorization\s*[:=]\s*)(?:basic|bearer)\s+[^\s<]+',
                      r'\1[REDACTED]', text)
        text = re.sub(r'(?i)((?:password|token|secret|api_key)=[^&\s]*)', '[REDACTED]', text)
        return text[:8192]

    def record_failure(self, item, exc, stage=None):
        original = getattr(exc, 'original', exc)
        details = dict(getattr(exc, 'http_error', {}) or {})
        response = getattr(original, 'response', None)
        status = details.get('http_status', getattr(original, 'code', None))
        body = details.get('server_response', getattr(original, 'message', ''))
        if response is not None:
            status = response.status_code
            body = response.content
        body = body if body is not None else ''
        stage = stage or getattr(exc, 'stage', 'unknown')
        with self.lock:
            self.failed[item['id']] = True
            self.failure_records[(self.key, item['source'])] = dict(
                item, key=self.key, failed_at=dt.datetime.now().astimezone().isoformat(timespec='seconds'),
                reason='전송 또는 SHA-256 검증 실패', stage=stage,
                exception_type=type(original).__name__, exception_message=self.redact(str(original)),
                http_status=status, server_response=self.redact(body),
                server_response_truncated=bool(details.get('server_response_truncated')) or len(body) > 8192)
            self.save_failures()
        self.log(f"실패 단계={stage}, HTTP={status if status is not None else '-'}, "
                 f"{type(original).__name__}: {self.redact(str(original))[:500]}")

    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump({'key': self.key, 'done': self.done}, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.state_file)
        self.saved = {'key': self.key, 'done': dict(self.done)}

    def check(self, data):
        config = parse_config(data)
        with self.lock:
            if self.status in ACTIVE or (self.worker and self.worker.is_alive()):
                raise ValueError('현재 작업이 끝난 뒤 다시 확인하세요.')
            self.history.add(config)
            self.config = config
            self.key = identity(config)
            self.status, self.error, self.current = 'checking', '', ''
            self.plan, self.failed, self.skipped = [], {}, 0
            self.active_plan = None
            self.done = dict(self.saved.get('done', {})) if self.saved.get('key') == self.key else {}
            self.worker = threading.Thread(target=self._check, daemon=True)
            self.worker.start()

    def clients(self):
        verify = self.config.getboolean('settings', 'verify_ssl')
        rate = self.config.getfloat('settings', 'speed_limit_mbps', fallback=0) * 1024 * 1024
        return (transfer.build_client(self.config['source'], verify, rate),
                transfer.build_client(self.config['destination'], verify, rate))

    def _check(self):
        try:
            source, dest = self.clients()
            sr = transfer.normalize_root(self.config['source']['root'])
            dr = transfer.normalize_root(self.config['destination']['root'])
            self.log('Source 연결 확인 및 파일 목록 조회 중...')
            entries = transfer.list_tree(source, sr)
            smap = transfer.build_info_map(entries)
            self.log('Destination 연결 확인 및 파일 목록 조회 중...')
            # Read-only preview: do not create destination directories here.
            parent = dr
            while parent and not dest.check(parent):
                parent = posixpath.dirname(parent)
            dest.list(parent, get_info=True)
            dmap = transfer.build_info_map(transfer.list_tree(dest, dr)) if not dr or dest.check(dr) else {}
            plan, skipped = [], 0
            for entry in entries:
                sp = entry['path']
                rel = transfer.relative_from_root(sp, sr)
                if rel is None:
                    continue
                dp = posixpath.join(dr, rel) if dr else rel
                info = smap[transfer.normalize_remote_path(sp)]
                signature = hashlib.sha256(json.dumps([sp, info[0], info[1], str(info[2])]).encode()).hexdigest()
                if signature in self.done and (dp not in dmap or dmap[dp][0] != self.done[signature]):
                    del self.done[signature]
                previously_failed = (self.key, sp) in self.failure_records
                if previously_failed:
                    self.done.pop(signature, None)
                if previously_failed or signature in self.done or transfer.should_upload(info, dmap.get(dp)):
                    plan.append(dict(id=signature, source=sp, destination=dp, size=transfer.get_entry_size(entry)))
                else:
                    skipped += 1
                    transfer.append_skip_log(str(transfer.DEFAULT_SKIP_LOG),
                                             transfer.compose_remote_url(self.config['source'], sp),
                                             transfer.compose_remote_url(self.config['destination'], dp))
            with self.lock:
                self.plan, self.skipped, self.status = plan, skipped, 'ready'
            self.log(f'확인 완료: 대상 {len(plan)}개, 기존 파일 건너뛰기 {skipped}개. 실행 버튼을 누르세요.')
        except Exception:
            self.fail('연결 또는 목록 조회 실패. URL, 디렉토리, 인증 정보와 SSL 설정을 확인하세요.')

    def fail(self, message):
        with self.lock:
            self.status, self.error, self.current = 'error', message, ''
        self.log(message)

    def start(self, failed_only=False):
        with self.lock:
            if self.status not in ('ready', 'paused', 'error') or self.config is None:
                raise ValueError('먼저 실행 전 확인을 완료하세요.')
            if self.worker and self.worker.is_alive():
                raise ValueError('현재 작업이 끝날 때까지 기다려 주세요.')
            if self.status == 'error' and not self.plan:
                raise ValueError('실행 전 확인을 다시 진행하세요.')
            if failed_only:
                selected = [item for item in self.plan
                            if (self.key, item['source']) in self.failure_records]
                if not selected:
                    raise ValueError('현재 설정과 원본 목록에 일치하는 실패 파일이 없습니다. 실행 전 확인을 다시 진행하세요.')
                self.active_plan = selected
                for item in selected:
                    self.done.pop(item['id'], None)
                self.log(f'이전 실패 리스트 복사: {len(selected)}개 재전송')
            elif self.active_plan is None:
                self.active_plan = self.plan
            self.pause.clear()
            self.status, self.error, self.failed = 'running', '', {}
            self.worker = threading.Thread(target=self._run, daemon=True)
            self.worker.start()

    def request_pause(self):
        with self.lock:
            if self.status != 'running':
                raise ValueError('전송 중에만 일시 중단할 수 있습니다.')
            self.pause.set()
            self.status = 'pausing'
        self.log('일시 중단 요청: 현재 파일 검증 완료 후 중단합니다.')

    def _run(self):
        try:
            source, dest = self.clients()
            dest_root = transfer.normalize_root(self.config['destination']['root'])
            self.log('Destination 디렉토리 확인 및 생성: ' + (dest_root or '/'))
            try:
                dest.last_http_error = None
                transfer.ensure_dirs(dest, dest_root)
            except Exception as exc:
                for item in self.active_plan:
                    if item['id'] not in self.done:
                        self.record_failure(item, transfer.TransferFailure(
                            'destination_directory', exc, getattr(dest, 'last_http_error', None)))
                raise
            for item in self.active_plan:
                if self.pause.is_set():
                    break
                if item['id'] in self.done:
                    continue
                with self.lock:
                    self.current = item['source']
                self.log('전송 및 SHA-256 검증: ' + item['source'])
                try:
                    size = transfer.upload_and_verify_file(source, dest, item['source'], item['destination'])
                except Exception as exc:
                    self.record_failure(item, exc)
                    self.log('전송/검증 실패: ' + item['source'] + ' (다시 시작 시 재시도)')
                    continue
                with self.lock:
                    self.done[item['id']] = size
                    self.save()
                    if self.failure_records.pop((self.key, item['source']), None) is not None:
                        self.save_failures()
                self.log('검증 완료: ' + item['source'])
            with self.lock:
                self.current = ''
                self.status = 'paused' if self.pause.is_set() else ('error' if self.failed else 'completed')
                self.error = '실패한 파일이 있습니다. 다시 시작하면 재시도합니다.' if self.failed else ''
                self.save()
            self.log({'paused': '일시 중단 완료', 'completed': '전체 전송 완료', 'error': '일부 전송 실패'}[self.status])
        except Exception:
            self.fail('작업 실패: 연결 또는 체크포인트 저장 경로를 확인하세요. 다시 시작할 수 있습니다.')


PAGE = r'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nextcloud 서버 전송</title><style>
body{font:16px system-ui;background:#f2f5f9;color:#203047;max-width:1050px;margin:30px auto;padding:0 20px}section{background:white;padding:22px;border-radius:12px;margin:18px 0}.columns{display:grid;grid-template-columns:1fr 1fr;gap:20px}label{display:block;margin:10px 0}input:not([type=checkbox]){display:block;box-sizing:border-box;width:100%;padding:9px;border:1px solid #bac6d5;border-radius:5px}button{padding:11px 16px;margin:6px;border:0;border-radius:6px;background:#2458aa;color:white;cursor:pointer}button:disabled{opacity:.4;cursor:default}progress{width:100%;height:25px}pre{background:#15243a;color:#d9e6f8;padding:15px;max-height:320px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}#error{color:#bd2937}@media(max-width:650px){.columns{grid-template-columns:1fr}}
</style><h1>Nextcloud 서버 전송</h1><p>증분 복사 · 중복 확인 · SHA-256 검증 · 체크포인트 재개</p>
<section><label>설정 히스토리 (최근 100개)<select id="history"><option value="">이전 설정 선택</option></select></label><p>실행 전 확인을 누르면 설정을 저장합니다. 암호는 마스킹하여 저장하므로 불러온 후 다시 입력하세요.</p><form id="config"><div class="columns" id="fields"></div><label><input id="verify_ssl" type="checkbox" checked> SSL 인증서 검증</label><label>전송 속도 제한 (MiB/s, 0 = 무제한)<input id="speed_limit_mbps" type="number" min="0" step="any" value="0"></label><p>Source 다운로드, Destination 업로드 및 검증 다운로드 각각에 적용됩니다.</p></form>
<button id="check">실행 전 확인</button><button id="start" disabled>실행 / 이어서 시작</button><button id="retry_failed" disabled>이전 실패 리스트 복사</button><button id="pause" disabled>일시 중단</button><p>일시 중단은 현재 파일의 전송 및 검증이 끝난 뒤 적용됩니다. 재실행 시 같은 설정으로 확인하면 완료한 파일을 이어받습니다.</p></section>
<section><strong id="status">대기</strong><p id="summary"></p><progress id="progress" max="100" value="0"></progress><p id="current"></p><p id="error" role="alert"></p><pre id="logs" aria-live="polite"></pre></section>
<script>
let token='',busy=false,dirty=true,history=[];const $=id=>document.getElementById(id);
const labels={webdav_hostname:'서버 URL (https://cloud.example.com)',webdav_root:'WebDAV 경로 (/remote.php/dav/files/user/)',port:'서버 포트 (빈칸: HTTP 80 / HTTPS 443)',username:'사용자 이름',password:'비밀번호 / 앱 비밀번호',root:'디렉토리 (Photos 등)'};
for(const name of ['source','destination']){const box=document.createElement('div');const title=document.createElement('h2');title.textContent=name==='source'?'Source · 원본':'Destination · 대상';box.append(title);for(const [key,label] of Object.entries(labels)){const l=document.createElement('label');l.textContent=label;const i=document.createElement('input');i.id=name+'_'+key;i.type=key==='password'?'password':'text';i.autocomplete=key==='password'?'new-password':'off';l.append(i);box.append(l)}$('fields').append(box)}
function data(){const d={verify_ssl:$('verify_ssl').checked,speed_limit_mbps:$('speed_limit_mbps').value};for(const n of ['source','destination']){d[n]={};for(const k of Object.keys(labels))d[n][k]=$(n+'_'+k).value}return d}
async function action(name){if(busy)return;busy=true;try{const r=await fetch('/api/'+name,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':token},body:JSON.stringify(name==='check'?data():{})});const d=await r.json();if(!r.ok)throw Error(d.error);if(name==='check'){dirty=false;await loadHistory()}await poll()}catch(e){$('error').textContent=e.message}finally{busy=false}}
$('check').onclick=()=>action('check');$('start').onclick=()=>action('start');$('pause').onclick=()=>action('pause');$('retry_failed').onclick=()=>action('retry_failed');$('config').onsubmit=e=>e.preventDefault();$('config').oninput=()=>{dirty=true;$('start').disabled=true;$('retry_failed').disabled=true};
const names={idle:'대기',checking:'연결 / 대상 확인 중',ready:'확인 완료',running:'전송 중',pausing:'중단 대기',paused:'일시 중단',completed:'완료',error:'오류'};
const bytes=n=>{let u=0;while(n>=1024&&u<4){n/=1024;u++}return n.toFixed(u?2:0)+' '+['B','KB','MB','GB','TB'][u]};
async function poll(){try{const r=await fetch('/api/status');if(!r.ok)throw Error('상태 조회 실패');const d=await r.json();$('status').textContent=names[d.status];$('progress').value=d.percent;$('summary').textContent=`${d.percent}% · 파일 ${d.completed_files}/${d.total_files} · 용량 ${bytes(d.completed_bytes)}/${bytes(d.total_bytes)} · 건너뛰기 ${d.skipped} · 실패 ${d.failed} · 저장된 실패 ${d.previous_failed}`;$('current').textContent=d.current;$('error').textContent=d.error;$('logs').textContent=d.logs.join('\n');$('logs').scrollTop=$('logs').scrollHeight;const active=['checking','running','pausing'].includes(d.status);$('check').disabled=active;$('history').disabled=active;for(const i of $('config').elements)i.disabled=active;$('start').disabled=dirty||!['ready','paused','error'].includes(d.status);$('retry_failed').disabled=dirty||!['ready','paused','error'].includes(d.status)||!d.previous_failed;$('pause').disabled=d.status!=='running'}catch(e){$('error').textContent='웹 서버 연결 실패: '+e.message}}
function applyConfig(d){for(const n of ['source','destination'])for(const k of Object.keys(labels))$(n+'_'+k).value=k==='password'?'':(d[n]?.[k]||'');$('speed_limit_mbps').value=d.speed_limit_mbps||0;$('verify_ssl').checked=d.verify_ssl;dirty=true;$('start').disabled=true;$('retry_failed').disabled=true}
async function loadHistory(){const r=await fetch('/api/history');if(!r.ok)throw Error('히스토리 조회 실패');history=await r.json();$('history').replaceChildren(new Option('이전 설정 선택',''));history.forEach((d,index)=>{const label=`${d.saved_at} · ${d.source.webdav_hostname}/${d.source.root} → ${d.destination.webdav_hostname}/${d.destination.root}`;$('history').append(new Option(label,String(index)))})}
$('history').onchange=()=>{if($('history').value!=='')applyConfig(history[Number($('history').value)])};
async function init(){const r=await fetch('/api/config');const d=await r.json();token=d.token;for(const n of ['source','destination'])for(const k of Object.keys(labels))$(n+'_'+k).value=d[n]?.[k]||'';$('speed_limit_mbps').value=d.speed_limit_mbps||0;$('verify_ssl').checked=d.verify_ssl;await loadHistory();if(history.length)applyConfig(history[0]);await poll();setInterval(poll,1000)}init();
</script></html>'''


def handler_for(manager, defaults, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, code, data, html=False):
            body = (data if html else json.dumps(data, ensure_ascii=False)).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            self.wfile.write(body)

        def allowed_host(self):
            host = self.headers.get('Host', '')
            return host in self.server.allowed_hosts

        def do_GET(self):
            if not self.allowed_host():
                return self.respond(403, {'error': '허용되지 않은 Host'})
            if self.path == '/':
                self.respond(200, PAGE, True)
            elif self.path == '/api/status':
                self.respond(200, manager.snapshot())
            elif self.path == '/api/history':
                self.respond(200, manager.history.snapshot())
            elif self.path == '/api/config':
                self.respond(200, dict(defaults, token=token))
            else:
                self.respond(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.allowed_host() or not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), token):
                return self.respond(403, {'error': '요청 인증 실패'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 65536:
                    raise ValueError('잘못된 요청 크기')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('설정 객체가 필요합니다.')
                if self.path == '/api/check':
                    manager.check(data)
                elif self.path == '/api/start':
                    manager.start()
                elif self.path == '/api/retry_failed':
                    manager.start(failed_only=True)
                elif self.path == '/api/pause':
                    manager.request_pause()
                else:
                    return self.respond(404, {'error': 'Not found'})
                self.respond(200, manager.snapshot())
            except OSError:
                self.respond(500, {'error': '설정 또는 실패 목록 저장 실패: 파일 경로와 쓰기 권한을 확인하세요.'})
            except (ValueError, KeyError, TypeError) as exc:
                self.respond(400, {'error': str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--config', type=Path, default=transfer.DEFAULT_CONFIG)
    parser.add_argument('--state-file', type=Path, default=transfer.SCRIPT_DIR / 'web_txtoserver.state.json')
    parser.add_argument('--history-file', type=Path, default=transfer.SCRIPT_DIR / 'web_txtoserver.history.json')
    parser.add_argument('--failed-file', type=Path, default=transfer.SCRIPT_DIR / 'web_txtoserver.failed.txt')
    parser.add_argument('--allow-host', action='append', default=[], help='Additional Host header, including port')
    args = parser.parse_args()
    defaults = {'source': {}, 'destination': {}, 'verify_ssl': True, 'speed_limit_mbps': '0'}
    if args.config.exists():
        config = transfer.load_config(str(args.config))
        for name in ('source', 'destination'):
            if config.has_section(name):
                defaults[name] = {k: config[name].get(k, '') for k in FIELDS if k != 'password'}
        defaults['speed_limit_mbps'] = config.get('settings', 'speed_limit_mbps', fallback='0')
        defaults['verify_ssl'] = config.getboolean('settings', 'verify_ssl', fallback=True)
    manager = Manager(args.state_file, args.history_file, args.failed_file)
    server = ThreadingHTTPServer((args.host, args.port), handler_for(manager, defaults, secrets.token_urlsafe(32)))
    port = server.server_address[1]
    server.allowed_hosts = {f'{args.host}:{port}', f'localhost:{port}', f'127.0.0.1:{port}', *args.allow_host}
    print(f'웹페이지: http://{args.host}:{port}')
    if args.host not in ('localhost', '127.0.0.1', '::1'):
        print('외부 접속에는 인증/TLS를 제공하는 리버스 프록시를 사용하세요.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        manager.pause.set()
        if manager.worker and manager.worker.is_alive():
            print('현재 파일 처리 및 체크포인트 저장을 기다리는 중...')
            manager.worker.join()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
