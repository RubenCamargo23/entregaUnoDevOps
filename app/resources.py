from flask_jwt_extended import jwt_required
from flask_restful import Resource

from app.models import Blacklist


class HealthResource(Resource):
    def get(self):
        from app import APP_VERSION

        return {"status": "ok", "version": APP_VERSION}, 200


class BlacklistCheckResource(Resource):
    @jwt_required()
    def get(self, email):
        email = email.strip().lower()
        entry = Blacklist.query.filter_by(email=email).first()
        if entry is None:
            return {"email": email, "is_blacklisted": False, "blocked_reason": None}, 200
        return {"email": email, "is_blacklisted": True, "blocked_reason": entry.blocked_reason}, 200
