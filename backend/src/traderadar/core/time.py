"""Time utilities ensuring all internal timestamps use UTC (aware) with WIB presentation support."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

WIB_TZ = ZoneInfo("Asia/Jakarta")
UTC_TZ = UTC


def utc_now() -> datetime:
    """Return current timestamp in UTC timezone."""
    return datetime.now(UTC_TZ)


def to_wib(dt: datetime) -> datetime:
    """Convert any aware datetime to Asia/Jakarta (WIB). If naive, assume UTC first."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(WIB_TZ)


def format_wib(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S WIB") -> str:
    """Format datetime in WIB timezone."""
    return to_wib(dt).strftime(fmt)


def to_iso_utc(dt: datetime) -> str:
    """Return ISO format string in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(UTC_TZ).isoformat()
