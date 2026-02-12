from app.extensions import ma
from app.models.team import Team
from marshmallow import Schema, fields, validate


class TeamSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Team
        load_instance = True
        include_fk = True

    category = fields.Function(lambda obj: obj.category.value if obj.category else None)
    status = fields.Function(lambda obj: obj.status.value if obj.status else None)
    county = ma.Nested("CountySchema", exclude=("region",), dump_only=True)
    region = ma.Nested("RegionSchema", exclude=("counties",), dump_only=True)


class CreateTeamSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    county_id = fields.Integer(required=True)
    category = fields.String(
        required=True, validate=validate.OneOf(["men", "women"])
    )


class UpdateTeamSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=200))
    status = fields.String(validate=validate.OneOf(["pending", "active", "suspended"]))
    logo_url = fields.String(validate=validate.Length(max=500), load_default=None, allow_none=True)
