#!/usr/bin/env python3
"""Collect SSH authentication events, send daily reports, and answer Telegram queries."""

import argparse
import configparser
import datetime as dt
import gzip
import hashlib
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path


APP_NAME = "ssh-telegram-monitor"
BASE_DIR = Path(os.environ.get("SSH_MONITOR_DATA_DIR", Path.home() / ".local/share" / APP_NAME))
DB_PATH = BASE_DIR / "events.sqlite3"
REPORT_LOG = BASE_DIR / "daily-reports.log"
APP_LOG = BASE_DIR / "monitor.log"
TELEGRAM_CONFIG = Path(os.environ.get("TELEGRAM_SEND_CONFIG", Path.home() / ".config/telegram-send.conf"))
TELEGRAM_SEND = Path.home() / ".local/bin/telegram-send"
DB_LOCK = threading.RLock()
MONITOR_LOG_MAX_BYTES = 5 * 1024 * 1024
MONITOR_LOG_BACKUPS = 10
DAILY_LOG_MAX_BYTES = 10 * 1024 * 1024
DAILY_LOG_BACKUPS = 12

IP_RE = r"(?P<ip>(?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F:]+)"
FAILED_INVALID_RE = re.compile(r"Failed password for invalid user (?P<user>\S+) from " + IP_RE + r" port")
FAILED_RE = re.compile(r"Failed password for (?P<user>\S+) from " + IP_RE + r" port")
ACCEPTED_RE = re.compile(r"Accepted (?P<method>password|publickey) for (?P<user>\S+) from " + IP_RE + r" port")


def configure_logging():
    os.umask(0o077)
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        str(APP_LOG),
        maxBytes=MONITOR_LOG_MAX_BYTES,
        backupCount=MONITOR_LOG_BACKUPS,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[file_handler, logging.StreamHandler()],
    )


