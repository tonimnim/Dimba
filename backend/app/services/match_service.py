from app.extensions import db
from app.models.match import Match, MatchStatus, MatchStage
from app.services.standings import recalculate_standings
from app.services.scheduler_service import advance_bracket_winner
from app.events import event_bus


def create_match(data):
    match = Match(
        competition_id=data["competition_id"],
        season_id=data["season_id"],
        home_team_id=data["home_team_id"],
        away_team_id=data["away_team_id"],
        match_date=data.get("match_date"),
        venue=data.get("venue"),
        status=MatchStatus.SCHEDULED,
    )
    db.session.add(match)
    db.session.commit()
    return match


def submit_result(match_id, home_score, away_score, user_id):
    """Coach submits match result. Status: SCHEDULED -> COMPLETED."""
    from app.models.user import User, UserRole

    match = db.session.get(Match, match_id)

    if not match:
        return None, "Match not found"

    if match.status != MatchStatus.SCHEDULED:
        return None, "Match result can only be submitted for scheduled matches"

    # Coach ownership check
    user = db.session.get(User, user_id)
    if user and user.role == UserRole.COACH:
        if user.team_id not in [match.home_team_id, match.away_team_id]:
            return None, "You can only submit results for your own team's matches"

    match.home_score = home_score
    match.away_score = away_score
    match.status = MatchStatus.COMPLETED
    match.submitted_by_id = user_id

    db.session.commit()
    return match, None


def confirm_result(match_id, user_id, penalty_winner_id=None):
    """Admin confirms match result. Status: COMPLETED -> CONFIRMED.
    Triggers standings recalculation.
    For knockout draws, penalty_winner_id identifies who won on penalties.
    """
    match = db.session.get(Match, match_id)

    if not match:
        return None, "Match not found"

    if match.status != MatchStatus.COMPLETED:
        return None, "Only completed matches can be confirmed"

    # For knockout matches that end in a draw, require penalty winner
    is_knockout = match.bracket_position is not None
    is_draw = match.home_score == match.away_score
    if is_knockout and is_draw and match.leg is None:
        if not penalty_winner_id:
            return None, "Knockout match ended in a draw — specify penalty_winner_id"
        if penalty_winner_id not in [match.home_team_id, match.away_team_id]:
            return None, "penalty_winner_id must be one of the two teams in this match"
        match.penalty_winner_id = penalty_winner_id

    match.status = MatchStatus.CONFIRMED
    match.confirmed_by_id = user_id

    db.session.commit()

    # Recalculate standings after confirmation
    recalculate_standings(match.competition_id, match.season_id)

    event_bus.publish("match_confirmed", {
        "match_id": match.id,
        "competition_id": match.competition_id,
        "season_id": match.season_id,
        "home_team_id": match.home_team_id,
        "away_team_id": match.away_team_id,
        "home_score": match.home_score,
        "away_score": match.away_score,
    })

    event_bus.publish("standings_updated", {
        "competition_id": match.competition_id,
        "season_id": match.season_id,
    })

    # Advance bracket winner if this is a knockout bracket match
    if match.bracket_position is not None:
        advance_bracket_winner(match)
        event_bus.publish("bracket_updated", {
            "competition_id": match.competition_id,
            "match_id": match.id,
            "bracket_position": match.bracket_position,
        })

    # Check if this was the last league/group match — fire competition_complete
    if match.stage in (MatchStage.LEAGUE, MatchStage.GROUP):
        remaining = Match.query.filter_by(
            competition_id=match.competition_id,
        ).filter(
            Match.stage.in_([MatchStage.LEAGUE, MatchStage.GROUP]),
            Match.status != MatchStatus.CONFIRMED,
        ).count()

        if remaining == 0:
            event_bus.publish("competition_complete", {
                "competition_id": match.competition_id,
                "season_id": match.season_id,
            })

    return match, None
