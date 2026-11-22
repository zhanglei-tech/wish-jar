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


def period_key(task_type: str, settings: Settings) -> str:
    now = local_now(settings)
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
