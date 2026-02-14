from app.extensions import db
from datetime import datetime, timezone
import enum


class CompetitionType(enum.Enum):
    REGIONAL = "regional"
    NATIONAL = "national"
    CUP = "cup"
    SUPER = "super"
    COUNTY = "county"


class CompetitionCategory(enum.Enum):
    MEN = "men"
    WOMEN = "women"


competition_teams = db.Table(
    "competition_teams",
    db.Column(
        "competition_id",
        db.Integer,
        db.ForeignKey("competitions.id"),
        primary_key=True,
    ),
    db.Column(
        "team_id", db.Integer, db.ForeignKey("teams.id"), primary_key=True
    ),
)


class Competition(db.Model):
    __tablename__ = "competitions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.Enum(CompetitionType), nullable=False)
    category = db.Column(db.Enum(CompetitionCategory), nullable=False)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey("regions.id"), nullable=True)
    county_id = db.Column(db.Integer, db.ForeignKey("counties.id"), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    county = db.relationship("County", backref="competitions")
    teams = db.relationship(
        "Team", secondary=competition_teams, backref="competitions", lazy="dynamic"
    )
    matches = db.relationship("Match", backref="competition", lazy="dynamic")
    standings = db.relationship("Standing", backref="competition", lazy="dynamic")

    def __repr__(self):
        return f"<Competition {self.name}>"
