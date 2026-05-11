"""
Music module — redesigned:

All users (mom/dad/admin):
  - See list of tracks with [▶ Play] buttons
  - [📩 Заявка на трек] → send name or link → forwarded to admin as message

Admin only:
  - Also sees [🗑 Delete] buttons on tracks
  - Can add tracks by sending an audio FILE directly to the bot
  - Receives track requests as messages from the bot
"""
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, Audio, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.config import is_allowed, is_admin, ADMIN_IDS
from bot.keyboards.inline import music_kb
from bot.models import MusicTrack, SessionLocal
from bot.services.msg_tracker import replace_section

router = Router()


class MusicStates(StatesGroup):
    waiting_request_text = State()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_tracks() -> list:
    async with SessionLocal() as s:
        res = await s.execute(select(MusicTrack).order_by(MusicTrack.created_at.asc()))
        return res.scalars().all()


async def show_music_menu(message: Message):
    tracks = await _get_tracks()
    admin = is_admin(message.from_user.id)
    if tracks:
        text = "🎵 *Музыка*\n\nВыбери трек для воспроизведения:"
    else:
        text = "🎵 *Музыка*\n\n_Треков пока нет. Оставь заявку — добавим!_"
    if admin:
        text += "\n\n_Чтобы добавить трек — просто отправь аудио-файл._"
    sent = await message.answer(text, reply_markup=music_kb(tracks, is_admin=admin), parse_mode="Markdown")
    await replace_section(message.bot, message.chat.id, sent.message_id)


# ── Play ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("music:play:"))
async def music_play(callback: CallbackQuery, bot: Bot):
    track_id = int(callback.data.split(":")[2])
    async with SessionLocal() as s:
        track = await s.get(MusicTrack, track_id)

    if not track:
        await callback.answer("Трек не найден", show_alert=True)
        return

    await callback.answer(f"▶ {track.title[:30]}")
    await bot.send_audio(
        chat_id=callback.message.chat.id,
        audio=track.file_id,
        title=track.title,
        duration=track.duration,
    )


# ── Delete (admin only) ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("music:del:"))
async def music_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    track_id = int(callback.data.split(":")[2])
    async with SessionLocal() as s:
        track = await s.get(MusicTrack, track_id)
        if track:
            await s.delete(track)
            await s.commit()

    tracks = await _get_tracks()
    text = "🎵 *Музыка*\n\n" + ("Выбери трек:" if tracks else "_Треков нет._")
    text += "\n\n_Чтобы добавить трек — отправь аудио-файл._"
    await callback.message.edit_text(text, reply_markup=music_kb(tracks, is_admin=True), parse_mode="Markdown")
    await callback.answer("🗑 Удалено")


# ── Request track (mom/dad → admin) ──────────────────────────────────────────

@router.callback_query(F.data == "music:request")
async def music_request_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MusicStates.waiting_request_text)
    await callback.message.answer(
        "📩 *Заявка на трек*\n\n"
        "Напишите название песни или артиста.\n"
        "Можно скинуть ссылку на YouTube/VK/Spotify.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(MusicStates.waiting_request_text)
async def music_request_received(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        return
    request_text = message.text or message.caption or ""
    if not request_text.strip():
        await message.answer("Напишите название песни или ссылку текстом.")
        return
    await state.clear()

    user_name = message.from_user.first_name or "Пользователь"

    # Forward to all admins
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"🎵 *Заявка на трек*\n\n"
                f"От: *{user_name}*\n"
                f"Запрос: {request_text}\n\n"
                f"_Когда найдёшь — отправь аудио-файл в чат_",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    await message.answer(
        "✅ Заявка отправлена! Трек скоро появится в списке.",
    )


# ── Admin: add track by uploading audio file ──────────────────────────────────

@router.message(F.audio | F.document)
async def admin_audio_upload(message: Message, bot: Bot):
    """Admin sends an audio file directly → auto-added to library."""
    if not is_admin(message.from_user.id):
        return

    audio = message.audio or message.document

    # Only process actual audio files
    if message.document:
        mime = message.document.mime_type or ""
        if not mime.startswith("audio/"):
            return

    if message.audio:
        title = message.audio.performer and message.audio.title \
            and f"{message.audio.performer} — {message.audio.title}"
        title = title or message.audio.file_name or "Трек"
        duration = message.audio.duration or 0
        file_id = message.audio.file_id
    else:
        title = message.document.file_name or "Трек"
        # strip extension
        if "." in title:
            title = title.rsplit(".", 1)[0]
        duration = 0
        file_id = message.document.file_id

    # Remove leading numbers/underscores from filename
    title = title.strip()

    async with SessionLocal() as s:
        track = MusicTrack(title=title, url="", file_id=file_id, duration=duration)
        s.add(track)
        await s.commit()

    tracks = await _get_tracks()
    await message.answer(
        f"✅ Трек добавлен: *{title}*\n"
        f"Всего треков: {len(tracks)}",
        reply_markup=music_kb(tracks, is_admin=True),
        parse_mode="Markdown",
    )
