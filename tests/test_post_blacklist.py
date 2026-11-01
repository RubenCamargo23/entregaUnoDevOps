import uuid

from app.models import Blacklist

APP_UUID = str(uuid.uuid4())


def test_body_must_be_json(client, headers):
    res = client.post("/blacklists", data="email=a@b.com", headers=headers)
    assert res.status_code == 400
    assert res.get_json()["msg"] == "El cuerpo de la solicitud debe ser JSON"


def test_email_is_normalized(app, client, headers):
    res = client.post("/blacklists", json={"email": "  Cliente@Example.COM ", "app_uuid": APP_UUID}, headers=headers)
    assert res.status_code == 201
    assert res.get_json()["blacklist"]["email"] == "cliente@example.com"


def test_unknown_fields_are_ignored(client, headers):
    body = {"email": "extra@example.com", "app_uuid": APP_UUID, "campo_desconocido": "x"}
    assert client.post("/blacklists", json=body, headers=headers).status_code == 201


def test_ip_without_proxy_uses_remote_addr(app, client, headers):
    client.post(
        "/blacklists",
        json={"email": "directo@example.com", "app_uuid": APP_UUID},
        headers=headers,
        environ_base={"REMOTE_ADDR": "190.10.20.30"},
    )
    with app.app_context():
        assert Blacklist.query.filter_by(email="directo@example.com").one().request_ip == "190.10.20.30"


def test_reason_max_length_is_accepted(client, headers):
    body = {"email": "largo@example.com", "app_uuid": APP_UUID, "blocked_reason": "x" * 255}
    assert client.post("/blacklists", json=body, headers=headers).status_code == 201


def test_invalid_token_is_rejected(client):
    res = client.post(
        "/blacklists",
        json={"email": "a@example.com", "app_uuid": APP_UUID},
        headers={"Authorization": "Bearer token-invalido"},
    )
    assert res.status_code == 401
