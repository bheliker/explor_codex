from app import app


def test_index_route() -> None:
    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {"message": "explor_codex is ready"}


def test_health_route() -> None:
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
