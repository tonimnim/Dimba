from app.extensions import db
from app.models.competition import Competition, CompetitionType
from app.models.match import Match, MatchStage, MatchStatus


def create_super_match(competition_id, home_team_id, away_team_id, match_date, venue=None):
    """Create the single Dimba Super match.

    home_team_id = Champions League winner
    away_team_id = Cup winner
    """
    competition = db.session.get(Competition, competition_id)
    if not competition:
        return None, "Competition not found"

    if competition.type != CompetitionType.SUPER:
        return None, "This is not a Super competition"

    # Check no match already exists
    existing = Match.query.filter_by(competition_id=competition_id).first()
    if existing:
        return None, "Super match already created"

    match = Match(
        competition_id=competition_id,
        season_id=competition.season_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        match_date=match_date,
        venue=venue,
        stage=MatchStage.SUPER,
        status=MatchStatus.SCHEDULED,
    )
    db.session.add(match)
    db.session.commit()

    return match, None
