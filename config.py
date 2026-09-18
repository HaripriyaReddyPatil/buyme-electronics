import os
import secrets
from datetime import timedelta


class Config:
    # Prefer an environment variable in deployment.
    # A random development key is generated locally if none is provided.
    SECRET_KEY = os.environ.get(
        "BUYME_SECRET_KEY",
        secrets.token_hex(32),
    )

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "BUYME_DATABASE_URI",
        "sqlite:///buyme.db",
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Safer session configuration
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Keep False locally so http://localhost works.
    # Set BUYME_COOKIE_SECURE=true in HTTPS production.
    SESSION_COOKIE_SECURE = (
        os.environ.get(
            "BUYME_COOKIE_SECURE",
            "false",
        ).lower()
        == "true"
    )

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
