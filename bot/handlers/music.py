"""
Music: save YouTube/direct links, play via Telegram file_id cache.

YouTube auth: bot accepts a cookies.txt file (Netscape format).
Upload via /cookies command. Stored at data/cookies.txt.
"""
import asyncio
import os
import tempfile
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, FSInputFile, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.keyboards.inline import music_list_kb
from bot.models import MusicTrack, SessionLocal
from bot.services.msg_tracker import replace_section

router = Router()

COOKIES_PATH = Path("data/cookies.txt")


class MusicStates(StatesGroup):
    waiting_url = State()
    waiting_cookies = State()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_tracks() -> list:
    async with SessionLocal() as s:
        res = await s.execute(
            select(MusicTrack).order_by(MusicTrack.created_at.asc())
        )
        return res.scalars().all()


async def show_music_menu(message: Message):
    tracks = await _get_tracks()
    text = "🎵 *Музыка*\n\n" + ("Выберите трек:" if tracks else "_Треков нет. Нажми «Добавить трек»_")
    sent = await message.answer(text, reply_markup=music_list_kb(tracks), parse_mode="Markdown")
    await replace_section(message.bot, message.chat.id, sent.message_id)


# ── Cookies management ────────────────────────────────────────────────────────

@router.message(Command("cookies"))
async def cookies_prompt(message: Message, state: FSMContext):
    await state.set_state(MusicStates.waiting_cookies)
    has = "✅ Файл уже загружен." if COOKIES_PATH.exists() else "❌ Файл не загружен."
    await message.answer(
        f"{has}\n\n"
        "Отправь файл *cookies.txt* (Netscape-формат) для авторизации YouTube.\n\n"
        "Как получить:\n"
        "1. Установи расширение «Get cookies.txt LOCALLY» в Chrome\n"
        "2. Зайди на youtube.com (авторизован)\n"
        "3. Нажми расширение → Export → отправь файл сюда",
        parse_mode="Markdown",
    )


@router.message(MusicStates.waiting_cookies, F.document)
async def cookies_received(message: Message, state: FSMContext, bot: Bot):
    doc: Document = message.document
    if not doc.file_name.endswith(".txt"):
        await message.answer("Ожидаю файл .txt")
        return
    await state.clear()
    COOKIES_PATH.parent.mkdir(exist_ok=True)
    await bot.download(doc, destination=str(COOKIES_PATH))
    await message.answer("✅ cookies.txt сохранён. Теперь YouTube-ссылки должны работать.")


# ── Add track ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "music:add")
async def music_add_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MusicStates.waiting_url)
    await callback.message.answer(
        "Отправь ссылку на YouTube или прямой mp3:\n\n_https://youtu.be/..._",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(MusicStates.waiting_url)
async def music_url_received(message: Message, state: FSMContext, bot: Bot):
    url = message.text.strip() if message.text else ""
    if not url.startswith("http"):
        await message.answer("Отправь корректную ссылку (начинается с http)")
        return

    await state.clear()
    status_msg = await message.answer("⏳ Загружаю трек…")

    try:
        title, file_id, duration = await asyncio.get_event_loop().run_in_executor(
            None, _download_and_upload_sync, url, message.chat.id, bot
        )
    except Exception as e:
        err = str(e)
        hint = ""
        if "Sign in" in err or "bot" in err.lower():
            hint = "\n\n💡 YouTube требует авторизацию. Используй /cookies"
        await status_msg.edit_text(f"❌ Ошибка загрузки:{hint}\n`{err[:300]}`", parse_mode="Markdown")
        return

    async with SessionLocal() as s:
        track = MusicTrack(title=title, url=url, file_id=file_id, duration=duration)
        s.add(track)
        await s.commit()

    tracks = await _get_tracks()
    await status_msg.delete()
    await message.answer(
        f"✅ Добавлено: *{title}*",
        reply_markup=music_list_kb(tracks),
        parse_mode="Markdown",
    )


def _download_and_upload_sync(url: str, chat_id: int, bot: Bot) -> tuple:
    """Sync wrapper for yt-dlp download (runs in executor).
    Downloads best available audio without requiring ffmpeg conversion.
    Preferred order: m4a → webm → ogg → best.
    """
    import yt_dlp
    import asyncio

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            # m4a (format 140) is universally available on YouTube and works in Telegram
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio[ext=ogg]/bestaudio/best",
            "outtmpl": os.path.join(tmpdir, "audio.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            # No postprocessors — avoid ffmpeg dependency
        }
        if COOKIES_PATH.exists():
            ydl_opts["cookiefile"] = str(COOKIES_PATH)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        title = info.get("title", "Трек")
        duration = info.get("duration", 0)

        # Find downloaded audio file (any extension)
        audio_exts = {".m4a", ".webm", ".ogg", ".mp3", ".mp4", ".opus"}
        audio_files = [
            f for f in os.listdir(tmpdir)
            if os.path.splitext(f)[1].lower() in audio_exts
        ]
        if not audio_files:
            all_files = os.listdir(tmpdir)
            if not all_files:
                raise RuntimeError("Файл не скачался")
            audio_files = all_files  # fallback: try whatever is there

        audio_path = os.path.join(tmpdir, audio_files[0])

        loop = asyncio.new_event_loop()
        try:
            file_id = loop.run_until_complete(
                _upload_audio(bot, chat_id, audio_path, title, duration)
            )
        finally:
            loop.close()

    return title, file_id, duration


async def _upload_audio(bot: Bot, chat_id: int, path: str, title: str, duration: int) -> str:
    input_file = FSInputFile(path, filename=f"{title[:50]}.mp3")
    sent = await bot.send_audio(chat_id=chat_id, audio=input_file, title=title, duration=duration)
    file_id = sent.audio.file_id
    await bot.delete_message(chat_id=chat_id, message_id=sent.message_id)
    return file_id


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


# ── Delete ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("music:del:"))
async def music_delete(callback: CallbackQuery):
    track_id = int(callback.data.split(":")[2])
    async with SessionLocal() as s:
        track = await s.get(MusicTrack, track_id)
        if track:
            await s.delete(track)
            await s.commit()

    tracks = await _get_tracks()
    text = "🎵 *Музыка*\n\n" + ("Выберите трек:" if tracks else "_Треков нет._")
    await callback.message.edit_text(text, reply_markup=music_list_kb(tracks), parse_mode="Markdown")
    await callback.answer("🗑 Удалено")
