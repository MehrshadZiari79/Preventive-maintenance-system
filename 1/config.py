import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def get_app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_db_path() -> Path:
    env_path = os.environ.get("DB_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return get_app_dir() / "pm_database.db"


APP_NAME = "سیستم نگهداری پیشگیرانه"
APP_VERSION = "1.0.0"

DB_PATH = get_db_path()
DATABASE_URL = f"sqlite:///{DB_PATH}"

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
