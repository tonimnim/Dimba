from app.extensions import db
from datetime import datetime, timezone
import enum


class TeamStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class TeamCategory(enum.Enum):
    MEN = "men"
    WOMEN = "women"


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    county_id = db.Column(db.Integer, db.ForeignKey("counties.id"), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey("regions.id"), nullable=False)
    category = db.Column(db.Enum(TeamCategory), nullable=False)
    status = db.Column(
        db.Enum(TeamStatus), nullable=False, default=TeamStatus.PENDING
    )
    logo_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    players = db.relationship("Player", backref="team", lazy="dynamic")
    home_matches = db.relationship(
        "Match", foreign_keys="Match.home_team_id", backref="home_team", lazy="dynamic"
    )
    away_matches = db.relationship(
        "Match", foreign_keys="Match.away_team_id", backref="away_team", lazy="dynamic"
    )
    standings = db.relationship("Standing", backref="team", lazy="dynamic")

    def __repr__(self):
        return f"<Team {self.name}>"
