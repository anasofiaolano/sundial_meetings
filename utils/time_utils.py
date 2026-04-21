# time_utils.py
#
# Shared timestamp helper used across phase-3B (server, worker, pipeline).
#
# All timestamps in this project are stored in Pacific time so they're
# human-readable without conversion when viewed in the DB or log files.
# The ISO string includes the UTC offset (e.g. -07:00 for PDT, -08:00 for PST)
# so the value is still unambiguous if you ever need to convert it.

from datetime import datetime
from zoneinfo import ZoneInfo  # stdlib in Python 3.9+

# Pacific time zone — automatically handles PST/PDT daylight saving transitions.
PT = ZoneInfo("America/Los_Angeles")


def now_pt() -> str:
    """Return the current Pacific time as an ISO 8601 string with UTC offset."""
    return datetime.now(PT).isoformat()


def now_pt_tag() -> str:
    """
    Return the current Pacific time as a compact, filesystem-safe string.
    Format: YYYYMMDD-HHMMSS  (e.g. '20260402-091532')
    Used as the prefix for run folder names so folders sort chronologically.
    No colons or timezone suffix — safe on all operating systems.
    """
    return datetime.now(PT).strftime("%Y%m%d-%H%M%S")
