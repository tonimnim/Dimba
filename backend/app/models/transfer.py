from app.extensions import db
from datetime import datetime, timezone
import enum


class TransferStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


class Transfer(db.Model):
    __tablename__ = "transfers"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    from_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    to_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    fee = db.Column(db.Numeric(12, 2), nullable=True, default=0)
    status = db.Column(
        db.Enum(TransferStatus), nullable=False, default=TransferStatus.PENDING
    )
    reason = db.Column(db.Text, nullable=True)
    initiated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    from_team = db.relationship("Team", foreign_keys=[from_team_id], backref="transfers_out")
    to_team = db.relationship("Team", foreign_keys=[to_team_id], backref="transfers_in")
    initiated_by = db.relationship(
        "User", foreign_keys=[initiated_by_id], backref="initiated_transfers"
    )
    approved_by = db.relationship(
        "User", foreign_keys=[approved_by_id], backref="approved_transfers"
    )

    def __repr__(self):
        return f"<Transfer {self.player_id}: {self.from_team_id} -> {self.to_team_id}>"
