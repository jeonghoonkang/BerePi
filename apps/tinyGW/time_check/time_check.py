#!/usr/bin/env python3
"""One durable health snapshot; scheduled by cron every ten minutes."""
import argparse
from datetime import datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time

BASE = Path(__file__).resolve().parent


def command(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=8)
        return {"ok": p.returncode == 0, "output": p.stdout.strip(),
                "error": p.stderr.strip() if p.returncode else None}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "output": "", "error": str(exc)}


def read(path):
    return Path(path).read_text().strip()


def cpu_ticks():
    values = list(map(int, read('/proc/stat').splitlines()[0].split()[1:9]))
    return sum(values), values[3] + values[4]


def cpu_percent(before, after):
    total = after[0] - before[0]
    return round(100 * (1 - (after[1] - before[1]) / total), 2) if total > 0 else None


def power_status():
    result = {"undervoltage_now": None, "undervoltage_since_boot": None}
    # Linux rpi_volt driver exposes the firmware undervoltage alarm on this host.
    alarms = []
    for folder in Path('/sys/class/hwmon').glob('hwmon*'):
        try:
            if read(folder / 'name') == 'rpi_volt':
                alarms.append({"path": str(folder / 'in0_lcrit_alarm'),
                               "value": int(read(folder / 'in0_lcrit_alarm'))})
        except (OSError, ValueError):
            continue
    result['hwmon_alarms'] = alarms
    if alarms:
        result['undervoltage_now'] = any(a['value'] != 0 for a in alarms)
    firmware = command(['vcgencmd', 'get_throttled'])
    result['firmware'] = firmware
    match = re.search(r'throttled=(0x[0-9a-fA-F]+)', firmware['output'])
    if firmware['ok'] and match:
        flags = int(match[1], 16)
        names = {0: 'undervoltage_now', 1: 'frequency_capped_now',
                 2: 'throttled_now', 3: 'soft_temperature_limit_now',
                 16: 'undervoltage_since_boot', 17: 'frequency_capped_since_boot',
                 18: 'throttled_since_boot', 19: 'soft_temperature_limit_since_boot'}
        result.update({name: bool(flags & (1 << bit)) for bit, name in names.items()})
        if alarms:
            result['undervoltage_now'] |= any(a['value'] != 0 for a in alarms)
    result['status'] = ('undervoltage_detected' if result['undervoltage_now'] else
                        'no_undervoltage_detected_at_sample' if result['undervoltage_now'] is False
                        else 'unknown')
    return result


def network_snapshot():
    routes, errors, defaults = [], [], set()
    for family in ('-4', '-6'):
        response = command(['ip', '-j', family, 'route', 'show', 'default'])
        if response['ok']:
            try:
                rows = json.loads(response['output'])
                routes.extend(rows)
                for row in rows:
                    if row.get('dev'):
                        defaults.add(row['dev'])
                    defaults.update(h['dev'] for h in row.get('nexthops', []) if h.get('dev'))
            except (ValueError, TypeError) as exc:
                errors.append(str(exc))
        else:
            errors.append(response['error'])
    counters = {}
    for folder in Path('/sys/class/net').iterdir():
        if folder.name == 'lo':
            continue
        try:
            counters[folder.name] = {
                'ifindex': int(read(folder / 'ifindex')),
                'state': read(folder / 'operstate'),
                **{key: int(read(folder / 'statistics' / key)) for key in
                   ('rx_bytes', 'tx_bytes', 'rx_errors', 'tx_errors', 'rx_dropped', 'tx_dropped')}}
        except (OSError, ValueError) as exc:
            errors.append(f'{folder.name}: {exc}')
    return {'default_route_interfaces': sorted(defaults), 'routes': routes,
            'interfaces': counters, 'errors': errors,
            'scope': 'Interface counters include LAN and Internet traffic; not Internet-only.'}


def network_deltas(current, previous, same_boot, seconds):
    for name, values in current['interfaces'].items():
        old = previous.get('interfaces', {}).get(name, {})
        valid = (same_boot and seconds and seconds > 0 and old.get('ifindex') == values['ifindex']
                 and all(values[k] >= old.get(k, 0) for k in ('rx_bytes', 'tx_bytes')))
        values['interval_seconds'] = seconds if valid else None
        for key in ('rx_bytes', 'tx_bytes'):
            delta = values[key] - old[key] if valid and key in old else None
            values[key + '_delta'] = delta
            values[key.replace('_bytes', '_mbps')] = round(delta * 8 / seconds / 1e6, 6) if delta is not None else None


