import uuid

import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.config import TestConfig
from app.models import Blacklist, db


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def headers(app):
    with app.app_context():
        token = create_access_token(identity="test", expires_delta=False)
    return {"Authorization": f"Bearer {token}"}


def payload(**overrides):
    body = {"email": "cliente@example.com", "app_uuid": str(uuid.uuid4()), "blocked_reason": "Spam"}
    body.update(overrides)
    return body


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_post_requires_token(client):
    assert client.post("/blacklists", json=payload()).status_code == 401


def test_get_requires_token(client):
    assert client.get("/blacklists/cliente@example.com").status_code == 401


def test_invalid_token(client):
    res = client.get("/blacklists/a@b.com", headers={"Authorization": "Bearer abc"})
    assert res.status_code == 401


def test_add_email_stores_ip_and_date(client, headers, app):
    res = client.post(
        "/blacklists", json=payload(), headers={**headers, "X-Forwarded-For": "200.1.2.3, 10.0.0.1"}
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["blacklist"]["email"] == "cliente@example.com"
    with app.app_context():
        entry = Blacklist.query.filter_by(email="cliente@example.com").one()
        assert entry.request_ip == "200.1.2.3"
        assert entry.created_at is not None


def test_add_duplicate_email(client, headers):
    client.post("/blacklists", json=payload(), headers=headers)
    res = client.post("/blacklists", json=payload(email="CLIENTE@example.com"), headers=headers)
    assert res.status_code == 409


def test_reason_is_optional(client, headers):
    body = payload()
    del body["blocked_reason"]
    assert client.post("/blacklists", json=body, headers=headers).status_code == 201


@pytest.mark.parametrize(
    "override",
    [
        {"email": "no-es-email"},
        {"app_uuid": "123"},
        {"app_uuid": None},
        {"blocked_reason": "x" * 256},
    ],
)
def test_validation_errors(client, headers, override):
    res = client.post("/blacklists", json=payload(**override), headers=headers)
    assert res.status_code == 400
    assert "errors" in res.get_json()


def test_missing_required_fields(client, headers):
    res = client.post("/blacklists", json={}, headers=headers)
    assert res.status_code == 400
    assert set(res.get_json()["errors"]) == {"email", "app_uuid"}


def test_check_email(client, headers):
    client.post("/blacklists", json=payload(blocked_reason="Fraude"), headers=headers)
    res = client.get("/blacklists/cliente@example.com", headers=headers)
    assert res.status_code == 200
    assert res.get_json() == {"email": "cliente@example.com", "is_blacklisted": True, "blocked_reason": "Fraude"}

    res = client.get("/blacklists/otro@example.com", headers=headers)
    assert res.get_json()["is_blacklisted"] is False
