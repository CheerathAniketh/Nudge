from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert "x-request-id" in resp.headers


def test_me_requires_token(client: TestClient) -> None:
    resp = client.get("/v1/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
