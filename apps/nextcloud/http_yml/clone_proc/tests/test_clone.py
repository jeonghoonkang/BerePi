import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("clone", Path(__file__).parents[1] / "clone.py")
clone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clone)


class CloneTests(unittest.TestCase):
    def test_compose_preserves_password_dollars_and_does_not_publish_db(self):
        meta = {"app_env": {"MYSQL_PASSWORD": "a${value}$b", "OVERWRITEHOST": "old.example",
                            "NEXTCLOUD_TRUSTED_DOMAINS": "old.example"},
                "db_env": {"MYSQL_PASSWORD": "a${value}$b"},
                "images": {"app": {"tag": "clone-app:fixed"}, "db": {"tag": "clone-db:fixed"}},
                "data_keys": ["html", "db", "db_config", "db_backup"]}
        config = clone.compose_config(meta, Path("/mnt/target"), 22080)
        app = config["services"]["nextcloud"]
        db = config["services"]["nextcloud_db"]
        self.assertEqual(app["environment"]["MYSQL_PASSWORD"], "a$${value}$$b")
        self.assertNotIn("OVERWRITEHOST", app["environment"])
        self.assertNotIn("NEXTCLOUD_TRUSTED_DOMAINS", app["environment"])
        self.assertEqual(app["ports"], ["22080:80"])
        self.assertNotIn("ports", db)
        self.assertEqual(db["volumes"][0]["target"], "/var/lib/mysql")
        self.assertFalse(db["volumes"][0]["bind"]["create_host_path"])

    def test_origin_rejects_credentials_https_and_subpaths(self):
        for origin in ("http://user:secret@192.0.2.20", "https://192.0.2.20",
                       "http://192.0.2.20/cloud", "http://192.0.2.20?x=1"):
            with self.subTest(origin=origin), self.assertRaises(clone.CloneError):
                clone.origin_parts(origin)
        self.assertEqual(clone.origin_parts("http://192.0.2.20:22080/"),
                         ("http://192.0.2.20:22080", "192.0.2.20:22080", 22080))

    def test_new_directory_rejects_overlap_existing_and_git(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            for path in (source, source / "nested"):
                with self.assertRaises(clone.CloneError):
                    clone.new_directory(path, root, [source])
            repo = root / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            with self.assertRaises(clone.CloneError):
                clone.new_directory(repo / "bundle", root)

    def test_incomplete_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "READY").touch()
            (root / "INCOMPLETE").touch()
            with self.assertRaises(clone.CloneError):
                clone.read_bundle(root)

    def test_kernel_fault_prevents_work(self):
        with patch.object(clone, "run", return_value="BUG: unable to handle page fault"), \
                self.assertRaises(clone.CloneError):
            clone.kernel_check()

    def test_copy_never_removes_source(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(clone, "run") as run:
            clone.copy_tree(Path(temp) / "source", Path(temp) / "target", 51200)
            args = run.call_args.args[0]
            self.assertNotIn("--remove-source-files", args)
            self.assertNotIn("--delete", args)

    def test_comparison_delete_is_always_dry_run(self):
        with patch.object(clone, "run", return_value="") as run:
            for checksum in (False, True):
                clone.verify_tree(Path("/source"), Path("/target"), checksum)
                args = run.call_args.args[0]
                self.assertIn("n", args[1])
                self.assertEqual("c" in args[1], checksum)
        with patch.object(clone, "run", return_value=">f.st...... changed-file"), \
                self.assertRaises(clone.CloneError):
            clone.verify_tree(Path("/source"), Path("/target"), False)

    def test_transfer_never_publishes_ready_after_failure(self):
        args = SimpleNamespace(bundle="/bundle", ssh="root@192.0.2.20",
                               remote_dir="/mnt/disk/clone", bwlimit=51200)
        with patch.object(clone, "require_tools"), \
                patch.object(clone, "read_bundle", return_value=(Path("/bundle"), {})), \
                patch.object(clone, "run", side_effect=[None, clone.CloneError("failed")]) as run:
            with self.assertRaises(clone.CloneError):
                clone.transfer(args)
            self.assertEqual(run.call_count, 2)
            self.assertIn("--exclude=/READY", run.call_args.args[0])

    def test_transfer_rejects_remote_shell_injection(self):
        args = SimpleNamespace(bundle="/bundle", ssh="root@192.0.2.20",
                               remote_dir="/mnt/backup;touch /tmp/pwn", bwlimit=51200)
        with patch.object(clone, "require_tools"), \
                patch.object(clone, "read_bundle", return_value=(Path("/bundle"), {})), \
                patch.object(clone, "run") as run:
            with self.assertRaises(clone.CloneError):
                clone.transfer(args)
            run.assert_not_called()

    def test_same_host_restore_is_rejected_before_copy(self):
        args = SimpleNamespace(bundle="/bundle")
        with patch.object(clone, "require_tools"), patch.object(clone, "kernel_check"), \
                patch.object(clone, "run"), patch.object(clone, "machine_key", return_value="host"), \
                patch.object(clone, "read_bundle", return_value=(Path("/bundle"), {"source_machine": "host"})), \
                patch.object(clone, "copy_tree") as copy:
            with self.assertRaises(clone.CloneError):
                clone.restore(args)
            copy.assert_not_called()

    def test_export_copy_failure_restores_source_and_leaves_incomplete(self):
        for maintenance in (False, True):
            with self.subTest(maintenance=maintenance), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / "source"
                source.mkdir()
                compose = root / "source.yml"
                compose.write_text("services: {}\n")
                app = {"Id": "app", "State": {"Running": True}, "Image": "sha256:app",
                       "Config": {"Env": ["MYSQL_PASSWORD=private"]}}
                db = {"Id": "db", "State": {"Running": True}, "Image": "sha256:db",
                      "Config": {"Env": ["MYSQL_USER=nc", "MYSQL_PASSWORD=private", "MYSQL_DATABASE=nc"]}}
                stopped = {"State": {"Running": False, "ExitCode": 0}}
                status = {"installed": True, "needsDbUpgrade": False, "version": "27.0.1.2",
                          "maintenance": maintenance}

                def command(args, **kwargs):
                    if args[:3] == ["docker", "image", "inspect"]:
                        return json.dumps([{"Id": args[3], "Architecture": "amd64", "Size": 1,
                                            "Config": {}}])
                    if args[0] == "du":
                        return "1 source"
                    return ""

                def occ(container, *args):
                    if args[0] == "status":
                        return json.dumps(status)
                    if args == ("config:system:get", "datadirectory"):
                        return "/var/www/html/data"
                    if args == ("config:system:get", "dbhost"):
                        return "nextcloud_db"
                    if args == ("config:list", "system"):
                        return '{"system":{"dbtype":"mysql"}}'
                    return ""

                args = SimpleNamespace(app="app", db="db", output=root / "bundle", mount=root,
                                       compose=compose, verify_content=False, bwlimit=51200)
                with patch.object(clone, "require_tools"), patch.object(clone, "kernel_check"), \
                        patch.object(clone, "inspect", side_effect=[app, db, stopped, stopped]), \
                        patch.object(clone, "mount_map", return_value={"html": source, "db": source}), \
                        patch.object(clone, "mounted", return_value=root), \
                        patch.object(clone, "machine_key", return_value="host"), \
                        patch.object(clone, "db_ready"), patch.object(clone, "app_ready"), \
                        patch.object(clone, "occ", side_effect=occ) as occ_call, \
                        patch.object(clone, "run", side_effect=command) as run, \
                        patch.object(clone, "copy_tree", side_effect=clone.CloneError("copy failed")):
                    with self.assertRaises(clone.CloneError):
                        clone.export(args)
                    calls = [call.args[0] for call in run.call_args_list]
                    self.assertIn(["docker", "start", "db"], calls)
                    self.assertIn(["docker", "start", "app"], calls)
                    off_calls = [call for call in occ_call.call_args_list if "--off" in call.args]
                    self.assertEqual(len(off_calls), 0 if maintenance else 1)
                    self.assertTrue((root / "bundle/INCOMPLETE").exists())
                    self.assertFalse((root / "bundle/READY").exists())


if __name__ == "__main__":
    unittest.main()
