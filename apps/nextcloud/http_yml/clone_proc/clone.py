#!/usr/bin/env python3
"""Cold-copy the local Nextcloud/MariaDB pair and restore it on another host."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import urlopen


class CloneError(Exception):
    pass


def log(message):
    print(time.strftime("%Y-%m-%d %H:%M:%S ") + message, flush=True)


def run(args, capture=False, timeout=None):
    result = subprocess.run([str(x) for x in args], text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None,
                            timeout=timeout)
    if result.returncode:
        # Docker inspect and environment arguments can contain credentials.
        raise CloneError("{} failed (exit {}).".format(args[0], result.returncode))
    return result.stdout if capture else None


def inspect(container):
    return json.loads(run(["docker", "inspect", container], capture=True))[0]


def occ(container, *args):
    return run(["docker", "exec", "-u", "www-data", container, "php", "occ", *args],
               capture=True, timeout=60)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    path.chmod(0o600)


def machine_key():
    return hashlib.sha256(Path("/etc/machine-id").read_bytes()).hexdigest()


def kernel_check():
    messages = run(["dmesg"], capture=True, timeout=10)
    if re.search(r"BUG:|Oops:|kernel BUG|I/O error|EXT4-fs error", messages):
        raise CloneError("This boot contains kernel/storage errors. Fix the host before cloning.")


def require_tools(*names):
    for name in names:
        if not shutil.which(name):
            raise CloneError("Required command not found: " + name)


def mounted(path):
    path = Path(path).resolve()
    if not path.is_mount():
        raise CloneError("Not a mounted filesystem: " + str(path))
    return path


def inside(path, parent):
    return path == parent or parent in path.parents


def new_directory(path, mount, forbidden=()):
    path = Path(path).resolve()
    if not inside(path, mount) or path == mount:
        raise CloneError("Destination must be below --mount.")
    if path.exists():
        raise CloneError("Destination already exists; choose a new directory: " + str(path))
    for other in forbidden:
        if inside(path, other) or inside(other, path):
            raise CloneError("Source and destination paths overlap.")
    if any((parent / ".git").exists() for parent in [path, *path.parents]):
        raise CloneError("Do not store a private clone bundle in a Git working tree.")
    return path


def mount_map(app, db):
    allowed = {"app": {"/var/www/html": "html"},
               "db": {"/var/lib/mysql": "db", "/config": "db_config", "/backup": "db_backup"}}
    result = {}
    for role, info in (("app", app), ("db", db)):
        for item in info["Mounts"]:
            dest = item["Destination"]
            if dest not in allowed[role] or item["Type"] not in ("bind", "volume"):
                raise CloneError("Unsupported mount: " + dest)
            source = Path(item["Source"]).resolve()
            if not source.is_dir():
                raise CloneError("Mount source is not a directory.")
            result[allowed[role][dest]] = source
    if not {"html", "db"}.issubset(result):
        raise CloneError("Expected /var/www/html and /var/lib/mysql mounts are missing.")
    return result


def env_map(info):
    return dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)


def copy_tree(source, dest, rate):
    dest.mkdir(parents=True, exist_ok=True)
    # No source deletion: the export is an independent snapshot.
    run(["rsync", "-aHAX", "--numeric-ids", "--info=stats2", "--bwlimit=" + str(rate),
         str(source) + "/", str(dest) + "/"])


def verify_tree(source, dest, checksum):
    flags = "-aHAXnci" if checksum else "-aHAXni"
    output = run(["rsync", flags, "--numeric-ids", "--delete",
                  str(source) + "/", str(dest) + "/"], capture=True)
    if output.strip():
        raise CloneError("Snapshot comparison found differences. Bundle remains incomplete.")


def db_ready(container, seconds=120):
    deadline = time.monotonic() + seconds
    command = ["docker", "exec", container, "sh", "-c",
               'MYSQL_PWD="$MYSQL_PASSWORD" mariadb -u "$MYSQL_USER" '
               '"$MYSQL_DATABASE" -Nse "SELECT 1"']
    while time.monotonic() < deadline:
        try:
            if run(command, capture=True, timeout=10).strip() == "1":
                return
        except (CloneError, subprocess.TimeoutExpired):
            time.sleep(2)
    raise CloneError("Database did not become ready; inspect its private logs.")


def app_ready(container):
    for _ in range(60):
        try:
            status = json.loads(occ(container, "status", "--output=json"))
            if status.get("installed") and not status.get("needsDbUpgrade"):
                return status
        except (CloneError, ValueError, subprocess.TimeoutExpired):
            pass
        time.sleep(2)
    raise CloneError("Nextcloud did not become ready without an upgrade.")


def export(args):
    require_tools("docker", "rsync", "dmesg")
    kernel_check()
    app, db = inspect(args.app), inspect(args.db)
    if not app["State"]["Running"] or not db["State"]["Running"]:
        raise CloneError("Both source containers must be running for preflight checks.")
    paths = mount_map(app, db)
    running = run(["docker", "ps", "-q"], capture=True).split()
    if running:
        others = json.loads(run(["docker", "inspect", *running], capture=True))
        for other in others:
            if other["Id"] in (app["Id"], db["Id"]):
                continue
            for item in other["Mounts"]:
                source = Path(item["Source"]).resolve()
                if any(inside(source, p) or inside(p, source) for p in paths.values()):
                    raise CloneError("Another running container shares snapshot data: " + other["Name"])
    output = new_directory(args.output, mounted(args.mount), list(paths.values()))
    source_compose = Path(args.compose).resolve(strict=True)
    status = json.loads(occ(args.app, "status", "--output=json"))
    if not status.get("installed") or status.get("needsDbUpgrade"):
        raise CloneError("Source is not installed or requires an upgrade.")
    if occ(args.app, "config:system:get", "datadirectory").strip() != "/var/www/html/data":
        raise CloneError("Only the standard /var/www/html/data directory is supported.")
    dbhost = occ(args.app, "config:system:get", "dbhost").strip()
    if dbhost not in ("nextcloud_db", "nextcloud_db:3306"):
        raise CloneError("This procedure expects dbhost=nextcloud_db[:3306].")
    config = json.loads(occ(args.app, "config:list", "system"))["system"]
    if any(config.get(key) for key in ("redis", "objectstore", "objectstore_multibucket")):
        raise CloneError("External Redis/object storage requires a separate migration plan.")
    if config.get("dbtype") != "mysql":
        raise CloneError("Only the MariaDB/mysql Nextcloud backend is supported.")
    db_env = env_map(db)
    if not all(db_env.get(key) for key in ("MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE")):
        raise CloneError("Expected MYSQL_* credentials are missing from the DB container.")
    db_ready(args.db)
    total = sum(int(run(["du", "-s", "-B1", str(p)], capture=True).split()[0])
                for p in paths.values())
    images = {}
    for role, info in (("app", app), ("db", db)):
        image = json.loads(run(["docker", "image", "inspect", info["Image"]], capture=True))[0]
        if any(info["Config"].get(key) != image["Config"].get(key)
               for key in ("Cmd", "Entrypoint")):
            raise CloneError("Custom container command/entrypoint requires an adapted clone procedure.")
        images[role] = {"id": image["Id"], "arch": image["Architecture"],
                        "tag": "nextcloud-clone-{}:{}".format(role, image["Id"].split(":")[1][:16])}
        total += image["Size"]
    if shutil.disk_usage(args.mount).free < total * 1.15:
        raise CloneError("Insufficient export space (data + images + 15% margin required).")
    output.mkdir(parents=True, mode=0o700)
    (output / "INCOMPLETE").touch(mode=0o600)
    (output / "metadata").mkdir(mode=0o700)
    shutil.copyfile(source_compose, output / "metadata/source-compose.yml")
    (output / "metadata/source-compose.yml").chmod(0o600)
    shutil.copyfile(__file__, output / "clone.py")
    manifest = {"format": 1, "source_machine": machine_key(), "images": images,
                "app_env": env_map(app), "db_env": db_env, "data_keys": list(paths),
                "version": status["version"], "checksum_verified": args.verify_content}
    write_json(output / "manifest.json", manifest)
    log("Saving exact running Docker images; source is still online.")
    for item in images.values():
        run(["docker", "image", "tag", item["id"], item["tag"]])
    run(["docker", "image", "save", "-o", output / "images.tar",
         images["app"]["tag"], images["db"]["tag"]])
    changed = False
    try:
        changed = True
        log("Enabling maintenance and stopping source app/DB for a consistent snapshot.")
        occ(args.app, "maintenance:mode", "--on")
        run(["docker", "stop", "-t", "120", args.app], capture=True, timeout=150)
        run(["docker", "stop", "-t", "120", args.db], capture=True, timeout=150)
        for name in (args.app, args.db):
            state = inspect(name)["State"]
            if state["Running"] or state["ExitCode"] != 0:
                raise CloneError("Source did not shut down cleanly: " + name)
        for key, source in paths.items():
            log("Copying snapshot section: " + key)
            copy_tree(source, output / "data" / key, args.bwlimit)
            verify_tree(source, output / "data" / key, args.verify_content)
            kernel_check()
        os.sync()
        kernel_check()
    finally:
        if changed:
            log("Restoring source DB/app and original maintenance state.")
            run(["docker", "start", args.db], capture=True, timeout=60)
            db_ready(args.db)
            run(["docker", "start", args.app], capture=True, timeout=60)
            app_ready(args.app)
            if not status.get("maintenance"):
                occ(args.app, "maintenance:mode", "--off")
    (output / "INCOMPLETE").unlink()
    (output / "READY").write_text("Snapshot complete. Contains private data and credentials.\n")
    log("Export complete: " + str(output))


def read_bundle(bundle):
    bundle = Path(bundle).resolve(strict=True)
    if not (bundle / "READY").is_file() or (bundle / "INCOMPLETE").exists():
        raise CloneError("Bundle is incomplete; it must not be restored.")
    meta = json.loads((bundle / "manifest.json").read_text())
    if meta.get("format") != 1 or not {"html", "db"}.issubset(meta["data_keys"]):
        raise CloneError("Unsupported bundle format.")
    if not set(meta["data_keys"]).issubset({"html", "db", "db_config", "db_backup"}):
        raise CloneError("Invalid data directory in manifest.")
    return bundle, meta


def origin_parts(origin):
    u = urlsplit(origin)
    if (u.scheme != "http" or not u.hostname or u.username or u.password or
            u.path not in ("", "/") or u.query or u.fragment):
        raise CloneError("Use a direct HTTP origin, e.g. http://192.0.2.20:22080 (no subpath).")
    port = u.port or 80
    if not 1 <= port <= 65535:
        raise CloneError("Invalid port.")
    return "http://" + u.netloc, u.netloc, port


def literal(value):
    # Compose interpolates dollar signs even in JSON/YAML values.
    if isinstance(value, str):
        return value.replace("$", "$$")
    if isinstance(value, list):
        return [literal(x) for x in value]
    if isinstance(value, dict):
        return {k: literal(v) for k, v in value.items()}
    return value


def compose_config(meta, destination, port):
    def bind(key, target):
        return {"type": "bind", "source": str(destination / key), "target": target,
                "bind": {"create_host_path": False}}
    app_env = dict(meta["app_env"])
    app_env["MYSQL_HOST"] = "nextcloud_db"
    app_env.pop("NEXTCLOUD_TRUSTED_DOMAINS", None)
    for key in list(app_env):
        if key.startswith("OVERWRITE") or key == "TRUSTED_PROXIES":
            app_env.pop(key)
    db_volumes = [bind("db", "/var/lib/mysql")]
    for key, target in (("db_config", "/config"), ("db_backup", "/backup")):
        if key in meta["data_keys"]:
            db_volumes.append(bind(key, target))
    return literal({"services": {
        "nextcloud": {"image": meta["images"]["app"]["tag"],
                      "container_name": "nextcloud_http", "restart": "unless-stopped",
                      "environment": app_env, "ports": ["{}:80".format(port)],
                      "volumes": [bind("html", "/var/www/html")], "depends_on": ["nextcloud_db"]},
        "nextcloud_db": {"image": meta["images"]["db"]["tag"],
                         "container_name": "nextcloud_db_http", "restart": "unless-stopped",
                         "environment": meta["db_env"], "volumes": db_volumes}}})


def restore(args):
    require_tools("docker", "rsync", "dmesg")
    kernel_check()
    run(["docker", "compose", "version"], capture=True)
    bundle, meta = read_bundle(args.bundle)
    if meta["source_machine"] == machine_key():
        raise CloneError("Restore is restricted to a different host.")
    destination = new_directory(args.destination, mounted(args.mount), [bundle])
    origin, authority, port = origin_parts(args.origin)
    arch = run(["docker", "info", "--format", "{{.Architecture}}"], capture=True).strip()
    arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(arch, arch)
    if any(item["arch"] != arch for item in meta["images"].values()):
        raise CloneError("Target Docker architecture differs from the saved images.")
    names = run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture=True).splitlines()
    if {"nextcloud_http", "nextcloud_db_http"}.intersection(names):
        raise CloneError("Target container names already exist; no containers were replaced.")
    with socket.socket() as probe:
        probe.bind(("0.0.0.0", port))
    needed = int(run(["du", "-s", "-B1", bundle / "data"], capture=True).split()[0])
    if shutil.disk_usage(args.mount).free < needed * 1.15:
        raise CloneError("Insufficient destination data space.")
    docker_root = run(["docker", "info", "--format", "{{.DockerRootDir}}"], capture=True).strip()
    image_space = (bundle / "images.tar").stat().st_size * 2
    shared_disk = os.stat(args.mount).st_dev == os.stat(docker_root).st_dev
    if shutil.disk_usage(docker_root).free < image_space + (needed * 1.15 if shared_disk else 0):
        raise CloneError("Insufficient Docker image storage space.")
    destination.mkdir(parents=True, mode=0o700)
    for key in meta["data_keys"]:
        log("Restoring section: " + key)
        copy_tree(bundle / "data" / key, destination / key, args.bwlimit)
        verify_tree(bundle / "data" / key, destination / key, args.verify_content)
        kernel_check()
    os.sync()
    kernel_check()
    run(["docker", "image", "load", "-i", bundle / "images.tar"], capture=True)
    for item in meta["images"].values():
        actual = run(["docker", "image", "inspect", item["tag"], "--format", "{{.Id}}"],
                     capture=True).strip()
        if actual != item["id"]:
            raise CloneError("Loaded image ID does not match the source.")
    compose = destination / "nextcloud.yml"
    write_json(compose, compose_config(meta, destination, port))
    command = ["docker", "compose", "-p", "nextcloud-clone", "-f", str(compose)]
    run(command + ["config", "--quiet"], capture=True)
    try:
        run(command + ["up", "-d", "--no-deps", "--pull", "never", "nextcloud_db"], capture=True)
        db_ready("nextcloud_db_http")
        run(command + ["up", "-d", "--no-deps", "--pull", "never", "nextcloud"], capture=True)
        status = app_ready("nextcloud_http")
        if status["version"] != meta["version"]:
            raise CloneError("Restored Nextcloud version differs from the source.")
        for key in ("trusted_domains", "trusted_proxies", "overwritecondaddr", "overwritewebroot"):
            occ("nextcloud_http", "config:system:delete", key)
        occ("nextcloud_http", "config:system:set", "trusted_domains", "0", "--value=" + authority)
        for key, value in (("overwritehost", authority), ("overwriteprotocol", "http"),
                           ("overwrite.cli.url", origin)):
            occ("nextcloud_http", "config:system:set", key, "--value=" + value)
        occ("nextcloud_http", "maintenance:data-fingerprint")
        kernel_check()
        occ("nextcloud_http", "maintenance:mode", "--off")
        with urlopen("http://127.0.0.1:{}/status.php".format(port), timeout=15) as response:
            web_status = json.load(response)
        if not web_status.get("installed") or web_status.get("maintenance"):
            raise CloneError("HTTP status check did not pass.")
    except BaseException:
        log("Restore failed; stopping only this clone. Data remains in the destination.")
        subprocess.run(command + ["stop", "-t", "120"], stdout=subprocess.DEVNULL)
        raise
    log("Clone ready: " + origin)
    log("Test login/upload/download from a separate browser/client before switching clients.")


def transfer(args):
    require_tools("rsync", "ssh")
    bundle, _ = read_bundle(args.bundle)
    if not re.fullmatch(r"root@[A-Za-z0-9][A-Za-z0-9.-]*", args.ssh):
        raise CloneError("Use root@TARGET_IP or root@hostname with key authentication.")
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", args.remote_dir) or ".." in Path(args.remote_dir).parts:
        raise CloneError("Use an absolute remote path containing only letters, digits, /, _, -, .")
    if args.remote_dir == "/":
        raise CloneError("Remote directory cannot be filesystem root.")
    # An existing directory is refused; failed transfers are not silently treated as complete.
    run(["ssh", "-o", "BatchMode=yes", args.ssh,
         "umask 077 && mkdir -- " + args.remote_dir])
    run(["rsync", "-aHAX", "--numeric-ids", "--protect-args", "--info=stats2",
         "--bwlimit=" + str(args.bwlimit), "--exclude=/READY", "-e", "ssh -o BatchMode=yes",
         str(bundle) + "/", args.ssh + ":" + args.remote_dir + "/"])
    # Publish the completion marker only after every other file was transferred.
    run(["rsync", "-a", "--protect-args", "-e", "ssh -o BatchMode=yes",
         bundle / "READY", args.ssh + ":" + args.remote_dir + "/READY"])
    log("Transfer complete; run restore on the destination host.")


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    e = sub.add_parser("export", help="Create a new private offline snapshot; restore source afterward")
    e.add_argument("--compose", required=True, help="Actual source Compose file, not the repository example")
    e.add_argument("--app", default="nextcloud_http")
    e.add_argument("--db", default="nextcloud_db_http")
    e.add_argument("--output", required=True)
    e.add_argument("--mount", required=True, help="Expected mounted export filesystem")
    e.add_argument("--verify-content", action="store_true", help="Read all data again for checksum comparison")
    e.set_defaults(func=export)
    t = sub.add_parser("transfer", help="Copy a completed bundle over SSH to another host")
    t.add_argument("--bundle", required=True)
    t.add_argument("--ssh", required=True)
    t.add_argument("--remote-dir", required=True, help="New directory; its parent must already exist")
    t.set_defaults(func=transfer)
    r = sub.add_parser("restore", help="Copy snapshot to a new directory and start the clone")
    r.add_argument("--bundle", required=True)
    r.add_argument("--destination", required=True)
    r.add_argument("--mount", required=True, help="Expected mounted destination filesystem")
    r.add_argument("--origin", required=True, help="http://TARGET_IP:PORT")
    r.add_argument("--verify-content", action="store_true")
    r.set_defaults(func=restore)
    for child in (e, t, r):
        child.add_argument("--bwlimit", type=int, default=51200, help="rsync KiB/s limit (default 51200)")
    return p


def main():
    args = parser().parse_args()
    if os.geteuid() != 0:
        raise CloneError("Run with sudo/root to preserve ownership and read private data.")
    if args.bwlimit < 1:
        raise CloneError("--bwlimit must be positive.")
    os.umask(0o077)
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(143))
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except (CloneError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Interrupted; inspect source/target status before retrying.", file=sys.stderr)
        sys.exit(130)
