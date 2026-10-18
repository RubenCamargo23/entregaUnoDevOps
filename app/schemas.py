from marshmallow import EXCLUDE, Schema, fields, pre_load, validate

from app.models import Blacklist, ma


class BlacklistCreateSchema(Schema):
    """Valida el cuerpo del POST /blacklists."""

    class Meta:
        unknown = EXCLUDE

    email = fields.Email(required=True, validate=validate.Length(max=255))
    app_uuid = fields.UUID(required=True)
    blocked_reason = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=255))

    @pre_load
    def normalize(self, data, **kwargs):
        if isinstance(data, dict) and isinstance(data.get("email"), str):
            data = {**data, "email": data["email"].strip().lower()}
        return data


class BlacklistSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Blacklist
        load_instance = False


blacklist_create_schema = BlacklistCreateSchema()
blacklist_schema = BlacklistSchema()
