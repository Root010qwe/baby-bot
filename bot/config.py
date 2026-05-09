import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = {int(x.strip()) for x in _raw.split(",") if x.strip()}

TZ: str = os.getenv("TZ", "Asia/Almaty")
BABY_BIRTHDATE: str = os.getenv("BABY_BIRTHDATE", "2025-04-09")
BABY_NAME: str = os.getenv("BABY_NAME", "Малыш")
