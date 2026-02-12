from app.extensions import db
from app.models.team import Team, TeamStatus, TeamCategory
from app.models.county import County


def create_team(data, auto_activate=False):
    county = db.session.get(County, data["county_id"])
    if not county:
        return None, "County not found"

    team = Team(
        name=data["name"],
        county_id=county.id,
        region_id=county.region_id,
        category=TeamCategory(data["category"]),
        status=TeamStatus.ACTIVE if auto_activate else TeamStatus.PENDING,
    )
    db.session.add(team)
    db.session.commit()
    return team, None


def update_team(team_id, data):
    team = db.session.get(Team, team_id)
    if not team:
        return None, "Team not found"

    if "name" in data:
        team.name = data["name"]
    if "status" in data:
        team.status = TeamStatus(data["status"])
    if "logo_url" in data and data["logo_url"] is not None:
        team.logo_url = data["logo_url"]

    db.session.commit()
    return team, None


def approve_team(team_id):
    team = db.session.get(Team, team_id)
    if not team:
        return None, "Team not found"

    team.status = TeamStatus.ACTIVE
    db.session.commit()
    return team, None


def delete_team(team_id):
    team = db.session.get(Team, team_id)
    if not team:
        return None, "Team not found"

    if team.players.count() > 0:
        return None, "Cannot delete team with registered players"

    db.session.delete(team)
    db.session.commit()
    return team, None
