from datetime import datetime, timezone
from itertools import groupby

from app.extensions import db
from app.models.match import Match, MatchStatus, MatchStage
from app.models.standing import Standing


# Stages that count toward league/group standings
_STANDINGS_STAGES = {MatchStage.LEAGUE, MatchStage.GROUP, None}


def sort_standings(standings, competition_id, season_id):
    """Sort standings using FIFA/CAF tiebreaker rules.

    Order:
      1. Points DESC
      2. Head-to-head points among tied teams DESC
      3. Head-to-head goal difference among tied teams DESC
      4. Overall goal difference DESC
      5. Overall goals for DESC

    Accepts a list of Standing objects and returns them sorted.
    """
    if len(standings) <= 1:
        return list(standings)

    # Load confirmed matches once for h2h lookups
    matches = Match.query.filter_by(
        competition_id=competition_id,
        season_id=season_id,
        status=MatchStatus.CONFIRMED,
    ).filter(
        Match.stage.in_([MatchStage.LEAGUE, MatchStage.GROUP]) | Match.stage.is_(None)
    ).all()

    # Pre-sort by points desc to identify tied groups
    by_points = sorted(standings, key=lambda s: s.points, reverse=True)

    result = []
    for _pts, group in groupby(by_points, key=lambda s: s.points):
        tied = list(group)
        if len(tied) == 1:
            result.append(tied[0])
            continue

        # Compute head-to-head mini-table among tied teams
        tied_ids = {s.team_id for s in tied}
        h2h = {tid: {"pts": 0, "gd": 0} for tid in tied_ids}

        for m in matches:
            if m.home_team_id in tied_ids and m.away_team_id in tied_ids:
                if m.home_score > m.away_score:
                    h2h[m.home_team_id]["pts"] += 3
                elif m.home_score < m.away_score:
                    h2h[m.away_team_id]["pts"] += 3
                else:
                    h2h[m.home_team_id]["pts"] += 1
                    h2h[m.away_team_id]["pts"] += 1
                h2h[m.home_team_id]["gd"] += m.home_score - m.away_score
                h2h[m.away_team_id]["gd"] += m.away_score - m.home_score

        tied.sort(
            key=lambda s: (
                h2h[s.team_id]["pts"],
                h2h[s.team_id]["gd"],
                s.goal_difference,
                s.goals_for,
            ),
            reverse=True,
        )
        result.extend(tied)

    return result


def recalculate_standings(competition_id, season_id):
    """Recalculate all standings for a competition in a season.

    Called after a match is confirmed. Rebuilds standings from all
    confirmed matches to ensure consistency.
    Only counts LEAGUE, GROUP, and legacy (None) stage matches — knockout
    matches are excluded from standings.
    """
    # Get all confirmed matches for this competition/season (only standings-relevant stages)
    matches = Match.query.filter_by(
        competition_id=competition_id,
        season_id=season_id,
        status=MatchStatus.CONFIRMED,
    ).filter(
        Match.stage.in_([MatchStage.LEAGUE, MatchStage.GROUP]) | Match.stage.is_(None)
    ).all()

    # Build stats dict keyed by team_id, also track group_name per team
    stats = {}
    team_groups = {}

    for match in matches:
        for team_id in [match.home_team_id, match.away_team_id]:
            if team_id not in stats:
                stats[team_id] = {
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                }
            # Track group_name from match
            if match.group_name and team_id not in team_groups:
                team_groups[team_id] = match.group_name

        # Home team stats
        home = stats[match.home_team_id]
        home["played"] += 1
        home["goals_for"] += match.home_score
        home["goals_against"] += match.away_score

        # Away team stats
        away = stats[match.away_team_id]
        away["played"] += 1
        away["goals_for"] += match.away_score
        away["goals_against"] += match.home_score

        if match.home_score > match.away_score:
            home["won"] += 1
            away["lost"] += 1
        elif match.home_score < match.away_score:
            away["won"] += 1
            home["lost"] += 1
        else:
            home["drawn"] += 1
            away["drawn"] += 1

    # Update standings in database
    for team_id, s in stats.items():
        standing = Standing.query.filter_by(
            team_id=team_id,
            competition_id=competition_id,
            season_id=season_id,
        ).first()

        if not standing:
            standing = Standing(
                team_id=team_id,
                competition_id=competition_id,
                season_id=season_id,
            )
            db.session.add(standing)

        standing.played = s["played"]
        standing.won = s["won"]
        standing.drawn = s["drawn"]
        standing.lost = s["lost"]
        standing.goals_for = s["goals_for"]
        standing.goals_against = s["goals_against"]
        standing.goal_difference = s["goals_for"] - s["goals_against"]
        standing.points = (s["won"] * 3) + (s["drawn"] * 1)
        standing.updated_at = datetime.now(timezone.utc)

        # Propagate group_name from match data
        if team_id in team_groups:
            standing.group_name = team_groups[team_id]

    db.session.commit()
