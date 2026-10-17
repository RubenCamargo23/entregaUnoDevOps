import os

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_restful import Api

from app.config import Config
from app.models import db, ma


def _read_version():
    # build_bundle.sh escribe el archivo VERSION dentro del paquete que se sube a Beanstalk
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return "dev"


APP_VERSION = _read_version()


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    ma.init_app(app)
    jwt = JWTManager(app)
    _register_jwt_errors(jwt)

    from app.resources import BlacklistCheckResource, HealthResource

    api = Api(app)
    api.add_resource(HealthResource, "/", "/health")
    api.add_resource(BlacklistCheckResource, "/blacklists/<string:email>")

    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:  # Varias instancias pueden intentar crear la tabla al tiempo
            app.logger.warning("db.create_all() fallo: %s", exc)

    return app


def _register_jwt_errors(jwt):
    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify({"msg": "Token de autorizacion requerido", "detail": reason}), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify({"msg": "Token de autorizacion invalido", "detail": reason}), 401

    @jwt.expired_token_loader
    def expired_token(_header, _payload):
        return jsonify({"msg": "Token de autorizacion expirado"}), 401
