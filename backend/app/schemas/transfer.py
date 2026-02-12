from app.extensions import ma
from app.models.transfer import Transfer
from marshmallow import Schema, fields, validate


class TransferSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Transfer
        load_instance = True
        include_fk = True

    status = fields.Function(lambda obj: obj.status.value if obj.status else None)
    player = ma.Nested("PlayerSchema", only=("id", "first_name", "last_name"), dump_only=True)
    from_team = ma.Nested("TeamSchema", only=("id", "name"), dump_only=True)
    to_team = ma.Nested("TeamSchema", only=("id", "name"), dump_only=True)
    initiated_by = ma.Nested("UserSchema", only=("id", "first_name", "last_name"), dump_only=True)
    approved_by = ma.Nested("UserSchema", only=("id", "first_name", "last_name"), dump_only=True)


class CreateTransferSchema(Schema):
    player_id = fields.Integer(required=True)
    from_team_id = fields.Integer(required=True)
    to_team_id = fields.Integer(required=True)
    fee = fields.Decimal(load_default=0, validate=validate.Range(min=0))
    reason = fields.String(load_default=None, validate=validate.Length(max=500))
