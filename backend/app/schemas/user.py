from app.extensions import ma
from app.models.user import User
from marshmallow import fields, validate, Schema


class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        include_fk = True
        exclude = ("password_hash",)

    role = fields.Function(lambda obj: obj.role.value if obj.role else None)
    team = ma.Nested("TeamSchema", only=("id", "name"), dump_only=True)
    county = ma.Nested("CountySchema", only=("id", "name"), dump_only=True)


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8))
    first_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    role = fields.String(
        required=True,
        validate=validate.OneOf(["super_admin", "county_admin", "coach", "player"]),
    )
    team_id = fields.Integer(load_default=None)
    county_id = fields.Integer(load_default=None)
