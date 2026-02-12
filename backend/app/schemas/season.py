from app.extensions import ma
from app.models.season import Season
from marshmallow import Schema, fields, validate


class SeasonSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Season
        load_instance = True
        include_fk = True


class CreateSeasonSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    year = fields.Integer(required=True, validate=validate.Range(min=2000, max=2100))
    is_active = fields.Boolean(load_default=False)


class UpdateSeasonSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=100))
    year = fields.Integer(validate=validate.Range(min=2000, max=2100))
    is_active = fields.Boolean()
