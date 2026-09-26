"""Read-only WebDAV inventory and PulseDAV recording checks."""
from __future__ import annotations

import json
import posixpath
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET

from pulsedav import APP_DIR, build_session, build_webdav_config, build_host_remote_dirs, compose_webdav_url, load_settings, propfind

DEFAULT_OUTPUT = APP_DIR.parents[3] / 'workshot/2remember/server_list'
NS = {'d': 'DAV:'}


def cron_configs(text, home):
    """Parse common cd + sender.py cron commands without executing shell text."""
    paths = set()
    unresolved = False
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if 'sender.py' not in line and 'pulsedav.py' not in line:
            continue
        try:
            tokens = shlex.split(line)
            if any(flag in tokens for flag in ('--gateway-watchdog', '--check-status', '--check-status-all', '--print-crontab', '--install-crontab')):
                continue
            cwd = Path(home)
            if 'cd' in tokens:
                cwd = Path(tokens[tokens.index('cd') + 1]).expanduser()
                if not cwd.is_absolute():
                    cwd = Path(home) / cwd
            scripts = [t for t in tokens if Path(t).name in ('sender.py', 'pulsedav.py')]
            if not scripts:
                continue
            script = Path(scripts[0])
            if not script.is_absolute():
                script = cwd / script
            if 'pulsedav' not in str(script):
                continue
            value = next((t.split('=', 1)[1] for t in tokens if t.startswith('--config=')), None)
            if '--config' in tokens:
                value = tokens[tokens.index('--config') + 1]
            path = Path(value).expanduser() if value else script.parent / 'settings.json'
            if not path.is_absolute():
                path = cwd / path
            if any(c in str(path) for c in '$`'):
                unresolved = True
            else:
                paths.add(path.resolve())
        except (ValueError, IndexError):
            unresolved = True
    return paths, unresolved


def discover_config(explicit=None):
    paths = set()
    notes = []
    for label, command, home in [('user', ['crontab', '-l'], Path.home()),
                                  ('root', ['sudo', '-n', 'crontab', '-l'], Path('/var/root') if sys.platform == 'darwin' else Path('/root'))]:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            if result.returncode:
                notes.append(f'{label} crontab: unavailable or absent')
                continue
            found, unresolved = cron_configs(result.stdout, home)
            paths.update(found)
            notes.append(f'{label} crontab: {len(found)} PulseDAV config(s)')
            if unresolved:
                notes.append(f'{label} crontab: unresolved config; use --config')
        except (OSError, subprocess.TimeoutExpired):
            notes.append(f'{label} crontab: unavailable')
    if explicit:
        return Path(explicit).expanduser().resolve(), notes
    if len(paths) != 1:
        raise ValueError('cron 설정을 하나로 결정할 수 없습니다. --config /path/to/settings.json을 지정하세요. ' + '; '.join(notes))
    return paths.pop(), notes


