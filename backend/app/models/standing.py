from app.extensions import db
from datetime import datetime, timezone


class Standing(db.Model):
    __tablename__ = "standings"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    competition_id = db.Column(
        db.Integer, db.ForeignKey("competitions.id"), nullable=False
    )
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    played = db.Column(db.Integer, nullable=False, default=0)
    won = db.Column(db.Integer, nullable=False, default=0)
    drawn = db.Column(db.Integer, nullable=False, default=0)
    lost = db.Column(db.Integer, nullable=False, default=0)
    goals_for = db.Column(db.Integer, nullable=False, default=0)
    goals_against = db.Column(db.Integer, nullable=False, default=0)
    goal_difference = db.Column(db.Integer, nullable=False, default=0)
    points = db.Column(db.Integer, nullable=False, default=0)
    group_name = db.Column(db.String(10), nullable=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.UniqueConstraint("team_id", "competition_id", "season_id",
                            name="uq_standing_team_comp_season"),
    )

    def __repr__(self):
        return f"<Standing {self.team_id} - {self.points}pts>"
