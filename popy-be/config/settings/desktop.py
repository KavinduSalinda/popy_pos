"""Settings for the packaged Windows app.

The Electron supervisor starts a private MySQL and passes connection details
through the environment. SQLite is not used here.
"""

import os
from pathlib import Path

import pymysql

pymysql.install_as_MySQLdb()

from .base import *  # noqa: E402,F403


def desktop_setting(name: str, default: str | None = None) -> str:
    """Supervisor environment wins over a .env file sitting next to the code."""
    value = os.environ.get(name)
    if value:
        return value
    if default is None:
        return config(name)  # noqa: F405
    return config(name, default=default)  # noqa: F405


DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": desktop_setting("DB_NAME", "popy"),
        "USER": desktop_setting("DB_USER", "popy"),
        "PASSWORD": desktop_setting("DB_PASSWORD"),
        "HOST": desktop_setting("DB_HOST", "127.0.0.1"),
        "PORT": desktop_setting("DB_PORT", "3307"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

_media = desktop_setting("POPY_MEDIA_ROOT", "")
MEDIA_ROOT = Path(_media) if _media else BASE_DIR / "media"  # noqa: F405
MEDIA_URL = "/media/"

_static = desktop_setting("POPY_STATIC_ROOT", "")
if _static:
    STATIC_ROOT = Path(_static)  # noqa: F405

_frontend = desktop_setting("POPY_FRONTEND_DIST", "")
if _frontend:
    WHITENOISE_ROOT = str(_frontend)
    WHITENOISE_INDEX_FILE = "index.html"

# Attendance and the other Pro features stay on. Email and SMS stay on the cloud.
NOTIFICATIONS_ENABLED = False

_security_idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")  # noqa: F405
MIDDLEWARE = [  # noqa: F405
    *MIDDLEWARE[: _security_idx + 1],  # noqa: F405
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[_security_idx + 1 :],  # noqa: F405
]
