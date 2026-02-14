from app.extensions import ma
from app.models.competition import Competition
from marshmallow import Schema, fields, validate


class CompetitionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Competition
        load_instance = True
        include_fk = True

    type = fields.Function(lambda obj: obj.type.value if obj.type else None)
    category = fields.Function(lambda obj: obj.category.value if obj.category else None)
    region = ma.Nested("RegionSchema", exclude=("counties",), dump_only=True)
    county = ma.Nested("CountySchema", dump_only=True)
    season = ma.Nested("SeasonSchema", dump_only=True)


class CreateCompetitionSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    type = fields.String(
        required=True, validate=validate.OneOf(["regional", "national", "cup", "super", "county"])
    )
    category = fields.String(
        required=True, validate=validate.OneOf(["men", "women"])
    )
    season_id = fields.Integer(required=True)
    region_id = fields.Integer(load_default=None)
    county_id = fields.Integer(load_default=None)


class UpdateCompetitionSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=200))
    type = fields.String(validate=validate.OneOf(["regional", "national", "cup", "super", "county"]))
    category = fields.String(validate=validate.OneOf(["men", "women"]))