def atomic_json(path, data):
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def cleanup(folder, now):
    # One year is defined as 365 days. Only our timestamped JSON logs are removed.
    cutoff = now.timestamp() - timedelta(days=365).total_seconds()
    deleted, errors = 0, []
    for path in folder.glob('health_*.json'):
        if not re.fullmatch(r'health_\d{8}_\d{6}_\d{6}[+-]\d{4}\.json', path.name):
            continue
        try:
            stamp = datetime.strptime(path.stem[7:], '%Y%m%d_%H%M%S_%f%z')
            if not path.is_symlink() and path.is_file() and stamp.timestamp() < cutoff:
                path.unlink()
                deleted += 1
        except (OSError, ValueError) as exc:
            errors.append(f'{path.name}: {exc}')
    return {'deleted_files': deleted, 'errors': errors, 'retention_days': 365}


def snapshot(folder):
    state_path = folder / '.state.json'
    errors = []
    try:
        previous = json.loads(state_path.read_text())
        if not isinstance(previous, dict):
            raise ValueError('state must be an object')
    except FileNotFoundError:
        previous = {}
    except (OSError, ValueError) as exc:
        previous = {}
        errors.append(f'previous state unavailable: {exc}')
    before = cpu_ticks()
    time.sleep(1)
    after = cpu_ticks()
    now = datetime.now().astimezone()
    boot_id = read('/proc/sys/kernel/random/boot_id')
    uptime = float(read('/proc/uptime').split()[0])
    same_boot = previous.get('boot_id') == boot_id
    elapsed = round(uptime - previous['uptime_seconds'], 3) if same_boot else None
    wall_gap = round(now.timestamp() - previous['timestamp_epoch'], 3) if previous else None
    temperatures = []
    for zone in Path('/sys/class/thermal').glob('thermal_zone*'):
        try:
            temperatures.append({'sensor': read(zone / 'type'), 'celsius': int(read(zone / 'temp')) / 1000})
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    network = network_snapshot()
    network_deltas(network, previous.get('network', {}), same_boot, elapsed)
    record = {
        'timestamp': now.isoformat(), 'timestamp_epoch': now.timestamp(),
        'hostname': socket.gethostname(), 'boot_id': boot_id, 'uptime_seconds': uptime,
        'estimated_boot_time': datetime.fromtimestamp(now.timestamp() - uptime, now.tzinfo).isoformat(),
        'event': 'first_sample' if not previous else 'periodic' if same_boot else 'boot_changed',
        'previous_timestamp': previous.get('timestamp'), 'gap_seconds': wall_gap,
        'missed_interval_suspected': (elapsed if same_boot else wall_gap) > 900 if previous else False,
        'cpu': {'usage_percent_1s': cpu_percent(before, after), 'temperatures': temperatures,
                'usage_percent_since_previous': cpu_percent(previous['cpu_ticks'], after) if same_boot else None},
        'cpu_ticks': after, 'power': power_status(), 'network': network, 'errors': errors,
        'retention': cleanup(folder, now),
    }
    # Keep evidence of storage, power, thermal and OOM issues when the journal is accessible.
    journal = command(['journalctl', '-k', '-b', '--since', '-11 minutes', '-n', '500', '--no-pager', '-o', 'short-iso'])
    pattern = re.compile(r'under.?voltage|brownout|throttl|overheat|thermal|out of memory|oom|I/O error|nvme.*(error|reset|timeout)', re.I)
    record['kernel_warnings'] = {'accessible': journal['ok'], 'error': journal['error'],
                               'lines': [line for line in journal['output'].splitlines() if pattern.search(line)]}
    path = folder / now.strftime('health_%Y%m%d_%H%M%S_%f%z.json')
    atomic_json(path, record)
    atomic_json(state_path, record)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-dir', type=Path, default=BASE / 'log')
    args = parser.parse_args()
    args.log_dir.mkdir(parents=True, exist_ok=True)
    with (args.log_dir / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        print(snapshot(args.log_dir))


if __name__ == '__main__':
    main()
