"""Thin async helpers on top of SQLAlchemy session."""
from contextlib import asynccontextmanager
from bot.models import SessionLocal


@asynccontextmanager
async def session_scope():
    async with SessionLocal() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise
