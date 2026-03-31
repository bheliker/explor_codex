from __future__ import annotations

from typing import Any

from flask import current_app

from app.models import User


def send_password_reset_email(*, user: User, reset_url: str) -> dict[str, str]:
    message = {
        "to": user.email,
        "from": current_app.config["EMAIL_FROM"],
        "subject": "explor_codex password reset",
        "text": (
            f"Hello {user.display_name},\n\n"
            f"Use this link to reset your password:\n{reset_url}\n\n"
            "If you did not request this, you can ignore this message."
        ),
        "reset_url": reset_url,
    }
    _deliver_message(message)
    return message


def latest_outbox_message() -> dict[str, str] | None:
    outbox = _outbox()
    if not outbox:
        return None
    message = outbox[-1]
    return message if isinstance(message, dict) else None


def _deliver_message(message: dict[str, str]) -> None:
    mode = current_app.config["EMAIL_DELIVERY_MODE"]
    if mode == "memory":
        _outbox().append(message)
        return
    raise RuntimeError(f"Unsupported EMAIL_DELIVERY_MODE: {mode}")


def _outbox() -> list[dict[str, str] | Any]:
    return current_app.extensions.setdefault("email_outbox", [])
