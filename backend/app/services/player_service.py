from app.extensions import db
from app.models.player import Player, PlayerPosition
from app.models.user import User, UserRole


def _check_coach_ownership(user_id, team_id):
    """If user is a coach, verify team_id matches their own team."""
    user = db.session.get(User, user_id)
    if not user:
        return "User not found"
    if user.role == UserRole.SUPER_ADMIN:
        return None
    if user.role == UserRole.COACH and user.team_id != team_id:
        return "You can only manage players on your own team"
    return None


def create_player(data, user_id=None):
    team_id = data.get("team_id")
    if user_id:
        error = _check_coach_ownership(user_id, team_id)
        if error:
            return None, error

    player = Player(
        first_name=data["first_name"],
        last_name=data["last_name"],
        position=PlayerPosition(data["position"]),
        jersey_number=data.get("jersey_number"),
        team_id=team_id,
        date_of_birth=data.get("date_of_birth"),
        photo_url=data.get("photo_url"),
    )
    db.session.add(player)
    db.session.commit()
    return player, None


def update_player(player_id, data, user_id=None):
    player = db.session.get(Player, player_id)
    if not player:
        return None, "Player not found"

    if user_id:
        error = _check_coach_ownership(user_id, player.team_id)
        if error:
            return None, error

    if "first_name" in data:
        player.first_name = data["first_name"]
    if "last_name" in data:
        player.last_name = data["last_name"]
    if "position" in data:
        player.position = PlayerPosition(data["position"])
    if "jersey_number" in data:
        player.jersey_number = data["jersey_number"]
    if "photo_url" in data:
        player.photo_url = data["photo_url"]

    db.session.commit()
    return player, None


def delete_player(player_id, user_id):
    player = db.session.get(Player, player_id)
    if not player:
        return None, "Player not found"

    error = _check_coach_ownership(user_id, player.team_id)
    if error:
        return None, error

    db.session.delete(player)
    db.session.commit()
    return player, None
