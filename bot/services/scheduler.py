"""APScheduler: reads times from DB Settings, supports live reschedule."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from bot.config import TZ, ALLOWED_USERS, ADMIN_IDS, MOM_IDS

_scheduler: AsyncIOScheduler | None = None


def setup_scheduler(bot, scheduler: AsyncIOScheduler):
    global _scheduler
    _scheduler = scheduler
    _schedule_all(bot, scheduler)


def _schedule_all(bot, scheduler: AsyncIOScheduler):
    tz = pytz.timezone(TZ)

    scheduler.add_job(
        _job_night_questionnaire, CronTrigger(hour=8, minute=30, timezone=tz),
        args=[bot], id="night_questionnaire", replace_existing=True,
    )
    scheduler.add_job(
        _job_evening_digest, CronTrigger(hour=21, minute=0, timezone=tz),
        args=[bot], id="evening_digest", replace_existing=True,
    )
    scheduler.add_job(
        _job_weight_reminder, CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=tz),
        args=[bot], id="weight_reminder", replace_existing=True,
    )


async def reschedule_jobs(bot):
    """Re-read settings from DB and reschedule all jobs."""
    if _scheduler is None:
        return
    from bot.models import get_setting
    tz = pytz.timezone(TZ)

    # Night report
    nr_enabled = await get_setting("night_report_enabled") == "1"
    nr_h = int(await get_setting("night_report_hour"))
    nr_m = int(await get_setting("night_report_minute"))
    if nr_enabled:
        _scheduler.add_job(
            _job_night_questionnaire,
            CronTrigger(hour=nr_h, minute=nr_m, timezone=tz),
            args=[bot], id="night_questionnaire", replace_existing=True,
        )
    else:
        _safe_remove("night_questionnaire")

    # Evening digest
    ed_enabled = await get_setting("evening_digest_enabled") == "1"
    ed_h = int(await get_setting("evening_digest_hour"))
    ed_m = int(await get_setting("evening_digest_minute"))
    if ed_enabled:
        _scheduler.add_job(
            _job_evening_digest,
            CronTrigger(hour=ed_h, minute=ed_m, timezone=tz),
            args=[bot], id="evening_digest", replace_existing=True,
        )
    else:
        _safe_remove("evening_digest")

    # Weight reminder
    wr_enabled = await get_setting("weight_reminder_enabled") == "1"
    wr_h = int(await get_setting("weight_reminder_hour"))
    wr_m = int(await get_setting("weight_reminder_minute"))
    if wr_enabled:
        _scheduler.add_job(
            _job_weight_reminder,
            CronTrigger(day_of_week="mon", hour=wr_h, minute=wr_m, timezone=tz),
            args=[bot], id="weight_reminder", replace_existing=True,
        )
    else:
        _safe_remove("weight_reminder")


def _safe_remove(job_id: str):
    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass


# ── Jobs ──────────────────────────────────────────────────────────────────────

async def _job_night_questionnaire(bot):
    from bot.models import get_setting
    if await get_setting("night_report_enabled") != "1":
        return
    from bot.handlers.night_report import send_night_questionnaire
    for uid in ALLOWED_USERS:
        try:
            await send_night_questionnaire(bot, uid)
        except Exception:
            pass


async def _job_evening_digest(bot):
    from bot.models import get_setting
    if await get_setting("evening_digest_enabled") != "1":
        return
    from datetime import timezone, timedelta, datetime
    from sqlalchemy import select
    from bot.models import SleepLog, SessionLocal
    from bot.services.baby import fmt_duration

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    async with SessionLocal() as s:
        res = await s.execute(
            select(SleepLog).where(SleepLog.started_at >= day_start)
        )
        sleep_logs = res.scalars().all()

    total = sum(
        int((s.ended_at - s.started_at).total_seconds())
        for s in sleep_logs if s.ended_at
    )
    text = (
        "🌙 *Итоги дня*\n\n"
        f"😴 Поспал за день: *{fmt_duration(total)}*\n\n"
        "Спокойной ночи! 🌟"
    )
    for uid in ALLOWED_USERS:
        try:
            await bot.send_message(uid, text, parse_mode="Markdown")
        except Exception:
            pass


async def _job_weight_reminder(bot):
    from bot.models import get_setting
    if await get_setting("weight_reminder_enabled") != "1":
        return
    text = "⚖️ *Напоминание*\n\nНе забудь взвесить Феликса сегодня!"
    for uid in ADMIN_IDS | MOM_IDS:
        try:
            await bot.send_message(uid, text, parse_mode="Markdown")
        except Exception:
            pass
