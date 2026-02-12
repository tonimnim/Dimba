from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func

from app.extensions import db
from app.models.user import User
from app.models.team import Team, TeamStatus
from app.models.player import Player
from app.models.match import Match, MatchStatus
from app.models.standing import Standing
from app.models.season import Season
from app.models.county import County
from app.models.competition import Competition, competition_teams

from app.schemas import (
    TeamSchema,
    PlayerSchema,
    MatchSchema,
    StandingSchema,
    CompetitionSchema,
    SeasonSchema,
)
from app.schemas.county import CountySchema
from app.auth.decorators import role_required
from app.services.standings import sort_standings

coach_bp = Blueprint("coach", __name__)

team_schema = TeamSchema()
teams_schema = TeamSchema(many=True)
players_schema = PlayerSchema(many=True)
match_schema = MatchSchema()
standing_schema = StandingSchema()
standings_schema = StandingSchema(many=True)
competition_schema = CompetitionSchema()
competitions_schema = CompetitionSchema(many=True)
season_schema = SeasonSchema()
county_schema = CountySchema()


@coach_bp.route("/my-team", methods=["GET"])
@role_required("coach", "county_admin")
def get_my_team():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if not user or not user.team_id:
        return jsonify({"error": "No team assigned to this coach"}), 404

    team = db.session.get(Team, user.team_id)
    if not team:
        return jsonify({"error": "Team not found"}), 404

    # Get players
    players = Player.query.filter_by(team_id=team.id).order_by(Player.last_name).all()

    # Find active season
    season = Season.query.filter_by(is_active=True).first()

    competition = None
    standing = None
    next_match = None
    rank = None

    if season:
        # Find competition this team is in for the active season
        competition = (
            Competition.query.join(competition_teams)
            .filter(
                competition_teams.c.team_id == team.id,
                Competition.season_id == season.id,
            )
            .first()
        )

        if competition:
            # Get standing
            standing = Standing.query.filter_by(
                team_id=team.id,
                competition_id=competition.id,
                season_id=season.id,
            ).first()

            # Calculate rank from all standings in the competition
            if standing:
                raw = Standing.query.filter_by(
                    competition_id=competition.id,
                    season_id=season.id,
                ).all()
                all_standings = sort_standings(raw, competition.id, season.id)
                for i, s in enumerate(all_standings):
                    if s.team_id == team.id:
                        rank = i + 1
                        break

            # Get next scheduled match
            next_match = (
                Match.query.filter(
                    Match.competition_id == competition.id,
                    Match.season_id == season.id,
                    Match.status == MatchStatus.SCHEDULED,
                    (Match.home_team_id == team.id) | (Match.away_team_id == team.id),
                )
                .order_by(Match.match_date.asc())
                .first()
            )

    return jsonify({
        "team": team_schema.dump(team),
        "players": players_schema.dump(players),
        "next_match": match_schema.dump(next_match) if next_match else None,
        "standing": standing_schema.dump(standing) if standing else None,
        "competition": competition_schema.dump(competition) if competition else None,
        "season": season_schema.dump(season) if season else None,
        "rank": rank,
    }), 200


@coach_bp.route("/my-county", methods=["GET"])
@role_required("county_admin")
def get_my_county():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if not user or not user.county_id:
        return jsonify({"error": "No county assigned"}), 404

    county = db.session.get(County, user.county_id)
    if not county:
        return jsonify({"error": "County not found"}), 404

    # Teams in county
    teams = Team.query.filter_by(county_id=county.id).order_by(Team.name).all()

    # Counts by status
    total_teams = len(teams)
    active_teams = sum(1 for t in teams if t.status == TeamStatus.ACTIVE)
    pending_teams = sum(1 for t in teams if t.status == TeamStatus.PENDING)

    # Total players across all county teams
    team_ids = [t.id for t in teams]
    total_players = (
        Player.query.filter(Player.team_id.in_(team_ids)).count()
        if team_ids
        else 0
    )

    return jsonify({
        "county": county_schema.dump(county),
        "teams": teams_schema.dump(teams),
        "stats": {
            "total_teams": total_teams,
            "active_teams": active_teams,
            "pending_teams": pending_teams,
            "total_players": total_players,
        },
    }), 200


@coach_bp.route("/my-standings", methods=["GET"])
@role_required("coach", "county_admin")
def get_my_standings():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Determine "my" team IDs based on role
    from app.models.user import UserRole

    if user.role == UserRole.COACH:
        if not user.team_id:
            return jsonify({"competitions": [], "my_team_ids": []}), 200
        my_team_ids = [user.team_id]
    else:
        # county_admin
        if not user.county_id:
            return jsonify({"competitions": [], "my_team_ids": []}), 200
        my_team_ids = [
            t.id for t in Team.query.filter_by(county_id=user.county_id).all()
        ]

    if not my_team_ids:
        return jsonify({"competitions": [], "my_team_ids": []}), 200

    # Active season
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        return jsonify({"competitions": [], "my_team_ids": my_team_ids}), 200

    # Find all competitions these teams are registered in
    comps = (
        Competition.query.join(competition_teams)
        .filter(
            competition_teams.c.team_id.in_(my_team_ids),
            Competition.season_id == season.id,
        )
        .distinct()
        .all()
    )

    result = []
    for comp in comps:
        raw = Standing.query.filter_by(
            competition_id=comp.id,
            season_id=season.id,
        ).all()
        # Sort within each group using h2h tiebreakers
        groups = {}
        for s in raw:
            groups.setdefault(s.group_name, []).append(s)
        rows = []
        for gn in sorted(groups.keys(), key=lambda x: (x is None, x)):
            rows.extend(sort_standings(groups[gn], comp.id, season.id))
        result.append({
            "competition": competition_schema.dump(comp),
            "standings": standings_schema.dump(rows),
        })

    return jsonify({
        "competitions": result,
        "my_team_ids": my_team_ids,
    }), 200
