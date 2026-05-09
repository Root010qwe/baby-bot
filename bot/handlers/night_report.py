"""Morning night-report questionnaire (3 button questions)."""
from datetime import date, datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.keyboards.inline import night_wakeups_kb, night_awake_kb, night_quality_kb
from bot.models import NightReport, SleepLog, SessionLocal
from bot.services.baby import fmt_duration

router = Router()

QUALITY_EMOJI = {"calm": "😌", "medium": "😐", "hard": "😩"}
QUALITY_RU = {"calm": "Спокойная", "medium": "Средняя", "hard": "Тяжёлая"}


class NightStates(StatesGroup):
    waiting_awake = State()
    waiting_quality = State()


async def send_night_questionnaire(bot: Bot, chat_id: int):
    today = date.today().isoformat()
    async with SessionLocal() as s:
        res = await s.execute(select(NightReport).where(NightReport.date == today))
        if res.scalar_one_or_none():
            return  # already filled today

    await bot.send_message(
        chat_id,
        "🌅 *Доброе утро!*\n\nКак прошла ночь?\n\nСколько раз Феликс просыпался?",
        reply_markup=night_wakeups_kb(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("night:wakeups:"))
async def night_wakeups(callback: CallbackQuery, state: FSMContext):
    wakeups = int(callback.data.split(":")[2])
    await state.update_data(wakeups=wakeups)

    if wakeups == 0:
        await state.update_data(awake_minutes=0)
        await callback.message.edit_text(
            "Как оцениваешь ночь?",
            reply_markup=night_quality_kb(),
        )
        await state.set_state(NightStates.waiting_quality)
    else:
        await callback.message.edit_text(
            "Сколько суммарно не спал ночью?",
            reply_markup=night_awake_kb(),
        )
        await state.set_state(NightStates.waiting_awake)
    await callback.answer()


@router.callback_query(NightStates.waiting_awake, F.data.startswith("night:awake:"))
async def night_awake(callback: CallbackQuery, state: FSMContext):
    awake_minutes = int(callback.data.split(":")[2])
    await state.update_data(awake_minutes=awake_minutes)
    await callback.message.edit_text(
        "Как оцениваешь ночь?",
        reply_markup=night_quality_kb(),
    )
    await state.set_state(NightStates.waiting_quality)
    await callback.answer()


@router.callback_query(NightStates.waiting_quality, F.data.startswith("night:quality:"))
async def night_quality(callback: CallbackQuery, state: FSMContext):
    quality = callback.data.split(":")[2]
    data = await state.get_data()
    await state.clear()

    wakeups: int = data["wakeups"]
    awake_minutes: int = data["awake_minutes"]
    today = date.today().isoformat()

    # Approx night sleep: 22:00 prev day → 08:00 today, minus awake time
    night_start = datetime.combine(
        date.today() - timedelta(days=1),
        datetime.strptime("22:00", "%H:%M").time()
    )
    night_end = datetime.combine(date.today(), datetime.strptime("08:00", "%H:%M").time())
    sleep_minutes = int((night_end - night_start).total_seconds() / 60) - awake_minutes

    async with SessionLocal() as s:
        s.add(NightReport(date=today, wakeups=wakeups, awake_minutes=awake_minutes, quality=quality))
        if sleep_minutes > 0:
            s.add(SleepLog(
                started_at=night_start,
                ended_at=night_end - timedelta(minutes=awake_minutes),
                is_night=True,
            ))
        await s.commit()

    eq = QUALITY_EMOJI[quality]
    q_ru = QUALITY_RU[quality]
    wakeups_str = "не просыпался" if wakeups == 0 else f"{wakeups} раз(а)"
    awake_str = f"{awake_minutes} мин" if awake_minutes else "—"
    sleep_str = fmt_duration(sleep_minutes * 60) if sleep_minutes > 0 else "—"

    await callback.message.edit_text(
        f"✅ *Ночь записана*\n\n"
        f"Просыпался: {wakeups_str}\n"
        f"Не спал: {awake_str}\n"
        f"Примерно поспал: {sleep_str}\n"
        f"Качество: {eq} {q_ru}",
        parse_mode="Markdown",
    )
    await callback.answer()
