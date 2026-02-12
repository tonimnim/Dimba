from app.extensions import ma
from app.models.standing import Standing


class StandingSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Standing
        load_instance = True
        include_fk = True

    team = ma.Nested("TeamSchema", only=("id", "name"), dump_only=True)
    competition = ma.Nested("CompetitionSchema", only=("id", "name"), dump_only=True)