def append_daily_report(report):
    """Append a report to a bounded set of 10 MiB rotating text files."""
    handler = RotatingFileHandler(
        str(REPORT_LOG),
        maxBytes=DAILY_LOG_MAX_BYTES,
        backupCount=DAILY_LOG_BACKUPS,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord(
        name="daily-report",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="=== generated {} ===\n{}".format(fmt_ts(int(time.time())), report),
        args=(),
        exc_info=None,
    )
    try:
        handler.emit(record)
    finally:
        handler.close()


def connect_db():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS events (
             cursor TEXT PRIMARY KEY,
             ts INTEGER NOT NULL,
             kind TEXT NOT NULL,
             username TEXT,
             ip TEXT NOT NULL,
             method TEXT,
             invalid_user INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ip_ts ON events(ip, ts)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_events_natural ON events(ts,kind,username,ip,method)")
    conn.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    return conn


def state_get(conn, key):
    row = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def state_set(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO state(key,value) VALUES(?,?)", (key, value))


def parse_message(message):
    match = FAILED_INVALID_RE.search(message)
    if match:
        return "failed", match.group("user"), match.group("ip"), "password", 1
    match = FAILED_RE.search(message)
    if match:
        return "failed", match.group("user"), match.group("ip"), "password", 0
    match = ACCEPTED_RE.search(message)
    if match:
        return "accepted", match.group("user"), match.group("ip"), match.group("method"), 0
    return None


def backfill_auth_logs(conn, initial_days=30):
    """Import retained auth.log files once; this avoids expensive full-journal scans."""
    if state_get(conn, "auth_backfill_complete"):
        return 0
    cutoff = int(time.time()) - initial_days * 86400
    now = dt.datetime.now()
    inserted = 0
    paths = sorted(Path("/var/log").glob("auth.log*"), key=lambda p: p.stat().st_mtime)
    line_re = re.compile(r"^(?P<stamp>[A-Z][a-z]{2}\s+\d{1,2}\s+\d\d:\d\d:\d\d)\s+")
    for path in paths:
        opener = gzip.open if path.suffix == ".gz" else open
        try:
            with opener(str(path), "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    parsed = parse_message(line)
                    stamp_match = line_re.match(line)
                    if not parsed or not stamp_match:
                        continue
                    stamp = dt.datetime.strptime(stamp_match.group("stamp"), "%b %d %H:%M:%S")
                    year = now.year - 1 if stamp.month > now.month + 1 else now.year
                    epoch = int(time.mktime(stamp.replace(year=year).timetuple()))
                    if epoch < cutoff:
                        continue
                    key = "auth:" + hashlib.sha256(line.encode("utf-8", "replace")).hexdigest()
                    conn.execute(
                        "INSERT OR IGNORE INTO events(cursor,ts,kind,username,ip,method,invalid_user) VALUES(?,?,?,?,?,?,?)",
                        (key, epoch) + parsed,
                    )
                    inserted += conn.execute("SELECT changes()").fetchone()[0]
        except OSError as exc:
            logging.warning("Could not read %s: %s", path, exc)
    state_set(conn, "auth_backfill_complete", "1")
    state_set(conn, "history_start", str(cutoff))
    conn.commit()
    logging.info("auth.log backfill complete: %d events", inserted)
    return inserted


def sync_journal(conn, initial_days=30):
    inserted = backfill_auth_logs(conn, initial_days)
    cursor = state_get(conn, "journal_cursor")
    cmd = [
        "journalctl", "-u", "ssh", "-u", "sshd", "--no-pager", "-o", "json",
    ]
    if cursor:
        cmd.append("--after-cursor=" + cursor)
    else:
        latest = conn.execute("SELECT max(ts) FROM events").fetchone()[0]
        cmd.extend(["--since", "@%d" % max(0, (latest or int(time.time())) - 2)])

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    last_cursor = cursor
    assert proc.stdout is not None
    for line in proc.stdout:
        try:
            item = json.loads(line)
            parsed = parse_message(item.get("MESSAGE", ""))
            item_cursor = item.get("__CURSOR")
            ts_text = item.get("__REALTIME_TIMESTAMP")
            if item_cursor:
                last_cursor = item_cursor
            if not parsed or not item_cursor or not ts_text:
                continue
            try:
                ipaddress.ip_address(parsed[2])
            except ValueError:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO events(cursor,ts,kind,username,ip,method,invalid_user) VALUES(?,?,?,?,?,?,?)",
                (item_cursor, int(ts_text) // 1000000) + parsed,
            )
            inserted += conn.execute("SELECT changes()").fetchone()[0]
            if inserted and inserted % 5000 == 0:
                state_set(conn, "journal_cursor", last_cursor)
                conn.commit()
        except (ValueError, json.JSONDecodeError) as exc:
            logging.warning("Skipping malformed journal record: %s", exc)

    stderr = proc.stderr.read() if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise RuntimeError("journalctl failed (%d): %s" % (code, stderr.strip()))
    if last_cursor:
        state_set(conn, "journal_cursor", last_cursor)
    conn.commit()
    logging.info("Journal synchronization complete: %d new events", inserted)
    return inserted


def local_day_bounds(day):
    start = int(time.mktime(day.timetuple()))
    end = int(time.mktime((day + dt.timedelta(days=1)).timetuple()))
    return start, end


def fmt_ts(epoch):
    return dt.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")


def period_stats(conn, start=None, end=None):
    where = []
    params = []
    if start is not None:
        where.append("ts>=?")
        params.append(start)
    if end is not None:
        where.append("ts<?")
        params.append(end)
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    row = conn.execute(
        """SELECT count(*),
                  sum(kind='failed'), sum(kind='accepted'),
                  count(DISTINCT CASE WHEN kind='failed' THEN ip END),
                  sum(kind='failed' AND invalid_user=1),
                  sum(kind='failed' AND username='root'), min(ts), max(ts)
           FROM events""" + clause,
        params,
    ).fetchone()
    top_ips = conn.execute(
        "SELECT ip,count(*) n FROM events" + clause + (" AND " if clause else " WHERE ") +
        "kind='failed' GROUP BY ip ORDER BY n DESC,ip LIMIT 5",
        params,
    ).fetchall()
    top_users = conn.execute(
        "SELECT username,count(*) n FROM events" + clause + (" AND " if clause else " WHERE ") +
        "kind='failed' GROUP BY username ORDER BY n DESC,username LIMIT 5",
        params,
    ).fetchall()
    return row, top_ips, top_users


def format_period(conn, title, start=None, end=None):
    row, top_ips, top_users = period_stats(conn, start, end)
    total, failed, accepted, unique_ips, invalid, root, first_ts, last_ts = row
    failed, accepted, invalid, root = [int(x or 0) for x in (failed, accepted, invalid, root)]
    lines = [
        "🔐 SSH 보안 통계 — " + title,
        "실패: {:,}회 | 공격 IP: {:,}개".format(failed, unique_ips or 0),
        "없는 계정: {:,}회 | root 시도: {:,}회".format(invalid, root),
        "성공 인증: {:,}회".format(accepted),
    ]
    if top_ips:
        lines.append("상위 IP: " + ", ".join("{}({:,})".format(ip, n) for ip, n in top_ips))
    if top_users:
        lines.append("상위 ID: " + ", ".join("{}({:,})".format(user or "?", n) for user, n in top_users))
    if total:
        lines.append("관측: {} ~ {}".format(fmt_ts(first_ts), fmt_ts(last_ts)))
    else:
        lines.append("해당 기간에 저장된 SSH 인증 기록이 없습니다.")
    return "\n".join(lines)


def daily_report(conn):
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    start, end = local_day_bounds(yesterday)
    yesterday_text = format_period(conn, "어제 " + yesterday.isoformat(), start, end)
    cumulative = format_period(conn, "누적(최근 30일 백필 이후)")
    return yesterday_text + "\n\n" + cumulative


def ip_report(conn, ip):
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return "올바른 IP 주소가 아닙니다: " + ip
    row = conn.execute(
        """SELECT count(*), sum(kind='failed'), sum(kind='accepted'),
                  count(DISTINCT username), min(ts), max(ts)
           FROM events WHERE ip=?""",
        (ip,),
    ).fetchone()
    total, failed, accepted, users, first_ts, last_ts = row
    if not total:
        return "{}의 접속 기록은 현재 DB에 없습니다.".format(ip)
    names = conn.execute(
        "SELECT username,count(*) n FROM events WHERE ip=? GROUP BY username ORDER BY n DESC LIMIT 8", (ip,)
    ).fetchall()
    return "\n".join([
        "🔎 IP 조회: " + ip,
        "최초 시도: " + fmt_ts(first_ts),
        "최근 시도: " + fmt_ts(last_ts),
        "실패: {:,}회 | 성공: {:,}회 | 대상 ID: {:,}개".format(failed or 0, accepted or 0, users or 0),
        "대상 ID: " + ", ".join("{}({:,})".format(u or "?", n) for u, n in names),
    ])


def answer_query(conn, text):
    normalized = text.strip()
    ip_match = re.search(r"(?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F]{0,4}:[0-9a-fA-F:]+", normalized)
    if ip_match:
        return ip_report(conn, ip_match.group(0))
    if "누적" in normalized or "지금까지" in normalized:
        return format_period(conn, "누적(최근 30일 백필 이후)")
    if "어제" in normalized:
        day = dt.date.today() - dt.timedelta(days=1)
    else:
        ago_match = re.search(r"(\d+)\s*일\s*전", normalized)
        date_match = re.search(r"(20\d{2})[-./년 ]\s*(\d{1,2})[-./월 ]\s*(\d{1,2})", normalized)
        if ago_match:
            day = dt.date.today() - dt.timedelta(days=int(ago_match.group(1)))
        elif date_match:
            try:
                day = dt.date(*(int(x) for x in date_match.groups()))
            except ValueError:
                return "날짜가 올바르지 않습니다. 예: 2026-09-01"
        elif "오늘" in normalized:
            day = dt.date.today()
        else:
            return (
                "질문 예시:\n"
                "• 어제 / 오늘 / 3일전 / 10일전\n"
                "• 2026-09-01 상황\n"
                "• 누적 상황\n"
                "• 59.14.241.229 언제부터"
            )
    start, end = local_day_bounds(day)
    return format_period(conn, day.isoformat(), start, end)


def telegram_credentials():
    parser = configparser.ConfigParser()
    if not parser.read(str(TELEGRAM_CONFIG)) or not parser.has_section("telegram"):
        raise RuntimeError("telegram-send config not found: " + str(TELEGRAM_CONFIG))
    return parser.get("telegram", "token"), int(parser.get("telegram", "chat_id"))


def send_daily(text):
    cmd = [str(TELEGRAM_SEND), "--config", str(TELEGRAM_CONFIG), "--format", "text", "--stdin"]
    subprocess.run(cmd, input=text, text=True, check=True)


def run_bot(conn):
    from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

    token, allowed_chat_id = telegram_credentials()
    updater = Updater(token=token, use_context=True)

    def handle(update, context):
        if not update.effective_chat or update.effective_chat.id != allowed_chat_id:
            logging.warning("Ignored Telegram query from unauthorized chat %s", getattr(update.effective_chat, "id", None))
            return
        query = update.effective_message.text or ""
        query = re.sub(r"^/ssh(?:@\w+)?\s*", "", query).strip()
        try:
            with DB_LOCK:
                sync_journal(conn)
                response = answer_query(conn, query)
            update.effective_message.reply_text(response)
        except Exception:
            logging.exception("Telegram query failed")
            update.effective_message.reply_text("SSH 통계 조회 중 오류가 발생했습니다. monitor.log를 확인하세요.")

    updater.dispatcher.add_handler(CommandHandler("ssh", handle))
    updater.dispatcher.add_handler(CommandHandler("ssh_help", handle))
    updater.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle))
    logging.info("Telegram query bot started for chat_id=%s", allowed_chat_id)
    updater.start_polling(drop_pending_updates=False)
    updater.idle()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("sync", "daily", "query", "bot"))
    parser.add_argument("query", nargs="*")
    parser.add_argument("--initial-days", type=int, default=30)
    args = parser.parse_args()
    configure_logging()
    conn = connect_db()

    if args.command == "sync":
        count = sync_journal(conn, args.initial_days)
        print("새 이벤트 {:,}건 저장".format(count))
    elif args.command == "daily":
        sync_journal(conn, args.initial_days)
        report = daily_report(conn)
        append_daily_report(report)
        send_daily(report)
        print(report)
    elif args.command == "query":
        sync_journal(conn, args.initial_days)
        print(answer_query(conn, " ".join(args.query)))
    elif args.command == "bot":
        sync_journal(conn, args.initial_days)
        run_bot(conn)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("Fatal error")
        print("error: " + str(exc), file=sys.stderr)
        sys.exit(1)
