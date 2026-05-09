import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import BOT_TOKEN
from bot.models import init_db
from bot.services.scheduler import setup_scheduler
from bot.handlers import menu, sleep, weight, music, analytics, night_report, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()

    dp.include_router(menu.router)
    dp.include_router(sleep.router)
    dp.include_router(night_report.router)
    dp.include_router(weight.router)
    dp.include_router(music.router)
    dp.include_router(analytics.router)
    dp.include_router(settings.router)

    scheduler = AsyncIOScheduler()
    setup_scheduler(bot, scheduler)
    scheduler.start()

    log.info("Bot started")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
