"""Notification settings: toggle on/off, change time."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.inline import settings_kb
from bot.models import get_setting, set_setting, DEFAULT_SETTINGS
from bot.services.msg_tracker import replace_section

router = Router()

SETTING_KEYS = {
    "night_report": ("night_report_enabled", "night_report_hour", "night_report_minute"),
    "evening_digest": ("evening_digest_enabled", "evening_digest_hour", "evening_digest_minute"),
    "weight_reminder": ("weight_reminder_enabled", "weight_reminder_hour", "weight_reminder_minute"),
}

SETTING_NAMES = {
    "night_report": "Утренний опросник",
    "evening_digest": "Вечерний дайджест",
    "weight_reminder": "Напоминание о весе",
}


class SettingsStates(StatesGroup):
    waiting_time = State()


async def _load_all() -> dict:
    result = {}
    for key in DEFAULT_SETTINGS:
        result[key] = await get_setting(key)
    return result


async def show_settings(message: Message):
    settings = await _load_all()
    sent = await message.answer(
        "⚙️ *Настройки уведомлений*\n\n"
        "Нажми на уведомление чтобы включить/выключить.\n"
        "Нажми «Изменить время» чтобы поменять время.",
        reply_markup=settings_kb(settings),
        parse_mode="Markdown",
    )
    await replace_section(message.bot, message.chat.id, sent.message_id)


# ── Toggle ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("settings:toggle:"))
async def settings_toggle(callback: CallbackQuery):
    name = callback.data.split(":")[2]  # night_report | evening_digest | weight_reminder
    enabled_key = f"{name}_enabled"
    current = await get_setting(enabled_key)
    new_val = "0" if current == "1" else "1"
    await set_setting(enabled_key, new_val)

    # Reschedule jobs
    from bot.services.scheduler import reschedule_jobs
    await reschedule_jobs(callback.bot)

    settings = await _load_all()
    status = "включено ✅" if new_val == "1" else "выключено ☐"
    await callback.answer(f"{SETTING_NAMES[name]}: {status}")
    await callback.message.edit_reply_markup(reply_markup=settings_kb(settings))


# ── Change time ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("settings:time:"))
async def settings_time_prompt(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split(":")[2]
    await state.update_data(setting_name=name)
    await state.set_state(SettingsStates.waiting_time)
    await callback.message.answer(
        f"Введи новое время для «{SETTING_NAMES[name]}» в формате *ЧЧ:ММ*\n"
        f"Например: `08:30`",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(SettingsStates.waiting_time)
async def settings_time_input(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        h_str, m_str = text.split(":")
        h, m = int(h_str), int(m_str)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except ValueError:
        await message.answer("Формат: ЧЧ:ММ, например 08:30")
        return

    data = await state.get_data()
    name = data["setting_name"]
    await state.clear()

    _, h_key, m_key = SETTING_KEYS[name]
    await set_setting(h_key, str(h))
    await set_setting(m_key, str(m))

    from bot.services.scheduler import reschedule_jobs
    await reschedule_jobs(message.bot)

    settings = await _load_all()
    await message.answer(
        f"✅ {SETTING_NAMES[name]}: время изменено на *{h:02d}:{m:02d}*",
        reply_markup=settings_kb(settings),
        parse_mode="Markdown",
    )
