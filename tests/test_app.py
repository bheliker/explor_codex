from flask import Flask
from flask.testing import FlaskClient

from app.config import Config, TestConfig


def test_index_route(client: FlaskClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {"message": "explor_codex is ready"}


def test_health_route(client: FlaskClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_app_factory_enables_testing_config(app: Flask) -> None:
    assert app.testing is True


def test_app_registers_sqlalchemy_extension(app: Flask) -> None:
    assert "sqlalchemy" in app.extensions


def test_test_config_uses_in_memory_sqlite() -> None:
    assert TestConfig.SQLALCHEMY_DATABASE_URI == "sqlite+pysqlite:///:memory:"


def test_config_normalizes_legacy_postgres_url() -> None:
    assert Config.SQLALCHEMY_DATABASE_URI.startswith("postgresql+psycopg://")
