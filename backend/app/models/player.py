from app.extensions import db
from datetime import datetime, timezone
import enum


class PlayerPosition(enum.Enum):
    GK = "goalkeeper"
    DEF = "defender"
    MID = "midfielder"
    FWD = "forward"


class Player(db.Model):
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    position = db.Column(db.Enum(PlayerPosition), nullable=False)
    jersey_number = db.Column(db.Integer, nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    photo_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    transfers = db.relationship("Transfer", backref="player", lazy="dynamic",
                                foreign_keys="Transfer.player_id")

    def __repr__(self):
        return f"<Player {self.first_name} {self.last_name}>"