def iso_time(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    return dt.replace(tzinfo=dt.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()


def list_directory(session, config, directory):
    root = propfind(session, compose_webdav_url(config, directory), '1')
    if root.tag != '{DAV:}multistatus':
        raise ValueError('Expected DAV multistatus')
    base = unquote(urlparse(compose_webdav_url(config)).path).rstrip('/')
    entries = []
    for response in root.findall('d:response', NS):
        href = response.findtext('d:href', '', NS)
        path = unquote(urlparse(href).path).rstrip('/')
        if not path.startswith(base + '/'):
            raise ValueError('Unexpected DAV path')
        relative = path[len(base):].strip('/')
        if relative != directory and (posixpath.dirname(relative) != directory or '..' in relative.split('/')):
            raise ValueError('Unexpected DAV child path')
        props = {}
        for stat in response.findall('d:propstat', NS):
            if re.search(r'\s200(?:\s|$)', stat.findtext('d:status', '', NS)):
                prop = stat.find('d:prop', NS)
                if prop is not None:
                    props.update({child.tag: child for child in prop})
        resource = props.get('{DAV:}resourcetype')
        if relative == directory:
            if resource is None:
                raise ValueError('Missing DAV collection properties')
            continue
        if resource is None:
            entries.append({'path': relative, 'error': 'missing_resource_type'})
            continue
        modified = props.get('{DAV:}getlastmodified')
        entries.append({'path': relative, 'is_directory': resource.find('d:collection', NS) is not None,
                        'modified_at': iso_time(modified.text if modified is not None else None)})
    return entries


def safe_error(exc):
    """Expose failure categories, never raw HTTP bodies, URLs or credentials."""
    code = getattr(getattr(exc, 'response', None), 'status_code', None)
    if code is None:
        match = re.search(r'HTTP(?: Error)? (\d{3})', str(exc))
        code = int(match.group(1)) if match else None
    if code:
        return f'HTTP {code}'
    message = str(exc).lower()
    for token, label in [('connection refused', 'connection_refused'), ('timed out', 'timeout'),
                         ('certificate', 'tls_certificate_error'), ('name or service', 'dns_error'),
                         ('nodename', 'dns_error')]:
        if token in message:
            return label
    return type(exc).__name__


def scan(session, config, target):
    pending, seen, files, directories, errors = [target], set(), [], [], []
    while pending:
        directory = pending.pop()
        if directory in seen:
            continue
        seen.add(directory)
        directories.append(directory)
        try:
            entries = list_directory(session, config, directory)
        except Exception as exc:
            errors.append({'directory': directory, 'error': safe_error(exc)})
            continue
        for entry in entries:
            if entry.get('error'):
                errors.append({'directory': directory, 'file': entry['path'], 'error': entry['error']})
            elif entry['is_directory']:
                pending.append(entry['path'])
            else:
                files.append(entry)
                if not entry['modified_at']:
                    errors.append({'directory': directory, 'file': entry['path'], 'error': 'missing_modified_time'})
    return sorted(directories), sorted(files, key=lambda f: f['path']), errors


def latest(files):
    return max((f for f in files if f['modified_at']), key=lambda f: f['modified_at'], default=None)


def report_metadata(session, config, entry):
    if not entry:
        return {}
    response = session.request('GET', compose_webdav_url(config, entry['path']), timeout=60)
    response.raise_for_status()
    # Only persist allowlisted header fields; reports can contain private cron commands.
    header = response.text.split('\n## ', 1)[0]
    fields = {}
    for key, label in [('server_name', '호스트명'), ('ip_address', '내부 IP'), ('public_ip', 'Public IP'), ('open_port', 'SSH 포트')]:
        match = re.search(r'^- ' + re.escape(label) + r':\s*(.+)$', header, re.M)
        if match:
            fields[key] = match.group(1).strip()
    return fields


def render_tree(result):
    lines = [f"/{result['target_directory']} [complete={result['scan_complete']}]", f"checked_at: {result['checked_at']}"]
    lines.append('scope: ' + result.get('scope', 'all'))
    for note in result['cron_notes']:
        lines.append(f'cron: {note}')
    by_dir = {s['directory']: s for s in result['servers']}
    children = {}
    display_directories = set(result['directories'])
    # Include ancestors for display only; local checks never query these parents.
    for directory in result['directories']:
        parent = posixpath.dirname(directory)
        while parent and parent != result['target_directory']:
            display_directories.add(parent)
            parent = posixpath.dirname(parent)
    for directory in sorted(display_directories):
        if directory != result['target_directory']:
            children.setdefault(posixpath.dirname(directory), []).append((directory, True, None))
    for f in result['files']:
        children.setdefault(posixpath.dirname(f['path']), []).append((f['path'], False, f['modified_at']))
    stack = [(result['target_directory'], '', None)]
    while stack:
        parent, prefix, line = stack.pop()
        if line is not None:
            lines.append(line)
        items = sorted(children.get(parent, []))
        for i in range(len(items) - 1, -1, -1):
            path, is_dir, modified = items[i]
            end = i == len(items) - 1
            text = posixpath.basename(path) + ('/' if is_dir else f'  {modified or "unknown"}')
            if path in by_dir:
                s = by_dir[path]
                text += f" [{s['status']}] IP={s['ip_address']} port={s['open_port']} latest={s['latest_modified_at']}"
            stack.append((path, prefix + ('    ' if end else '│   '), prefix + ('└── ' if end else '├── ') + text))
    for server in result['servers']:
        if server['directory'] not in result['directories']:
            lines.append(f"MISSING {server['directory']} [{server['status']}]")
    for error in result['errors']:
        lines.append(f"ERROR {error['directory']}: {error['error']}")
    return '\n'.join(lines) + '\n'


def check_status(config_path=None, output_dir=None, max_age_minutes=None, server_list=None, *, all_nodes=False):
    path, notes = discover_config(config_path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not raw.get('webdav'):
        raise ValueError('유효한 webdav 설정이 필요합니다.')
    settings = load_settings(path)
    config = build_webdav_config(settings)
    if 'example.com' in config.hostname or not config.username or not config.password:
        raise ValueError('예제 설정 대신 실제 WebDAV 설정을 지정하세요.')
    threshold = max_age_minutes if max_age_minutes is not None else int(settings['schedule']['interval_minutes']) * 2
    if threshold <= 0:
        raise ValueError('--max-age-minutes는 양수여야 합니다.')
    inventory = []
    if server_list:
        data = json.loads(Path(server_list).expanduser().read_text(encoding='utf-8'))
        inventory = data.get('servers', []) if isinstance(data, dict) else data
        if not isinstance(inventory, list) or any(not isinstance(row, dict) or not row.get('directory') for row in inventory):
            raise ValueError('server-list는 directory가 포함된 JSON 배열 또는 {"servers": [...]} 형식이어야 합니다.')
        inventory = [{**row, 'directory': str(row['directory']).strip('/')} for row in inventory]
        if any(not row['directory'].startswith('tinyGW/') or '..' in row['directory'].split('/') for row in inventory):
            raise ValueError('server-list directory는 tinyGW/ 이하의 경로여야 합니다.')
    session = build_session(config)
    try:
        local_hosts = set(build_host_remote_dirs(config))
        targets = ['tinyGW'] if all_nodes else sorted(local_hosts)
        directory_set, file_map, errors = set(), {}, []
        for target in targets:
            found_dirs, found_files, found_errors = scan(session, config, target)
            directory_set.update(found_dirs)
            file_map.update((entry['path'], entry) for entry in found_files)
            errors.extend(found_errors)
        directories = sorted(directory_set)
        files = sorted(file_map.values(), key=lambda entry: entry['path'])
        now = datetime.now(timezone.utc)
        hosts = set(local_hosts)
        if all_nodes:
            # PulseDAV host directories may occur under any subdirectory.
            hosts.update(posixpath.dirname(f['path']) for f in files if posixpath.basename(f['path']).startswith('pulse_') and f['path'].endswith('.md'))
            hosts.update(row['directory'] for row in inventory)
        servers = []
        for host in sorted(hosts):
            descendants = [f for f in files if f['path'].startswith(host + '/')]
            newest = latest(descendants)
            pulse = latest([f for f in descendants if posixpath.basename(f['path']).startswith('pulse_') and f['path'].endswith('.md')])
            age = (now - datetime.fromisoformat(pulse['modified_at'])).total_seconds() / 60 if pulse else None
            status = 'missing' if pulse is None else ('clock_skew' if age < -5 else 'ok' if age <= threshold else 'stale')
            if any(e['directory'] == host or e['directory'].startswith(host + '/') or host.startswith(e['directory'] + '/') for e in errors):
                status = 'unknown'
            row = {'server_name': posixpath.basename(host), 'ip_address': None, 'open_port': None,
                   'directory': host, 'latest_file': newest['path'] if newest else None,
                   'latest_modified_at': newest['modified_at'] if newest else None,
                   'latest_pulse_file': pulse['path'] if pulse else None, 'age_minutes': round(age, 2) if age is not None else None,
                   'status': status, 'metadata_source': pulse['path'] if pulse else None}
            try:
                row.update(report_metadata(session, config, pulse))
            except Exception as exc:
                errors.append({'directory': host, 'error': 'metadata_' + type(exc).__name__})
            configured = next((item for item in inventory if item['directory'] == host), None)
            if configured:
                row.update({key: configured[key] for key in ('server_name', 'ip_address', 'open_port') if key in configured})
                row['metadata_source'] = str(Path(server_list).resolve())
            servers.append(row)
    finally:
        if hasattr(session, 'close'):
            session.close()
    result = {'checked_at': now.isoformat(), 'webdav_server': config.hostname, 'target_directory': 'tinyGW',
              'scope': 'all' if all_nodes else 'local', 'target_directories': targets,
              'settings_file': str(path), 'cron_notes': notes, 'max_age_minutes': threshold,
              'scan_complete': not errors, 'servers': servers, 'directories': directories, 'files': files, 'errors': errors,
              'port_note': 'SSH port reported by PulseDAV; reachability is not probed.'}
    tree = render_tree(result)
    output = Path(output_dir) if output_dir else DEFAULT_OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    for name, content in [('server_status.json', json.dumps(result, ensure_ascii=False, indent=2) + '\n'), ('server_status.txt', tree)]:
        destination = output / name
        temporary = destination.with_suffix(destination.suffix + '.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(destination)
    print(tree, end='')
    print(f'Results: {output.resolve()}')
    return 2 if errors else 1 if any(s['status'] != 'ok' for s in servers) else 0
