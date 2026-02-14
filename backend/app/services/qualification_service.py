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


def qualify_for_regional(season_id, regional_competition_id, top_n=4):
    """Qualify top N teams from each completed county league into a regional competition.

    Steps:
    1. Find the regional competition, verify it's REGIONAL type
    2. Find all COUNTY competitions for this season in that region
    3. Verify each county league is complete
    4. Get top N from each county league
    5. Add qualified teams to the regional competition
    """
    regional_comp = db.session.get(Competition, regional_competition_id)
    if not regional_comp:
        return None, "Regional competition not found"

    if regional_comp.type != CompetitionType.REGIONAL:
        return None, "Target competition must be of type 'regional'"

    if regional_comp.season_id != season_id:
        return None, "Regional competition does not belong to this season"

    # Find all county competitions for this season in the same region
    county_comps = Competition.query.filter_by(
        season_id=season_id,
        type=CompetitionType.COUNTY,
    ).all()

    # Filter to counties within this region
    region_id = regional_comp.region_id
    county_comps = [c for c in county_comps if c.county and c.county.region_id == region_id]

    if not county_comps:
        return None, f"No county competitions found for this season in region {region_id}"

    qualified = []
    incomplete = []
    region_summaries = []

    for comp in county_comps:
        status, err = get_competition_status(comp.id)
        if err:
            return None, f"Error checking {comp.name}: {err}"

        county_name = comp.county.name if comp.county else "Unknown"

        if not status["complete"]:
            incomplete.append({
                "competition": comp.name,
                "county": county_name,
                "remaining": status["remaining"],
                "total": status["total"],
            })
            continue

        team_ids, err = get_top_teams(comp.id, season_id, count=top_n)
        if err:
            return None, f"Error getting top teams from {comp.name}: {err}"

        region_summaries.append({
            "competition": comp.name,
            "county": county_name,
            "qualified_team_ids": team_ids,
        })

        for rank, tid in enumerate(team_ids, 1):
            qualified.append((tid, county_name, comp.name, rank))

    if incomplete:
        names = [f"{i['county']} ({i['remaining']}/{i['total']} remaining)" for i in incomplete]
        return None, f"County leagues not yet complete: {', '.join(names)}"

    # Add all qualified teams to the regional competition
    existing_ids = {t.id for t in regional_comp.teams}
    added = 0
    for tid, _, _, _ in qualified:
        if tid not in existing_ids:
            from app.models.team import Team
            team = db.session.get(Team, tid)
            if team:
                regional_comp.teams.append(team)
                added += 1

    db.session.commit()

    return {
        "qualified_count": len(qualified),
        "added_to_regional": added,
        "already_in_regional": len(qualified) - added,
        "counties": region_summaries,
        "regional_competition_id": regional_competition_id,
    }, None


def get_top_teams_from_groups(competition_id, season_id, count=3):
    """Get top teams from a competition that uses groups.

    Ranks group winners first (by points, GD, GF), then runners-up if needed.
    Returns list of team IDs.
    """
    all_standings = Standing.query.filter_by(
        competition_id=competition_id,
        season_id=season_id,
    ).filter(Standing.group_name.isnot(None)).all()

    if not all_standings:
        return None, "No group standings found for this competition"

    # Group by group_name
    group_map = {}
    for s in all_standings:
        group_map.setdefault(s.group_name, []).append(s)

    winners = []
    runners_up = []

    for group_name in sorted(group_map.keys()):
        sorted_group = sort_standings(group_map[group_name], competition_id, season_id)
        if len(sorted_group) >= 1:
            winners.append(sorted_group[0])
        if len(sorted_group) >= 2:
            runners_up.append(sorted_group[1])

    # Sort winners by performance
    winners.sort(key=lambda s: (s.points, s.goal_difference, s.goals_for), reverse=True)
    runners_up.sort(key=lambda s: (s.points, s.goal_difference, s.goals_for), reverse=True)

    result_ids = []
    # Take from winners first
    for s in winners:
        if len(result_ids) >= count:
            break
        result_ids.append(s.team_id)

    # If still need more, take from runners-up
    for s in runners_up:
        if len(result_ids) >= count:
            break
        result_ids.append(s.team_id)

    return result_ids, None


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

        # Check if this regional uses groups
        has_groups = Standing.query.filter_by(
            competition_id=reg.id,
            season_id=season_id,
        ).filter(Standing.group_name.isnot(None)).first()

        if has_groups:
            team_ids, err = get_top_teams_from_groups(reg.id, season_id, count=top_n)
        else:
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
