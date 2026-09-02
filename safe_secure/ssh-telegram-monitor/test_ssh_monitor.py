import datetime as dt
import sqlite3
import unittest

import ssh_monitor as app


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE events(cursor TEXT PRIMARY KEY, ts INTEGER, kind TEXT, username TEXT, ip TEXT, method TEXT, invalid_user INTEGER)")
        day = dt.date.today() - dt.timedelta(days=3)
        ts, _ = app.local_day_bounds(day)
        self.db.executemany("INSERT INTO events VALUES(?,?,?,?,?,?,?)", [
            ("a", ts + 1, "failed", "root", "203.0.113.1", "password", 0),
            ("b", ts + 2, "failed", "admin", "203.0.113.1", "password", 1),
            ("c", ts + 3, "accepted", "tinyos", "10.0.0.58", "publickey", 0),
        ])

    def test_parse(self):
        got = app.parse_message("Failed password for invalid user admin from 203.0.113.1 port 22 ssh2")
        self.assertEqual(got, ("failed", "admin", "203.0.113.1", "password", 1))

    def test_days_ago(self):
        text = app.answer_query(self.db, "3일전 상황")
        self.assertIn("실패: 2회", text)
        self.assertIn("성공 인증: 1회", text)

    def test_ip(self):
        text = app.answer_query(self.db, "203.0.113.1 언제부터")
        self.assertIn("실패: 2회", text)
        self.assertIn("최초 시도", text)

    def test_rotation_limits(self):
        self.assertEqual(app.MONITOR_LOG_MAX_BYTES, 5 * 1024 * 1024)
        self.assertEqual(app.DAILY_LOG_MAX_BYTES, 10 * 1024 * 1024)
        self.assertGreater(app.MONITOR_LOG_BACKUPS, 0)
        self.assertGreater(app.DAILY_LOG_BACKUPS, 0)

    def test_ufw_candidates_exclude_private(self):
        day = dt.date.today() - dt.timedelta(days=3)
        start, end = app.local_day_bounds(day)
        for index in range(60):
            self.db.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?)",
                ("private-%d" % index, start + 100 + index, "failed", "root", "10.0.0.58", "password", 0),
            )
            self.db.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?)",
                ("public-%d" % index, start + 200 + index, "failed", "root", "8.8.8.8", "password", 0),
            )
        got = app.ufw_block_candidates(self.db, start, end, threshold=50, limit=10)
        self.assertEqual(got, [("8.8.8.8", 60)])


if __name__ == "__main__":
    unittest.main()
