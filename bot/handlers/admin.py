"""Admin panel: /admin — view DB stats and delete data without touching code."""
from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy import select, func, delete

from bot.config import is_admin
from bot.models import SleepLog, WeightLog, MusicTrack, NightReport, SessionLocal

router = Router()

# What each action deletes (shown in confirmation message)
_ACTION_LABELS = {
    "last_sleep":       "последний сон",
    "today_sleep":      "все сны за сегодня",
    "all_sleep":        "ВСЕ записи сна",
    "last_weight":      "последнюю запись веса",
    "all_weights":      "ВСЕ записи веса",
    "all_nightreports": "все ночные отчёты",
    "all_music":        "все треки музыки",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _db_stats() -> dict:
    async with SessionLocal() as s:
        sleep_total   = (await s.execute(select(func.count()).select_from(SleepLog))).scalar()
        sleep_open    = (await s.execute(
            select(func.count()).select_from(SleepLog).where(SleepLog.ended_at.is_(None))
        )).scalar()
        weight_total  = (await s.execute(select(func.count()).select_from(WeightLog))).scalar()
        music_total   = (await s.execute(select(func.count()).select_from(MusicTrack))).scalar()
        night_total   = (await s.execute(select(func.count()).select_from(NightReport))).scalar()
    return {
        "sleep": sleep_total,
        "sleep_open": sleep_open,
        "weight": weight_total,
        "music": music_total,
        "night": night_total,
    }


def _admin_kb() -> "InlineKeyboardMarkup":
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="admin:refresh"))
    # Sleep
    b.row(
        InlineKeyboardButton(text="🗑 Удалить последний сон",  callback_data="admin:del:last_sleep"),
        InlineKeyboardButton(text="🗑 Сон за сегодня",         callback_data="admin:del:today_sleep"),
    )
    b.row(InlineKeyboardButton(text="💣 Удалить ВЕСЬ сон",     callback_data="admin:del:all_sleep"))
    # Weight
    b.row(
        InlineKeyboardButton(text="🗑 Последний вес",  callback_data="admin:del:last_weight"),
        InlineKeyboardButton(text="💣 Весь вес",       callback_data="admin:del:all_weights"),
    )
    # Other
    b.row(
        InlineKeyboardButton(text="🗑 Ночные отчёты",  callback_data="admin:del:all_nightreports"),
        InlineKeyboardButton(text="🗑 Музыку",         callback_data="admin:del:all_music"),
    )
    return b.as_markup()


def _confirm_kb(action: str) -> "InlineKeyboardMarkup":
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Да, удалить",  callback_data=f"admin:confirm:{action}"),
        InlineKeyboardButton(text="❌ Отмена",        callback_data="admin:cancel"),
    )
    return b.as_markup()


async def _build_stats_text() -> str:
    s = await _db_stats()
    open_note = f" ({s['sleep_open']} открытых)" if s["sleep_open"] else ""
    return (
        "🔧 *Админ-панель*\n\n"
        "📊 *Статистика БД:*\n"
        f"  😴 Сессий сна: {s['sleep']}{open_note}\n"
        f"  ⚖️ Записей веса: {s['weight']}\n"
        f"  🌙 Ночных отчётов: {s['night']}\n"
        f"  🎵 Треков музыки: {s['music']}\n\n"
        "Выбери действие:"
    )


# ── Entry ─────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    text = await _build_stats_text()
    await message.answer(text, reply_markup=_admin_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "admin:refresh")
async def admin_refresh(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    text = await _build_stats_text()
    await callback.message.edit_text(text, reply_markup=_admin_kb(), parse_mode="Markdown")
    await callback.answer("Обновлено")


# ── Delete prompt ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin:del:"))
async def admin_del_prompt(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    action = callback.data.split(":")[2]
    label = _ACTION_LABELS.get(action, action)
    await callback.message.edit_text(
        f"⚠️ Удалить *{label}*?\n\nЭто нельзя отменить.",
        reply_markup=_confirm_kb(action),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:cancel")
async def admin_cancel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    text = await _build_stats_text()
    await callback.message.edit_text(text, reply_markup=_admin_kb(), parse_mode="Markdown")
    await callback.answer("Отменено")


# ── Execute deletion ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin:confirm:"))
async def admin_del_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    action = callback.data.split(":")[2]
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    deleted = 0

    async with SessionLocal() as s:
        if action == "last_sleep":
            res = await s.execute(
                select(SleepLog).order_by(SleepLog.created_at.desc()).limit(1)
            )
            row = res.scalar_one_or_none()
            if row:
                await s.delete(row)
                deleted = 1

        elif action == "today_sleep":
            day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            res = await s.execute(
                select(SleepLog).where(SleepLog.started_at >= day_start)
            )
            rows = res.scalars().all()
            for row in rows:
                await s.delete(row)
            deleted = len(rows)

        elif action == "all_sleep":
            res = await s.execute(select(SleepLog))
            rows = res.scalars().all()
            for row in rows:
                await s.delete(row)
            deleted = len(rows)

        elif action == "last_weight":
            res = await s.execute(
                select(WeightLog).order_by(WeightLog.created_at.desc()).limit(1)
            )
            row = res.scalar_one_or_none()
            if row:
                await s.delete(row)
                deleted = 1

        elif action == "all_weights":
            res = await s.execute(select(WeightLog))
            rows = res.scalars().all()
            for row in rows:
                await s.delete(row)
            deleted = len(rows)

        elif action == "all_nightreports":
            res = await s.execute(select(NightReport))
            rows = res.scalars().all()
            for row in rows:
                await s.delete(row)
            deleted = len(rows)

        elif action == "all_music":
            res = await s.execute(select(MusicTrack))
            rows = res.scalars().all()
            for row in rows:
                await s.delete(row)
            deleted = len(rows)

        await s.commit()

    label = _ACTION_LABELS.get(action, action)
    await callback.answer(f"✅ Удалено ({deleted})", show_alert=True)

    text = await _build_stats_text()
    await callback.message.edit_text(text, reply_markup=_admin_kb(), parse_mode="Markdown")
