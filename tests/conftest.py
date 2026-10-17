import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.config import TestConfig
from app.models import db


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
    """Cabecera Authorization con un Bearer token valido."""
    with app.app_context():
        token = create_access_token(identity="test", expires_delta=False)
    return {"Authorization": f"Bearer {token}"}
