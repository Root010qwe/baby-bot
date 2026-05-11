from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def sleep_asleep_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="😴 Уснул", callback_data="sleep:fell"))
    return builder.as_markup()


def sleep_awake_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🌞 Проснулся", callback_data="sleep:woke"))
    return builder.as_markup()


def time_picker_kb(action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Сейчас", callback_data=f"time:{action}:0"),
        InlineKeyboardButton(text="1 мин",  callback_data=f"time:{action}:1"),
        InlineKeyboardButton(text="5 мин",  callback_data=f"time:{action}:5"),
    )
    builder.row(
        InlineKeyboardButton(text="10 мин", callback_data=f"time:{action}:10"),
        InlineKeyboardButton(text="20 мин", callback_data=f"time:{action}:20"),
        InlineKeyboardButton(text="30 мин", callback_data=f"time:{action}:30"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Другое время", callback_data=f"time:{action}:custom"),
    )
    return builder.as_markup()


def weight_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚖️ Внести вес", callback_data="weight:add"),
        InlineKeyboardButton(text="📈 График",     callback_data="weight:chart"),
    )
    return builder.as_markup()


def analytics_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Сегодня", callback_data="analytics:today"),
        InlineKeyboardButton(text="📊 Неделя",  callback_data="analytics:week"),
        InlineKeyboardButton(text="📈 Месяц",   callback_data="analytics:month"),
    )
    return builder.as_markup()


# ── Music keyboards ────────────────────────────────────────────────────────────

def music_kb(tracks: list, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Track list for all users. Admin gets delete buttons too."""
    builder = InlineKeyboardBuilder()
    for track in tracks:
        short = track.title[:26] + "…" if len(track.title) > 26 else track.title
        if is_admin:
            builder.row(
                InlineKeyboardButton(text=f"▶ {short}", callback_data=f"music:play:{track.id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"music:del:{track.id}"),
            )
        else:
            builder.row(
                InlineKeyboardButton(text=f"▶ {short}", callback_data=f"music:play:{track.id}"),
            )
    builder.row(InlineKeyboardButton(text="📩 Заявка на трек", callback_data="music:request"))
    return builder.as_markup()


def music_request_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Отправить", callback_data="music:request:confirm"))
    builder.row(InlineKeyboardButton(text="✏️ Изменить", callback_data="music:request:edit"))
    return builder.as_markup()


# ── Night report ───────────────────────────────────────────────────────────────

def night_wakeups_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Не просыпался", callback_data="night:wakeups:0"))
    builder.row(
        InlineKeyboardButton(text="1", callback_data="night:wakeups:1"),
        InlineKeyboardButton(text="2", callback_data="night:wakeups:2"),
        InlineKeyboardButton(text="3", callback_data="night:wakeups:3"),
        InlineKeyboardButton(text="4", callback_data="night:wakeups:4"),
        InlineKeyboardButton(text="5+", callback_data="night:wakeups:5"),
    )
    return builder.as_markup()


def night_awake_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="~15 мин", callback_data="night:awake:15"),
        InlineKeyboardButton(text="~30 мин", callback_data="night:awake:30"),
        InlineKeyboardButton(text="~1 час",  callback_data="night:awake:60"),
    )
    builder.row(
        InlineKeyboardButton(text="~1.5 ч",  callback_data="night:awake:90"),
        InlineKeyboardButton(text="~2 ч",    callback_data="night:awake:120"),
        InlineKeyboardButton(text=">2 ч",    callback_data="night:awake:150"),
    )
    return builder.as_markup()


def night_quality_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="😌 Спокойная", callback_data="night:quality:calm"),
        InlineKeyboardButton(text="😐 Средняя",   callback_data="night:quality:medium"),
        InlineKeyboardButton(text="😩 Тяжёлая",   callback_data="night:quality:hard"),
    )
    return builder.as_markup()


# ── Settings ───────────────────────────────────────────────────────────────────

def settings_kb(settings: dict) -> InlineKeyboardMarkup:
    def _on(key): return "✅" if settings.get(key) == "1" else "☐"
    def _t(h, m): return f"{int(settings.get(h,8)):02d}:{int(settings.get(m,0)):02d}"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"{_on('night_report_enabled')} Утренний опросник ({_t('night_report_hour','night_report_minute')})",
        callback_data="settings:toggle:night_report"))
    builder.row(InlineKeyboardButton(text="🕐 Изменить время", callback_data="settings:time:night_report"))

    builder.row(InlineKeyboardButton(
        text=f"{_on('evening_digest_enabled')} Вечерний дайджест ({_t('evening_digest_hour','evening_digest_minute')})",
        callback_data="settings:toggle:evening_digest"))
    builder.row(InlineKeyboardButton(text="🕐 Изменить время", callback_data="settings:time:evening_digest"))

    builder.row(InlineKeyboardButton(
        text=f"{_on('weight_reminder_enabled')} Напоминание о весе ({_t('weight_reminder_hour','weight_reminder_minute')} пн)",
        callback_data="settings:toggle:weight_reminder"))
    builder.row(InlineKeyboardButton(text="🕐 Изменить время", callback_data="settings:time:weight_reminder"))

    return builder.as_markup()
