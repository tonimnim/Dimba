from app.extensions import db
from app.models.competition import Competition, CompetitionType, CompetitionCategory
from app.models.team import Team


def create_competition(data):
    competition = Competition(
        name=data["name"],
        type=CompetitionType(data["type"]),
        category=CompetitionCategory(data["category"]),
        season_id=data["season_id"],
        region_id=data.get("region_id"),
    )
    db.session.add(competition)
    db.session.commit()
    return competition


def update_competition(comp_id, data):
    competition = db.session.get(Competition, comp_id)
    if not competition:
        return None, "Competition not found"

    if "name" in data:
        competition.name = data["name"]
    if "type" in data:
        competition.type = CompetitionType(data["type"])
    if "category" in data:
        competition.category = CompetitionCategory(data["category"])

    db.session.commit()
    return competition, None


def add_team_to_competition(comp_id, team_id):
    competition = db.session.get(Competition, comp_id)
    if not competition:
        return None, "Competition not found"

    team = db.session.get(Team, team_id)
    if not team:
        return None, "Team not found"

    competition.teams.append(team)
    db.session.commit()
    return competition, None
