from app.extensions import db
from app.models.transfer import Transfer, TransferStatus
from app.models.player import Player


def initiate_transfer(data, user_id):
    """Coach initiates a player transfer. Status: PENDING."""
    player = db.session.get(Player, data["player_id"])

    if not player:
        return None, "Player not found"

    if player.team_id != data["from_team_id"]:
        return None, "Player does not belong to the specified team"

    transfer = Transfer(
        player_id=data["player_id"],
        from_team_id=data["from_team_id"],
        to_team_id=data["to_team_id"],
        fee=data.get("fee") or 0,
        reason=data.get("reason"),
        initiated_by_id=user_id,
        status=TransferStatus.PENDING,
    )

    db.session.add(transfer)
    db.session.commit()

    return transfer, None


def approve_transfer(transfer_id, user_id):
    """Admin approves transfer. Player moves to new team. Status: COMPLETED."""
    transfer = db.session.get(Transfer, transfer_id)

    if not transfer:
        return None, "Transfer not found"

    if transfer.status != TransferStatus.PENDING:
        return None, "Only pending transfers can be approved"

    # Move player to new team
    player = db.session.get(Player, transfer.player_id)
    player.team_id = transfer.to_team_id

    transfer.status = TransferStatus.COMPLETED
    transfer.approved_by_id = user_id

    db.session.commit()
    return transfer, None


def reject_transfer(transfer_id, user_id):
    """Admin rejects transfer. Status: REJECTED."""
    transfer = db.session.get(Transfer, transfer_id)

    if not transfer:
        return None, "Transfer not found"

    if transfer.status != TransferStatus.PENDING:
        return None, "Only pending transfers can be rejected"

    transfer.status = TransferStatus.REJECTED
    transfer.approved_by_id = user_id

    db.session.commit()
    return transfer, None
