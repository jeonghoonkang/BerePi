"""A shared Seoul timezone, independent of the machine's local timezone."""
from datetime import timedelta, timezone

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    # Python < 3.9 has no standard-library zoneinfo module.
    SEOUL = timezone(timedelta(hours=9), "KST")
else:
    try:
        SEOUL = ZoneInfo("Asia/Seoul")
    except ZoneInfoNotFoundError:
        # Minimal installations may lack the IANA timezone database.
        SEOUL = timezone(timedelta(hours=9), "KST")
