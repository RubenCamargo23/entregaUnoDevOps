from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models import Blacklist, db
from app.schemas import blacklist_create_schema, blacklist_schema


def client_ip():
    # Detras del balanceador de Beanstalk la IP real llega en X-Forwarded-For ("cliente, proxy1, ...").
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


class HealthResource(Resource):
    def get(self):
        from app import APP_VERSION

        return {"status": "ok", "version": APP_VERSION}, 200


class BlacklistResource(Resource):
    @jwt_required()
    def post(self):
        payload = request.get_json(silent=True)
        if payload is None:
            return {"msg": "El cuerpo de la solicitud debe ser JSON"}, 400
        try:
            data = blacklist_create_schema.load(payload)
        except ValidationError as err:
            return {"msg": "Datos invalidos, el email no pudo ser agregado", "errors": err.messages}, 400

        entry = Blacklist(
            email=data["email"],
            app_uuid=str(data["app_uuid"]),
            blocked_reason=data["blocked_reason"],
            request_ip=client_ip(),
        )
        db.session.add(entry)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"msg": f"El email {data['email']} ya se encuentra en la lista negra global"}, 409

        return {
            "msg": f"El email {entry.email} fue agregado a la lista negra global",
            "blacklist": blacklist_schema.dump(entry),
        }, 201


class BlacklistCheckResource(Resource):
    @jwt_required()
    def get(self, email):
        email = email.strip().lower()
        entry = Blacklist.query.filter_by(email=email).first()
        if entry is None:
            return {"email": email, "is_blacklisted": False, "blocked_reason": None}, 200
        return {"email": email, "is_blacklisted": True, "blocked_reason": entry.blocked_reason}, 200
