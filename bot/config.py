import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

TZ: str = os.getenv("TZ", "Asia/Almaty")
BABY_BIRTHDATE: str = os.getenv("BABY_BIRTHDATE", "2026-03-31")
BABY_NAME: str = os.getenv("BABY_NAME", "Феликс")

# ── Roles ─────────────────────────────────────────────────────────────────────
ADMIN_IDS: set[int] = {904170083}          # ты — полный доступ + музыкальные запросы
MOM_IDS:   set[int] = {944466833}          # мама — полный доступ
DAD_IDS:   set[int] = {60646039}           # папа — упрощённый вид

ALLOWED_USERS: set[int] = ADMIN_IDS | MOM_IDS | DAD_IDS


def get_role(user_id: int) -> str:
    if user_id in ADMIN_IDS:
        return "admin"
    if user_id in MOM_IDS:
        return "mom"
    if user_id in DAD_IDS:
        return "dad"
    return "unknown"


def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_full_access(user_id: int) -> bool:
    """Mom and admin get full access; dad gets simplified view."""
    return user_id in ADMIN_IDS or user_id in MOM_IDS
