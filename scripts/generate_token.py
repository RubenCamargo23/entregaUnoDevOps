"""Genera el Bearer token estatico (no expira) firmado con JWT_SECRET_KEY.

Uso:
    JWT_SECRET_KEY=<misma clave configurada en Beanstalk> python scripts/generate_token.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402
from flask_jwt_extended import JWTManager, create_access_token  # noqa: E402

from app.config import Config  # noqa: E402

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = Config.JWT_SECRET_KEY
JWTManager(app)

with app.app_context():
    print(create_access_token(identity="devops-blacklist-client", expires_delta=False))
