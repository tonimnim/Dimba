from app.extensions import db
from datetime import datetime, timezone


class County(db.Model):
    __tablename__ = "counties"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.Integer, nullable=False, unique=True)
    region_id = db.Column(db.Integer, db.ForeignKey("regions.id"), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    teams = db.relationship("Team", backref="county", lazy="dynamic")

    def __repr__(self):
        return f"<County {self.name}>"
