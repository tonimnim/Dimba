from app.extensions import db
from datetime import datetime, timezone


class Season(db.Model):
    __tablename__ = "seasons"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    competitions = db.relationship("Competition", backref="season", lazy="dynamic")
    matches = db.relationship("Match", backref="season", lazy="dynamic")
    standings = db.relationship("Standing", backref="season", lazy="dynamic")

    def __repr__(self):
        return f"<Season {self.name}>"
