from app.extensions import db
from datetime import datetime, timezone


class Region(db.Model):
    __tablename__ = "regions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(3), nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    counties = db.relationship("County", backref="region", lazy="dynamic")
    teams = db.relationship("Team", backref="region", lazy="dynamic")
    competitions = db.relationship("Competition", backref="region", lazy="dynamic")

    def __repr__(self):
        return f"<Region {self.name}>"
