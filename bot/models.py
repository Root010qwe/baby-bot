from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, BigInteger
)
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///data/baby.db"

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)


class SleepLog(Base):
    __tablename__ = "sleep_logs"
    id = Column(Integer, primary_key=True)
    # start=засыпание, end=пробуждение
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    # True = ночной сон (из опросника)
    is_night = Column(Boolean, default=False)
    note = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class NightReport(Base):
    """Утренний опросник о ночи."""
    __tablename__ = "night_reports"
    id = Column(Integer, primary_key=True)
    date = Column(String(10), unique=True, nullable=False)  # YYYY-MM-DD
    wakeups = Column(Integer, nullable=False)          # сколько раз просыпался
    awake_minutes = Column(Integer, nullable=False)    # суммарно не спал (мин)
    quality = Column(String(20), nullable=False)       # calm / medium / hard
    created_at = Column(DateTime, default=datetime.utcnow)


class Setting(Base):
    """Key-value store for bot settings (notifications etc.)."""
    __tablename__ = "settings"
    key = Column(String(50), primary_key=True)
    value = Column(String(200), nullable=False)


# Default settings applied on first run
DEFAULT_SETTINGS = {
    "night_report_enabled": "1",
    "night_report_hour": "8",
    "night_report_minute": "30",
    "evening_digest_enabled": "1",
    "evening_digest_hour": "21",
    "evening_digest_minute": "0",
    "weight_reminder_enabled": "1",
    "weight_reminder_hour": "9",
    "weight_reminder_minute": "0",
}


class WeightLog(Base):
    __tablename__ = "weight_logs"
    id = Column(Integer, primary_key=True)
    grams = Column(Integer, nullable=False)
    measured_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class MusicTrack(Base):
    __tablename__ = "music_tracks"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    url = Column(Text, nullable=False)
    # file_id после первой загрузки в Telegram
    file_id = Column(String(200), nullable=True)
    duration = Column(Integer, nullable=True)  # секунды
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # seed default settings if missing
    async with SessionLocal() as s:
        for key, value in DEFAULT_SETTINGS.items():
            existing = await s.get(Setting, key)
            if existing is None:
                s.add(Setting(key=key, value=value))
        await s.commit()


async def get_setting(key: str) -> str:
    async with SessionLocal() as s:
        row = await s.get(Setting, key)
        return row.value if row else DEFAULT_SETTINGS.get(key, "")


async def set_setting(key: str, value: str):
    async with SessionLocal() as s:
        row = await s.get(Setting, key)
        if row:
            row.value = value
        else:
            s.add(Setting(key=key, value=value))
        await s.commit()
