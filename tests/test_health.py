import pytest


@pytest.mark.parametrize("path", ["/health", "/"])
def test_health_responds_ok(client, path):
    res = client.get(path)
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_health_reports_version(client):
    body = client.get("/health").get_json()
    assert isinstance(body["version"], str) and body["version"]


def test_health_does_not_require_token(client):
    res = client.get("/health", headers={"Authorization": "Bearer token-invalido"})
    assert res.status_code == 200
