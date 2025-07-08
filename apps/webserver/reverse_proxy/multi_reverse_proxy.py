import argparse
import http.server
import socketserver
import urllib.request
import urllib.parse
import threading

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
    args = parser.parse_args()

    servers = []
    for m in args.map:
        out_port, target = parse_map(m)
        srv = start_proxy(out_port, target)
        print(f'Forwarding 0.0.0.0:{out_port} -> {target}')
        servers.append(srv)

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for srv in servers:
            srv.shutdown()


if __name__ == '__main__':
    main()
