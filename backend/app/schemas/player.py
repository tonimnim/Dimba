from app.extensions import ma
from app.models.player import Player
from marshmallow import Schema, fields, validate


class PlayerSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Player
        load_instance = True
        include_fk = True

    position = fields.Function(lambda obj: obj.position.value if obj.position else None)
    team = ma.Nested("TeamSchema", only=("id", "name"), dump_only=True)


class CreatePlayerSchema(Schema):
    first_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    position = fields.String(
        required=True,
        validate=validate.OneOf(["goalkeeper", "defender", "midfielder", "forward"]),
    )
    jersey_number = fields.Integer(
        load_default=None, validate=validate.Range(min=1, max=99)
    )
    team_id = fields.Integer(load_default=None)
    date_of_birth = fields.Date(load_default=None)
    photo_url = fields.String(load_default=None, validate=validate.Length(max=500), allow_none=True)


class UpdatePlayerSchema(Schema):
    first_name = fields.String(validate=validate.Length(min=1, max=100))
    last_name = fields.String(validate=validate.Length(min=1, max=100))
    position = fields.String(
        validate=validate.OneOf(["goalkeeper", "defender", "midfielder", "forward"])
    )
    jersey_number = fields.Integer(validate=validate.Range(min=1, max=99), allow_none=True)
    photo_url = fields.String(validate=validate.Length(max=500), allow_none=True)
