from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

SLEEP_BTN = "😴 Сон"
WEIGHT_BTN = "⚖️ Вес"
MUSIC_BTN = "🎵 Музыка"
STATS_BTN = "📊 Статистика"
SETTINGS_BTN = "⚙️ Настройки"


def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SLEEP_BTN), KeyboardButton(text=WEIGHT_BTN)],
            [KeyboardButton(text=MUSIC_BTN), KeyboardButton(text=STATS_BTN)],
            [KeyboardButton(text=SETTINGS_BTN)],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
