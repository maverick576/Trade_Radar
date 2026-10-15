"""Time utilities ensuring all internal timestamps use UTC (aware) with WIB presentation support."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

WIB_TZ = ZoneInfo("Asia/Jakarta")
UTC_TZ = UTC


def utc_now() -> datetime:
    """Return current timestamp in UTC timezone."""
    return datetime.now(UTC_TZ)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(UTC_TZ)


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


NY_TZ = ZoneInfo("America/New_York")


def is_us_dst(dt: datetime | None = None) -> bool:
    """Return True if US Eastern Time is currently in Daylight Saving Time (EDT, UTC-4)."""
    target = dt or utc_now()
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC_TZ)
    ny_dt = target.astimezone(NY_TZ)
    return bool(ny_dt.dst())


def is_gold_market_open(dt: datetime | None = None) -> bool:
    """Return True if spot Gold (XAU/USD) market is open.

    Market hours in New York Time (America/New_York):
    - Opens Sunday at 18:00 ET.
    - Closes Friday at 17:00 ET.
    - Daily maintenance break Mon-Thu from 17:00 to 18:00 ET.
    - Closed all day Saturday and Sunday until 18:00 ET.
    """
    target = dt or utc_now()
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC_TZ)
    ny = target.astimezone(NY_TZ)
    weekday = ny.weekday()  # Monday=0, ..., Friday=4, Saturday=5, Sunday=6
    hour = ny.hour
    minute = ny.minute
    time_min = hour * 60 + minute

    # Saturday: completely closed
    if weekday == 5:
        return False

    # Sunday: opens at 18:00 ET (1080 minutes)
    if weekday == 6:
        return time_min >= 18 * 60

    # Friday: closes at 17:00 ET (1020 minutes)
    if weekday == 4:
        return time_min < 17 * 60

    # Monday through Thursday (0, 1, 2, 3):
    # Daily break between 17:00 and 18:00 ET
    if 17 * 60 <= time_min < 18 * 60:
        return False

    return True


def is_gold_rollover(
    dt: datetime | None = None,
    start_utc: str = "20:45",
    end_utc: str = "01:15",
) -> bool:
    """Check if timestamp falls into broker daily rollover window where spreads widen.

    Default window: 20:45 UTC to 01:15 UTC next day.
    """
    target = dt or utc_now()
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC_TZ)
    utc_dt = target.astimezone(UTC_TZ)

    start_h, start_m = (int(x) for x in start_utc.split(":"))
    end_h, end_m = (int(x) for x in end_utc.split(":"))

    target_min = utc_dt.hour * 60 + utc_dt.minute
    start_min = start_h * 60 + start_m
    end_min = end_h * 60 + end_m

    if start_min < end_min:
        return start_min <= target_min <= end_min
    else:
        # Crosses midnight UTC (e.g. 20:45 to 01:15)
        return target_min >= start_min or target_min <= end_min


def get_gold_market_status(
    dt: datetime | None = None,
    rollover_start_utc: str = "20:45",
    rollover_end_utc: str = "01:15",
) -> dict[str, object]:
    """Provide comprehensive status of the Gold market (open, rollover, session, DST)."""
    target = dt or utc_now()
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC_TZ)

    ny = target.astimezone(NY_TZ)
    open_status = is_gold_market_open(target)
    rollover_status = is_gold_rollover(target, rollover_start_utc, rollover_end_utc)
    dst = is_us_dst(target)

    reason: str | None = None
    if not open_status:
        if ny.weekday() == 5 or (ny.weekday() == 6 and ny.hour < 18):
            reason = "Pasar emas tutup akhir pekan (buka Senin 05:00/06:00 WIB / Minggu 18:00 ET)"
        elif ny.weekday() == 4 and ny.hour >= 17:
            reason = "Pasar emas tutup akhir pekan sejak Sabtu 04:00/05:00 WIB / Jumat 17:00 ET"
        else:
            reason = "Pasar emas dalam jeda istirahat harian (17:00-18:00 ET)"
    elif rollover_status:
        reason = (
            f"Periode rollover spread broker melebar "
            f"({rollover_start_utc} - {rollover_end_utc} UTC)"
        )

    return {
        "is_open": open_status,
        "is_rollover": rollover_status,
        "is_dst": dst,
        "ny_time": ny.isoformat(),
        "utc_time": target.astimezone(UTC_TZ).isoformat(),
        "wib_time": to_wib(target).isoformat(),
        "reason": reason,
    }
