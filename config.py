"""Configuration centralisée — chargement depuis les variables d'environnement."""
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


DEBUG = _bool_env("DEBUG", default=False)
TESTING = _bool_env("TESTING", default=False)

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    # Développement uniquement — la prod doit définir SECRET_KEY (≥ 32 caractères)
    SECRET_KEY = os.environ.get("SECRET_KEY_DEV_FALLBACK", "dev-insecure-key-change-in-production-32chars!!")

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", default=False)
SESSION_COOKIE_SAMESITE = "Lax"
PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
MAX_CONTENT_LENGTH = 16 * 1024 * 1024
WTF_CSRF_TIME_LIMIT = 3600
PROPAGATE_EXCEPTIONS = False

# Premier compte admin : uniquement si INITIAL_ADMIN_PASSWORD est défini (jamais de mot de passe codé en dur)
INITIAL_ADMIN_EMAIL = os.environ.get("INITIAL_ADMIN_EMAIL", "admin@argan.ma")
INITIAL_ADMIN_PASSWORD = os.environ.get("INITIAL_ADMIN_PASSWORD")
