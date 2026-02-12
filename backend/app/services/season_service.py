from app.extensions import db
from app.models.season import Season


def create_season(data):
    # Deactivate all existing seasons — the newest is always the active one
    Season.query.filter_by(is_active=True).update({"is_active": False})

    season = Season(
        name=data["name"],
        year=data["year"],
        is_active=True,
    )
    db.session.add(season)
    db.session.commit()
    return season


def update_season(season_id, data):
    season = db.session.get(Season, season_id)
    if not season:
        return None, "Season not found"

    if "name" in data:
        season.name = data["name"]
    if "year" in data:
        season.year = data["year"]
    if "is_active" in data:
        season.is_active = data["is_active"]

    db.session.commit()
    return season, None
