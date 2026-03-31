from __future__ import annotations

import os


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    AUTH_SIGNUP_ENABLED = os.environ.get("AUTH_SIGNUP_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    AUTH_SHOW_RESET_LINKS = os.environ.get("AUTH_SHOW_RESET_LINKS", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    RESET_PASSWORD_TOKEN_MAX_AGE = int(os.environ.get("RESET_PASSWORD_TOKEN_MAX_AGE", "3600"))
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://explor:explor@localhost:5432/explor",
        )
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite+pysqlite:///:memory:"
