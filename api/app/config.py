import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "growth.db")))
APP_ORIGIN = os.getenv("APP_ORIGIN", "http://localhost:3000").rstrip("/")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").lower()
MAIL_HOST = os.getenv("MAIL_HOST", "")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USER = os.getenv("MAIL_USER", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_FROM = os.getenv("MAIL_FROM", "")
MAIL_TLS = os.getenv("MAIL_TLS", "true").lower() == "true"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
AI_DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "10"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
