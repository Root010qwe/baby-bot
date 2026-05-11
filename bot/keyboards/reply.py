from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# Button labels — used as message text matchers in menu.py
SLEEP_BTN    = "😴 Сон"
WEIGHT_BTN   = "⚖️ Вес"
MUSIC_BTN    = "🎵 Музыка"
STATS_BTN    = "📊 Статистика"
SETTINGS_BTN = "⚙️ Настройки"


def full_kb() -> ReplyKeyboardMarkup:
    """Keyboard for mom and admin — all features."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SLEEP_BTN), KeyboardButton(text=WEIGHT_BTN)],
            [KeyboardButton(text=MUSIC_BTN), KeyboardButton(text=STATS_BTN)],
            [KeyboardButton(text=SETTINGS_BTN)],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def dad_kb() -> ReplyKeyboardMarkup:
    """Simplified keyboard for dad — sleep and music only."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SLEEP_BTN)],
            [KeyboardButton(text=MUSIC_BTN)],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def kb_for(user_id: int) -> ReplyKeyboardMarkup:
    from bot.config import is_full_access
    return full_kb() if is_full_access(user_id) else dad_kb()


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
