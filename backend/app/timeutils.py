from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import Settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_tz(settings: Settings) -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def local_now(settings: Settings) -> datetime:
    return utcnow().astimezone(get_tz(settings))


def local_today(settings: Settings) -> date:
    return local_now(settings).date()


def to_local(value: datetime, settings: Settings) -> datetime:
    return as_utc(value).astimezone(get_tz(settings))


def period_key(task_type: str, settings: Settings, at: datetime | None = None) -> str:
    now = to_local(at, settings) if at is not None else local_now(settings)
    if task_type == "daily":
        return now.date().isoformat()
    if task_type == "weekly":
        iso = now.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return "once"


def week_start_utc(settings: Settings) -> datetime:
    now = local_now(settings)
    start_date = now.date() - timedelta(days=now.weekday())
    start_local = datetime.combine(start_date, time.min, tzinfo=get_tz(settings))
    return start_local.astimezone(timezone.utc)


def local_date_start_utc(value: date, settings: Settings) -> datetime:
    start_local = datetime.combine(value, time.min, tzinfo=get_tz(settings))
    return start_local.astimezone(timezone.utc)


def local_date_end_utc(value: date, settings: Settings) -> datetime:
    """Exclusive end: the first instant of the following local day."""
    start_local = datetime.combine(
        value + timedelta(days=1), time.min, tzinfo=get_tz(settings)
    )
    return start_local.astimezone(timezone.utc)


def period_bounds(
    period: str, anchor: date | None, settings: Settings
) -> tuple[date, date, str]:
    """Return the inclusive local-date range and a human-readable label."""
    today = local_today(settings)
    anchor = anchor or today
    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
        iso = start.isocalendar()
        label = f"{iso.year} 年第 {iso.week} 周"
    elif period == "month":
        start = anchor.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        end = next_month - timedelta(days=1)
        label = f"{start.year} 年 {start.month} 月"
    elif period == "quarter":
        quarter = (anchor.month - 1) // 3 + 1
        start = date(anchor.year, (quarter - 1) * 3 + 1, 1)
        if quarter == 4:
            next_quarter = date(anchor.year + 1, 1, 1)
        else:
            next_quarter = date(anchor.year, quarter * 3 + 1, 1)
        end = next_quarter - timedelta(days=1)
        label = f"{anchor.year} 年第 {quarter} 季度"
    elif period == "year":
        start = date(anchor.year, 1, 1)
        end = date(anchor.year, 12, 31)
        label = f"{anchor.year} 年"
    else:
        raise ValueError("统计周期不正确")
    return start, end, label


def bucket_starts(
    start: date, end: date, period: str
) -> list[tuple[date, date, str]]:
    """Split a range into chart buckets expressed as local date ranges."""
    buckets: list[tuple[date, date, str]] = []
    if period == "week":
        cursor = start
        while cursor <= end:
            buckets.append((cursor, cursor, cursor.strftime("%m-%d")))
            cursor += timedelta(days=1)
    elif period == "month":
        cursor = start
        while cursor <= end:
            bucket_end = min(end, cursor + timedelta(days=6))
            buckets.append((cursor, bucket_end, cursor.strftime("%m-%d")))
            cursor = bucket_end + timedelta(days=1)
    elif period == "quarter":
        cursor = start
        while cursor <= end:
            next_month = (
                cursor.replace(year=cursor.year + 1, month=1)
                if cursor.month == 12
                else cursor.replace(month=cursor.month + 1)
            )
            bucket_end = min(end, next_month - timedelta(days=1))
            buckets.append((cursor, bucket_end, f"{cursor.month} 月"))
            cursor = next_month
    else:
        cursor = start
        while cursor <= end:
            next_year = cursor.replace(year=cursor.year + 1)
            bucket_end = min(end, next_year - timedelta(days=1))
            buckets.append((cursor, bucket_end, f"{cursor.month} 月"))
            cursor = next_year
    return buckets
