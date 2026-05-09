"""
Sleep tracker — gapless user scenario:

STATE A — Baby is AWAKE (no open SleepLog):
  show: "🌞 Не спит Xм" + button [😴 Уснул]
  → tap → time picker → save → back to STATE B confirmation

STATE B — Baby is SLEEPING (open SleepLog exists):
  show: "😴 Спит Xч Yм" + button [🌞 Проснулся]
  → tap → time picker → save → back to STATE A confirmation
"""
from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.keyboards.inline import sleep_asleep_kb, sleep_awake_kb, time_picker_kb
from bot.models import SleepLog, SessionLocal
from bot.services.baby import fmt_duration
from bot.services.msg_tracker import replace_sleep_status
from bot.config import TZ

import pytz

router = Router()
_tz = pytz.timezone(TZ)


class SleepStates(StatesGroup):
    waiting_custom_minutes = State()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_open_sleep() -> SleepLog | None:
    async with SessionLocal() as s:
        res = await s.execute(
            select(SleepLog)
            .where(SleepLog.ended_at.is_(None))
            .where(SleepLog.is_night == False)
            .order_by(SleepLog.started_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()


async def _get_last_ended_sleep() -> SleepLog | None:
    async with SessionLocal() as s:
        res = await s.execute(
            select(SleepLog)
            .where(SleepLog.ended_at.isnot(None))
            .order_by(SleepLog.ended_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _elapsed(dt_naive: datetime) -> int:
    """Seconds since a naive UTC datetime."""
    return int((_utcnow_naive() - dt_naive).total_seconds())


def _fmt_local(dt_naive: datetime) -> str:
    return pytz.utc.localize(dt_naive).astimezone(_tz).strftime("%H:%M")


# ── Main entry: show current state ────────────────────────────────────────────

async def show_sleep_status(message: Message):
    sent = await _build_and_send_status(message.chat.id, message.bot, reply_to=message)
    await replace_sleep_status(message.bot, message.chat.id, sent.message_id)


# ── Action buttons ────────────────────────────────────────────────────────────

@router.callback_query(F.data.in_({"sleep:fell", "sleep:woke"}))
async def sleep_action_chosen(callback: CallbackQuery):
    action = callback.data.split(":")[1]  # "fell" or "woke"
    verb = "уснул" if action == "fell" else "проснулся"

    # Validate state before showing time picker
    open_sleep = await _get_open_sleep()
    if action == "fell" and open_sleep:
        # Already sleeping — ignore, refresh status
        elapsed = _elapsed(open_sleep.started_at)
        await callback.answer(f"Феликс уже спит {fmt_duration(elapsed)}", show_alert=True)
        return
    if action == "woke" and not open_sleep:
        await callback.answer("Сон не был начат", show_alert=True)
        return

    await callback.message.edit_text(
        f"Когда {verb}?",
        reply_markup=time_picker_kb(action),
    )
    await callback.answer()


# ── Time picker ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("time:"))
async def time_picked(callback: CallbackQuery, state: FSMContext):
    # format: time:fell:10  or  time:woke:custom
    parts = callback.data.split(":")  # ["time", "fell", "10"]
    action = parts[1]
    minutes_str = parts[2]

    if minutes_str == "custom":
        await state.update_data(pending_action=action)
        await state.set_state(SleepStates.waiting_custom_minutes)
        await callback.message.edit_text("Введите сколько минут назад (число):")
        await callback.answer()
        return

    await _commit_sleep_event(callback, action, int(minutes_str))
    await callback.answer()


@router.message(SleepStates.waiting_custom_minutes)
async def sleep_custom_minutes(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) < 0:
        await message.answer("Введите целое число, например: 15")
        return
    data = await state.get_data()
    await state.clear()
    await _commit_sleep_event(message, data["pending_action"], int(text))


# ── DB write ──────────────────────────────────────────────────────────────────

async def _commit_sleep_event(target, action: str, minutes_ago: int):
    event_time = _utcnow_naive() - timedelta(minutes=minutes_ago)
    is_fell = action == "fell"

    result_text = ""

    async with SessionLocal() as s:
        if is_fell:
            # Safety: close any accidentally open session
            res = await s.execute(
                select(SleepLog)
                .where(SleepLog.ended_at.is_(None))
                .where(SleepLog.is_night == False)
                .order_by(SleepLog.started_at.desc())
                .limit(1)
            )
            stale = res.scalar_one_or_none()
            if stale:
                stale.ended_at = event_time

            s.add(SleepLog(started_at=event_time))
            await s.commit()
            result_text = f"✅ Уснул в *{_fmt_local(event_time)}*"

        else:  # woke
            res = await s.execute(
                select(SleepLog)
                .where(SleepLog.ended_at.is_(None))
                .where(SleepLog.is_night == False)
                .order_by(SleepLog.started_at.desc())
                .limit(1)
            )
            log = res.scalar_one_or_none()
            if log:
                log.ended_at = event_time
                await s.commit()
                duration = int((event_time - log.started_at).total_seconds())
                result_text = (
                    f"✅ Проснулся в *{_fmt_local(event_time)}*\n"
                    f"Поспал: *{fmt_duration(duration)}*"
                )
            else:
                await s.commit()
                result_text = f"✅ Проснулся в *{_fmt_local(event_time)}*"

    # Show confirmation then updated status
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(result_text, parse_mode="Markdown")
        # Send fresh status as new message
        await _send_updated_status(target.message.chat.id, target.message.bot)
    else:
        await target.answer(result_text, parse_mode="Markdown")
        await _send_updated_status(target.chat.id, target.bot)


async def _send_updated_status(chat_id: int, bot):
    sent = await _build_and_send_status(chat_id, bot)
    await replace_sleep_status(bot, chat_id, sent.message_id)


async def _build_and_send_status(chat_id: int, bot, reply_to=None):
    open_sleep = await _get_open_sleep()
    if open_sleep:
        elapsed = _elapsed(open_sleep.started_at)
        text = (
            f"😴 *Феликс спит*\n"
            f"Уснул в {_fmt_local(open_sleep.started_at)} — уже {fmt_duration(elapsed)}\n\n"
            "Когда проснётся — нажми кнопку:"
        )
        kb = sleep_awake_kb()
    else:
        last = await _get_last_ended_sleep()
        if last and last.ended_at:
            elapsed = _elapsed(last.ended_at)
            duration = int((last.ended_at - last.started_at).total_seconds())
            text = (
                f"🌞 *Феликс не спит* — {fmt_duration(elapsed)}\n"
                f"Прошлый сон: {fmt_duration(duration)} "
                f"({_fmt_local(last.started_at)} – {_fmt_local(last.ended_at)})\n\n"
                "Когда уснёт — нажми кнопку:"
            )
        else:
            text = "🌞 *Феликс не спит*\n\nКогда уснёт — нажми кнопку:"
        kb = sleep_asleep_kb()

    if reply_to:
        return await reply_to.answer(text, reply_markup=kb, parse_mode="Markdown")
    return await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
