from app.extensions import ma
from app.models.county import County


class CountySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = County
        load_instance = True
        include_fk = True

    region = ma.Nested("RegionSchema", exclude=("counties",), dump_only=True)
