"""Helpers for baby age and current sleep status."""
from datetime import date, datetime
import pytz
from bot.config import BABY_BIRTHDATE, TZ


def baby_age_str() -> str:
    birth = date.fromisoformat(BABY_BIRTHDATE)
    today = date.today()
    months = (today.year - birth.year) * 12 + (today.month - birth.month)
    days = today.day - birth.day
    if days < 0:
        months -= 1
        # days in previous month
        from calendar import monthrange
        prev = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        days += monthrange(*prev)[1]
    if months == 0:
        return f"{days} д."
    return f"{months} мес. {days} д."


def now_tz() -> datetime:
    tz = pytz.timezone(TZ)
    return datetime.now(tz)


def fmt_duration(seconds: int) -> str:
    h, m = divmod(abs(seconds) // 60, 60)
    if h:
        return f"{h}ч {m}м"
    return f"{m}м"
