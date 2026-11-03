#!/usr/bin/env python3
"""Send files to LocalSend v2 peers using only the Python standard library."""

import argparse
import contextlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import socket
import ssl
import sys
import threading
import time
from urllib.parse import urlencode
import uuid

PORT = 53317
GROUP = '224.0.0.167'
API = '/api/localsend/v2/'


class LocalSendError(Exception):
    pass


def connection(host, port, protocol, timeout):
    if protocol == 'https':
        # LocalSend peers use self-signed certificates on the local network.
        return http.client.HTTPSConnection(
            host, port, timeout=timeout, context=ssl._create_unverified_context())
    return http.client.HTTPConnection(host, port, timeout=timeout)


def request(host, port, protocol, route, payload=None, timeout=120):
    with contextlib.closing(connection(host, port, protocol, timeout)) as conn:
        body = json.dumps(payload).encode() if payload is not None else b''
        conn.request('POST', API + route, body, {'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = response.read()
        if not 200 <= response.status < 300:
            hints = {401: 'PIN required or incorrect', 403: 'Receiver rejected the request',
                     409: 'Receiver is busy', 422: 'Checksum mismatch',
                     429: 'Too many requests'}
            raise LocalSendError(f'HTTP {response.status}: '
                                 f'{hints.get(response.status, response.reason)}')
        return json.loads(data) if data else None


def sender_info(alias):
    return dict(alias=alias, version='2.0', deviceModel='BerePi Python',
                deviceType='headless', fingerprint=uuid.uuid4().hex,
                port=PORT, protocol='http', download=False)


def discover(info, seconds=4, interface='0.0.0.0', port=PORT, group=GROUP):
    peers = {}
    lock = threading.Lock()

    def remember(data, host):
        if not isinstance(data, dict) or data.get('fingerprint') == info['fingerprint']:
            return
        if not isinstance(data.get('alias'), str):
            return
        peer_port = data.get('port', port)
        protocol = data.get('protocol', 'https')
        if type(peer_port) is not int or not 1 <= peer_port <= 65535:
            return
        if protocol not in ('http', 'https'):
            return
        with lock:
            peers[(host, peer_port)] = dict(data, host=host, port=peer_port,
                                          protocol=protocol)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != API + 'register':
                self.send_error(404)
                return
            try:
                self.connection.settimeout(2)
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 65536:
                    raise ValueError('invalid registration length')
                remember(json.loads(self.rfile.read(length)), self.client_address[0])
            except (ValueError, OSError):
                self.send_error(400)
                return
            body = json.dumps(info).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer((interface, 0), Handler) as server:
        info = dict(info, port=server.server_port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as udp:
                udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                udp.bind(('', port))
                udp.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                               socket.inet_aton(group) + socket.inet_aton(interface))
                udp.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
                if interface != '0.0.0.0':
                    udp.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                                   socket.inet_aton(interface))
                deadline = time.monotonic() + seconds
                next_announce = 0
                while time.monotonic() < deadline:
                    now = time.monotonic()
                    if now >= next_announce:
                        udp.sendto(json.dumps(dict(info, announce=True)).encode(), (group, port))
                        next_announce = now + 1
                    udp.settimeout(min(0.25, max(0.001, deadline - now)))
                    try:
                        raw, address = udp.recvfrom(65536)
                        remember(json.loads(raw), address[0])
                    except (socket.timeout, ValueError, UnicodeError):
                        continue
        finally:
            server.shutdown()
            thread.join()
    return sorted(peers.values(), key=lambda p: (p['alias'], p['host']))


def collect_files(paths):
    files = {}
    names = set()
    for value in paths:
        root = Path(value).expanduser().absolute()
        if root.is_symlink():
            raise LocalSendError(f'Symbolic links are not supported: {root}')
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = sorted(p for p in root.rglob('*')
                                if p.is_file() and not p.is_symlink()
                                and not any(a.is_symlink() for a in p.parents))
        else:
            raise LocalSendError(f'File or directory not found: {root}')
        for path in candidates:
            name = path.relative_to(root.parent).as_posix() if root.is_dir() else path.name
            if name.casefold() in names:
                raise LocalSendError(f'Duplicate destination filename: {name}')
            names.add(name.casefold())
            file_id = uuid.uuid4().hex
            files[file_id] = (path, dict(id=file_id, fileName=name,
                                        size=path.stat().st_size,
                                        fileType=mimetypes.guess_type(name)[0]
                                        or 'application/octet-stream'))
    if not files:
        raise LocalSendError('No files to send (empty directories are not transferred)')
    return files


def send(host, port, protocol, info, files, pin=None, timeout=120, log=print):
    route = 'prepare-upload' + ('?' + urlencode({'pin': pin}) if pin else '')
    result = request(host, port, protocol, route,
                     dict(info=info, files={k: v[1] for k, v in files.items()}), timeout)
    if result is None:
        log('Receiver reports no transfer needed.')
        return 0
    if not isinstance(result, dict) or not isinstance(result.get('sessionId'), str):
        raise LocalSendError('Invalid prepare-upload response')
    session = result['sessionId']
    accepted = result.get('files')
    sent = 0
    try:
        if not isinstance(accepted, dict) or any(
                k not in files or not isinstance(v, str) for k, v in accepted.items()):
            raise LocalSendError('Invalid file tokens from receiver')
        for file_id, token in accepted.items():
            path, metadata = files[file_id]
            query = urlencode(dict(sessionId=session, fileId=file_id, token=token))
            with path.open('rb') as stream:
                if path.stat().st_size != metadata['size']:
                    raise LocalSendError(f'File size changed: {path}')
                with contextlib.closing(connection(host, port, protocol, timeout)) as conn:
                    conn.putrequest('POST', API + 'upload?' + query)
                    conn.putheader('Content-Type', 'application/octet-stream')
                    conn.putheader('Content-Length', str(metadata['size']))
                    conn.endheaders()
                    remaining = metadata['size']
                    while remaining:
                        chunk = stream.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise LocalSendError(f'File truncated during transfer: {path}')
                        conn.send(chunk)
                        remaining -= len(chunk)
                    response = conn.getresponse()
                    response.read()
                    if not 200 <= response.status < 300:
                        raise LocalSendError(f'Upload failed: HTTP {response.status}')
            sent += 1
            log(f'Sent: {metadata["fileName"]} ({metadata["size"]} bytes)')
    except BaseException:
        try:
            request(host, port, protocol, 'cancel?' + urlencode({'sessionId': session}), timeout=5)
        except Exception:
            pass
        raise
    log(f'Completed: {sent}/{len(files)} files '
        f'({len(files) - sent} not selected by receiver).')
    return sent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alias', default='BerePi-' + socket.gethostname())
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('discover', 'send'):
        command = sub.add_parser(name)
        command.add_argument('--port', type=int, default=PORT)
        command.add_argument('--interface', default='0.0.0.0', help='Local IPv4 interface address')
        command.add_argument('--discovery-timeout', type=float, default=4)
        command.add_argument('--group', default=GROUP)
        if name == 'send':
            target = command.add_mutually_exclusive_group(required=True)
            target.add_argument('--host', help='Receiver IP or hostname (no URL)')
            target.add_argument('--device', help='Exact alias found by discovery')
            command.add_argument('--protocol', choices=['https', 'http'], default='https')
            command.add_argument('--pin')
            command.add_argument('--timeout', type=float, default=120,
                                 help='Seconds to wait for receiver approval / network I/O')
            command.add_argument('paths', nargs='+')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535 or args.discovery_timeout <= 0:
        parser.error('Port must be 1..65535 and discovery timeout must be positive')
    if args.command == 'send' and args.timeout <= 0:
        parser.error('Timeout must be positive')
    info = sender_info(args.alias)
    try:
        files = collect_files(args.paths) if args.command == 'send' else None
        if args.command == 'discover' or args.device:
            peers = discover(info, args.discovery_timeout, args.interface, args.port, args.group)
            if args.command == 'discover':
                for peer in peers:
                    print(f'{peer["alias"]}\t{peer["host"]}:{peer["port"]}\t{peer["protocol"]}')
                if not peers:
                    print('No devices found. Try send --host RECEIVER_IP.')
                return 0
            matches = [p for p in peers if p['alias'] == args.device]
            if len(matches) != 1:
                raise LocalSendError('Device alias missing or ambiguous; use --host RECEIVER_IP')
            peer = matches[0]
            args.host, args.port, args.protocol = peer['host'], peer['port'], peer['protocol']
        send(args.host, args.port, args.protocol, info, files, args.pin, args.timeout)
        return 0
    except (OSError, ValueError, http.client.HTTPException, LocalSendError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Cancelled.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
