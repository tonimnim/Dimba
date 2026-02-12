"""Regional → Champions League qualification pipeline.

Handles:
- Detecting whether a regional competition is complete (all matches confirmed)
- Extracting the top N teams from a completed regional league
- Qualifying teams from all 7 regions into a Champions League competition
"""
from app.extensions import db
from app.models.competition import Competition, CompetitionType, CompetitionCategory
from app.models.match import Match, MatchStatus, MatchStage
from app.models.standing import Standing
from app.services.standings import sort_standings


def get_competition_status(competition_id):
    """Return completion status of a competition's league/group matches.

    Returns dict with:
        total:     total league/group matches
        confirmed: how many are confirmed
        remaining: how many are not yet confirmed
        complete:  bool, True when every match is confirmed
    """
    competition = db.session.get(Competition, competition_id)
    if not competition:
        return None, "Competition not found"

    total = Match.query.filter_by(
        competition_id=competition_id,
    ).filter(
        Match.stage.in_([MatchStage.LEAGUE, MatchStage.GROUP])
    ).count()

    confirmed = Match.query.filter_by(
        competition_id=competition_id,
        status=MatchStatus.CONFIRMED,
    ).filter(
        Match.stage.in_([MatchStage.LEAGUE, MatchStage.GROUP])
    ).count()

    return {
        "competition_id": competition_id,
        "competition_name": competition.name,
        "total": total,
        "confirmed": confirmed,
        "remaining": total - confirmed,
        "complete": total > 0 and confirmed == total,
    }, None


def get_top_teams(competition_id, season_id, count=3):
    """Return the top N teams from a completed regional league.

    Uses sort_standings (FIFA/CAF h2h tiebreakers) to determine order.
    Returns list of team IDs, best-placed first.
    """
    raw = Standing.query.filter_by(
        competition_id=competition_id,
        season_id=season_id,
    ).all()

    if not raw:
        return None, "No standings found for this competition"

    sorted_standings = sort_standings(raw, competition_id, season_id)
    top = sorted_standings[:count]
    return [s.team_id for s in top], None


def qualify_for_champions_league(season_id, cl_competition_id, top_n=3):
    """Pull the top N teams from every completed regional league in this season
    and add them to the Champions League competition.

    Steps:
    1. Find all REGIONAL competitions for this season
    2. Verify each one is complete (all matches confirmed)
    3. Extract top N from each using h2h-aware standings
    4. Add all qualified teams to the CL competition

    Returns a summary dict or (None, error_string).
    """
    cl_comp = db.session.get(Competition, cl_competition_id)
    if not cl_comp:
        return None, "Champions League competition not found"

    if cl_comp.type != CompetitionType.NATIONAL:
        return None, "Target competition must be of type 'national'"

    if cl_comp.season_id != season_id:
        return None, "Champions League competition does not belong to this season"

    # Find all regional competitions for this season
    regionals = Competition.query.filter_by(
        season_id=season_id,
        type=CompetitionType.REGIONAL,
    ).all()

    if not regionals:
        return None, "No regional competitions found for this season"

    # Check each regional is complete and gather top teams
    qualified = []          # list of (team_id, region_name, comp_name, rank)
    incomplete = []         # regions that aren't done yet
    region_summaries = []   # per-region breakdown for the response

    for reg in regionals:
        status, err = get_competition_status(reg.id)
        if err:
            return None, f"Error checking {reg.name}: {err}"

        region_name = reg.region.name if reg.region else "Unknown"

        if not status["complete"]:
            incomplete.append({
                "competition": reg.name,
                "region": region_name,
                "remaining": status["remaining"],
                "total": status["total"],
            })
            continue

        team_ids, err = get_top_teams(reg.id, season_id, count=top_n)
        if err:
            return None, f"Error getting top teams from {reg.name}: {err}"

        region_summary = {
            "competition": reg.name,
            "region": region_name,
            "qualified_team_ids": team_ids,
        }
        region_summaries.append(region_summary)

        for rank, tid in enumerate(team_ids, 1):
            qualified.append((tid, region_name, reg.name, rank))

    if incomplete:
        names = [f"{i['region']} ({i['remaining']}/{i['total']} remaining)" for i in incomplete]
        return None, f"Regional leagues not yet complete: {', '.join(names)}"

    expected = len(regionals) * top_n
    if len(qualified) != expected:
        return None, (
            f"Expected {expected} qualified teams "
            f"({len(regionals)} regions × {top_n}), got {len(qualified)}"
        )

    # Add all qualified teams to the CL competition
    existing_ids = {t.id for t in cl_comp.teams}
    added = 0
    for tid, _, _, _ in qualified:
        if tid not in existing_ids:
            from app.models.team import Team
            team = db.session.get(Team, tid)
            if team:
                cl_comp.teams.append(team)
                added += 1

    db.session.commit()

    return {
        "qualified_count": len(qualified),
        "added_to_cl": added,
        "already_in_cl": len(qualified) - added,
        "regions": region_summaries,
        "cl_competition_id": cl_competition_id,
    }, None
