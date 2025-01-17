from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_compile_empty_fails():
    response = client.post("/compile", json={})
    assert response.status_code == 422
