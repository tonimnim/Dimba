from app.extensions import ma
from app.models.region import Region


class RegionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Region
        load_instance = True
        include_fk = True

    counties = ma.Nested("CountySchema", many=True, exclude=("region",), dump_only=True)
