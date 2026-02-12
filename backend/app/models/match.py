from app.extensions import db
from datetime import datetime, timezone
import enum


class MatchStage(enum.Enum):
    SUPER = "super"
    LEAGUE = "league"
    GROUP = "group"
    ROUND_1 = "round_1"
    ROUND_2 = "round_2"
    ROUND_3 = "round_3"
    ROUND_OF_16 = "round_of_16"
    QUARTER_FINAL = "quarter_final"
    SEMI_FINAL = "semi_final"
    FINAL = "final"


class MatchStatus(enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CONFIRMED = "confirmed"


class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(
        db.Integer, db.ForeignKey("competitions.id"), nullable=False
    )
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    away_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    match_date = db.Column(db.DateTime, nullable=True)
    venue = db.Column(db.String(200), nullable=True)
    status = db.Column(
        db.Enum(MatchStatus), nullable=False, default=MatchStatus.SCHEDULED
    )
    submitted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    confirmed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    matchday = db.Column(db.Integer, nullable=True)
    stage = db.Column(db.Enum(MatchStage), nullable=True)
    group_name = db.Column(db.String(10), nullable=True)
    leg = db.Column(db.Integer, nullable=True)
    round_number = db.Column(db.Integer, nullable=True)
    bracket_position = db.Column(db.Integer, nullable=True)
    penalty_winner_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    penalty_winner = db.relationship("Team", foreign_keys=[penalty_winner_id])
    submitted_by = db.relationship(
        "User", foreign_keys=[submitted_by_id], backref="submitted_matches"
    )
    confirmed_by = db.relationship(
        "User", foreign_keys=[confirmed_by_id], backref="confirmed_matches"
    )

    def __repr__(self):
        return f"<Match {self.home_team_id} vs {self.away_team_id}>"
