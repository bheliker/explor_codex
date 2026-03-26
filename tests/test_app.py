from flask import Flask
from flask.testing import FlaskClient


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
