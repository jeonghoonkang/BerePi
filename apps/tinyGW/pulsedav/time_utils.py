"""A shared Seoul timezone, independent of the machine's local timezone."""
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    SEOUL = ZoneInfo("Asia/Seoul")
except ZoneInfoNotFoundError:
    # Minimal installations may lack the IANA timezone database.
    SEOUL = timezone(timedelta(hours=9), "KST")
