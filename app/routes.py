from __future__ import annotations

from flask import Blueprint

bp = Blueprint("core", __name__)


@bp.get("/")
def index() -> tuple[dict[str, str], int]:
    return {"message": "explor_codex is ready"}, 200


@bp.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200
