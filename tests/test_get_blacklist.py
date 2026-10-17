import uuid

from app.models import Blacklist, db


def add_entry(app, email, reason="Fraude"):
    with app.app_context():
        db.session.add(
            Blacklist(email=email, app_uuid=str(uuid.uuid4()), blocked_reason=reason, request_ip="127.0.0.1")
        )
        db.session.commit()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_email_in_blacklist(app, client, headers):
    add_entry(app, "cliente@example.com", "Fraude")
    res = client.get("/blacklists/cliente@example.com", headers=headers)
    assert res.status_code == 200
    assert res.get_json() == {"email": "cliente@example.com", "is_blacklisted": True, "blocked_reason": "Fraude"}


def test_email_lookup_is_case_insensitive(app, client, headers):
    add_entry(app, "cliente@example.com")
    res = client.get("/blacklists/CLIENTE@Example.com", headers=headers)
    assert res.get_json()["is_blacklisted"] is True


def test_reason_can_be_empty(app, client, headers):
    add_entry(app, "sin.motivo@example.com", reason=None)
    res = client.get("/blacklists/sin.motivo@example.com", headers=headers)
    assert res.get_json() == {"email": "sin.motivo@example.com", "is_blacklisted": True, "blocked_reason": None}


def test_email_not_in_blacklist(client, headers):
    res = client.get("/blacklists/limpio@example.com", headers=headers)
    assert res.status_code == 200
    assert res.get_json() == {"email": "limpio@example.com", "is_blacklisted": False, "blocked_reason": None}


def test_requires_token(client):
    res = client.get("/blacklists/cliente@example.com")
    assert res.status_code == 401
    assert res.get_json()["msg"] == "Token de autorizacion requerido"


def test_invalid_token(client):
    res = client.get("/blacklists/cliente@example.com", headers={"Authorization": "Bearer token-invalido"})
    assert res.status_code == 401
    assert res.get_json()["msg"] == "Token de autorizacion invalido"


def test_token_signed_with_other_key(client):
    # JWT con firma de otra clave
    forged = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ4In0."
        "c2lnbmF0dXJhLWZhbHNhLWNvbi1vdHJhLWNsYXZl"
    )
    res = client.get("/blacklists/cliente@example.com", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401
