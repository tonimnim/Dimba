from datetime import datetime, timedelta, timezone

from app.extensions import ma
from app.models.match import Match, MatchStatus
from marshmallow import Schema, fields, validate

MATCH_DURATION = timedelta(minutes=90)


def _can_submit_result(match):
    """True if the match is SCHEDULED and kick-off + 90 min has passed.
    Note: admins can override this on the backend, but coaches cannot."""
    if match.status != MatchStatus.SCHEDULED:
        return False
    if not match.match_date:
        return True  # no date set — allow submission
    kickoff = match.match_date.replace(tzinfo=timezone.utc) if match.match_date.tzinfo is None else match.match_date
    return datetime.now(timezone.utc) >= kickoff + MATCH_DURATION


def _result_submit_opens_at(match):
    """ISO timestamp of when result submission opens (kick-off + 90 min)."""
    if not match.match_date:
        return None
    kickoff = match.match_date.replace(tzinfo=timezone.utc) if match.match_date.tzinfo is None else match.match_date
    return (kickoff + MATCH_DURATION).isoformat()


class MatchSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Match
        load_instance = True
        include_fk = True

    status = fields.Function(lambda obj: obj.status.value if obj.status else None)
    stage = fields.Function(lambda obj: obj.stage.value if obj.stage else None)
    can_submit_result = fields.Function(lambda obj: _can_submit_result(obj), dump_only=True)
    result_submit_opens_at = fields.Function(lambda obj: _result_submit_opens_at(obj), dump_only=True)
    home_team = ma.Nested("TeamSchema", only=("id", "name"), dump_only=True)
    away_team = ma.Nested("TeamSchema", only=("id", "name"), dump_only=True)
    penalty_winner = ma.Nested("TeamSchema", only=("id", "name"), dump_only=True)
    competition = ma.Nested("CompetitionSchema", only=("id", "name"), dump_only=True)
    submitted_by = ma.Nested("UserSchema", only=("id", "first_name", "last_name"), dump_only=True)
    confirmed_by = ma.Nested("UserSchema", only=("id", "first_name", "last_name"), dump_only=True)


class CreateMatchSchema(Schema):
    competition_id = fields.Integer(required=True)
    season_id = fields.Integer(required=True)
    home_team_id = fields.Integer(required=True)
    away_team_id = fields.Integer(required=True)
    match_date = fields.DateTime(load_default=None)
    venue = fields.String(load_default=None, validate=validate.Length(max=200))


class SubmitResultSchema(Schema):
    home_score = fields.Integer(required=True, validate=validate.Range(min=0))
    away_score = fields.Integer(required=True, validate=validate.Range(min=0))


class GenerateFixturesSchema(Schema):
    start_date = fields.Date(required=True)
    interval_days = fields.Integer(load_default=7, validate=validate.Range(min=1))
    end_date = fields.Date(load_default=None)


class GenerateCupDrawSchema(Schema):
    start_date = fields.Date(required=True)


class GenerateKnockoutSchema(Schema):
    start_date = fields.Date(required=True)
    two_legged = fields.Boolean(load_default=True)
