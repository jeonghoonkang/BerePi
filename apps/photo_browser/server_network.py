"""Server-side address discovery with a non-blocking, bounded public-IP lookup."""
import ipaddress
import socket
import threading
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen


def local_addresses():
    addresses = set()
    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None, type=socket.SOCK_DGRAM):
            addresses.add(entry[4][0].split('%', 1)[0])
    except OSError:
        pass
    try:
        # UDP connect selects the default outgoing interface without sending a packet.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
            route.settimeout(1)
            route.connect(('192.0.2.1', 9))
            addresses.add(route.getsockname()[0])
    except OSError:
        pass
    result = []
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if not (address.is_loopback or address.is_unspecified or address.is_multicast or address.is_link_local):
            result.append(str(address))
    return sorted(result, key=lambda value: (ipaddress.ip_address(value).version, value))


def public_address():
    request = Request('https://api.ipify.org', headers={'User-Agent': 'BerePi-PhotoBrowser/1.0'})
    with urlopen(request, timeout=4) as response:
        value = response.read(128).decode('ascii').strip()
    address = ipaddress.ip_address(value)
    if not address.is_global:
        raise ValueError('The public-IP service did not return a public address')
    return str(address)


class ServerNetwork:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.expires = 0
        self.state = {'internal_ips': [], 'external_ip': None, 'status': 'loading', 'checked_at': None}

    def get(self):
        with self.lock:
            if not self.running and time.monotonic() >= self.expires:
                self.running = True
                threading.Thread(target=self.refresh, name='photo-server-ip', daemon=True).start()
            return {**self.state, 'internal_ips': list(self.state['internal_ips']), 'refreshing': self.running}

    def refresh(self):
        try:
            addresses = local_addresses()
            with self.lock:
                self.state['internal_ips'] = addresses
            external = public_address()
            state = {'internal_ips': addresses, 'external_ip': external, 'status': 'ok', 'checked_at': datetime.now(timezone.utc).isoformat()}
            ttl = 600
        except Exception:
            # Network errors never block page rendering or scan processing.
            with self.lock:
                addresses = list(self.state['internal_ips'])
            state = {'internal_ips': addresses, 'external_ip': None, 'status': 'unavailable', 'checked_at': datetime.now(timezone.utc).isoformat()}
            ttl = 60
        with self.lock:
            self.state = state
            self.expires = time.monotonic() + ttl
            self.running = False
