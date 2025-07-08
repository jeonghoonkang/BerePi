import argparse
import base64
import http.server
import socketserver
import urllib.request
import urllib.parse
import threading

# hold mapping information (out_port -> target url) for status display
status_data = []

class ProxyHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def do_PUT(self):
        self.forward()

    def do_DELETE(self):
        self.forward()

    def do_HEAD(self):
        self.forward()

    def forward(self):
        target = self.server.target
        url = urllib.parse.urljoin(target, self.path)
        data = None
        if 'Content-Length' in self.headers:
            length = int(self.headers['Content-Length'])
            data = self.rfile.read(length)
        headers = {k: v for k, v in self.headers.items() if k.lower() != 'host'}
        req = urllib.request.Request(url, data=data, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                for key, value in resp.getheaders():
                    if key.lower() == 'transfer-encoding' and value.lower() == 'chunked':
                        continue
                    self.send_header(key, value)
                self.end_headers()
                body = resp.read()
                self.wfile.write(body)
        except urllib.error.HTTPError as e:
            self.send_error(e.code, e.reason)
        except Exception as e:
            self.send_error(502, str(e))

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class StatusHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Basic authentication if configured
        expected = getattr(self.server, 'auth', None)
        if expected:
            auth_header = self.headers.get('Authorization')
            if auth_header != expected:
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Basic realm="Proxy Status"')
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'Authentication required.')
                return
        html = '<html><body><h1>Proxy Status</h1>'
        html += f'<p>Status port: {self.server.status_port}</p>'
        html += '<ul>'
        for out_port, target in self.server.data:
            html += f'<li>{out_port} -&gt; {target}</li>'
        html += '</ul></body></html>'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))


def start_status_server(port, data, auth_header=None):
    handler = StatusHTTPRequestHandler
    server = ThreadingHTTPServer(('', port), handler)
    server.data = data
    server.status_port = port
    if auth_header:
        server.auth = auth_header
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def write_status_file(path, data, status_port):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'status_port: {status_port}\n')
        for out_port, target in data:
            f.write(f'{out_port} -> {target}\n')


def start_proxy(port, target):
    handler = ProxyHTTPRequestHandler
    server = ThreadingHTTPServer(('', port), handler)
    server.target = target
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def parse_map(mapping):
    parts = mapping.split(':')
    if len(parts) != 3:
        raise argparse.ArgumentTypeError('mapping must be OUT_PORT:HOST:PORT')
    out_port = int(parts[0])
    host = parts[1]
    target_port = int(parts[2])
    target = f'http://{host}:{target_port}'
    return out_port, target


def main():
    parser = argparse.ArgumentParser(description='Simple multi reverse proxy')
    parser.add_argument('--map', action='append', required=True,
                        metavar='OUT_PORT:HOST:PORT',
                        help='forward OUT_PORT to HOST:PORT')
    parser.add_argument('--status-port', type=int, default=8000,
                        help='port to serve status page')
    parser.add_argument('--status-file', default='status.txt',
                        help='path to write status information')
    parser.add_argument('--status-user', default=None,
                        help='username for status page basic auth')
    parser.add_argument('--status-pass', dest='status_pass', default=None,
                        help='password for status page basic auth')
    args = parser.parse_args()

    servers = []
    global status_data
    for m in args.map:
        out_port, target = parse_map(m)
        srv = start_proxy(out_port, target)
        print(f'Forwarding 0.0.0.0:{out_port} -> {target}')
        servers.append(srv)
        status_data.append((out_port, target))

    write_status_file(args.status_file, status_data, args.status_port)

    auth_header = None
    if args.status_user and args.status_pass:
        token = f'{args.status_user}:{args.status_pass}'
        b64 = base64.b64encode(token.encode('utf-8')).decode('ascii')
        auth_header = 'Basic ' + b64

    status_srv = start_status_server(args.status_port, status_data, auth_header)

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        status_srv.shutdown()
        for srv in servers:
            srv.shutdown()


if __name__ == '__main__':
    main()
