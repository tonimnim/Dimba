from datetime import datetime

from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.region import Region
from app.models.county import County
from app.models.season import Season
from app.models.competition import Competition, CompetitionCategory, CompetitionType
from app.models.team import Team, TeamStatus, TeamCategory
from app.models.player import Player
from app.models.user import User, UserRole
from app.models.match import Match, MatchStatus, MatchStage
from app.models.standing import Standing
from app.models.transfer import Transfer, TransferStatus

from app.schemas import (
    RegionSchema,
    CountySchema,
    SeasonSchema,
    CreateSeasonSchema,
    UpdateSeasonSchema,
    CompetitionSchema,
    CreateCompetitionSchema,
    UpdateCompetitionSchema,
    TeamSchema,
    CreateTeamSchema,
    UpdateTeamSchema,
    PlayerSchema,
    CreatePlayerSchema,
    UpdatePlayerSchema,
    UserSchema,
    MatchSchema,
    CreateMatchSchema,
    SubmitResultSchema,
    GenerateFixturesSchema,
    GenerateCupDrawSchema,
    GenerateKnockoutSchema,
    StandingSchema,
    TransferSchema,
    CreateTransferSchema,
)

from app.auth.decorators import role_required, admin_required
from app.services.season_service import create_season, update_season
from app.services.competition_service import (
    create_competition,
    update_competition,
    add_team_to_competition,
)
from app.services.team_service import create_team, update_team, approve_team, delete_team
from app.services.player_service import create_player, update_player, delete_player
from app.services.match_service import (
    create_match,
    submit_result,
    confirm_result,
)
from app.services.transfer_service import (
    initiate_transfer,
    approve_transfer,
    reject_transfer,
)
from app.services.scheduler_service import (
    generate_round_robin,
    generate_county_round_robin,
    generate_regional_groups,
    generate_cl_groups,
    advance_cl_knockout,
    generate_cl_knockout_bracket,
    generate_cup_draw,
    get_bracket,
)
from app.services.standings import sort_standings
from app.services.qualification_service import (
    get_competition_status,
    get_top_teams,
    qualify_for_champions_league,
    qualify_for_regional,
)

api_bp = Blueprint("api", __name__)

# ── Schema instances ─────────────────────────────────────────────────────────
regions_schema = RegionSchema(many=True, exclude=("counties",))
region_detail_schema = RegionSchema()

county_schema = CountySchema()
counties_schema = CountySchema(many=True, exclude=("region",))

season_schema = SeasonSchema()
seasons_schema = SeasonSchema(many=True)
create_season_schema = CreateSeasonSchema()
update_season_schema = UpdateSeasonSchema()

competition_schema = CompetitionSchema()
competitions_schema = CompetitionSchema(many=True)
create_competition_schema = CreateCompetitionSchema()
update_competition_schema = UpdateCompetitionSchema()

team_schema = TeamSchema()
teams_schema = TeamSchema(many=True)
create_team_schema = CreateTeamSchema()
update_team_schema = UpdateTeamSchema()

player_schema = PlayerSchema()
players_schema = PlayerSchema(many=True)
create_player_schema = CreatePlayerSchema()
update_player_schema = UpdatePlayerSchema()

user_schema = UserSchema()
users_schema = UserSchema(many=True)

match_schema = MatchSchema()
matches_schema = MatchSchema(many=True)
create_match_schema = CreateMatchSchema()
submit_result_schema = SubmitResultSchema()
generate_fixtures_schema = GenerateFixturesSchema()
generate_cup_draw_schema = GenerateCupDrawSchema()
generate_knockout_schema = GenerateKnockoutSchema()

standings_schema = StandingSchema(many=True)

transfer_schema = TransferSchema()
transfers_schema = TransferSchema(many=True)
create_transfer_schema = CreateTransferSchema()


# ─── Regions ──────────────────────────────────────────────────────────────────

@api_bp.route("/regions", methods=["GET"])
def get_regions():
    regions = Region.query.order_by(Region.name).all()
    return jsonify({"regions": regions_schema.dump(regions)}), 200


@api_bp.route("/regions/<int:region_id>", methods=["GET"])
def get_region(region_id):
    region = db.get_or_404(Region, region_id)
    return jsonify({"region": region_detail_schema.dump(region)}), 200


# ─── Counties ─────────────────────────────────────────────────────────────────

@api_bp.route("/counties", methods=["GET"])
def get_counties():
    region_id = request.args.get("region_id", type=int)
    query = County.query
    if region_id:
        query = query.filter_by(region_id=region_id)
    counties = query.order_by(County.name).all()
    return jsonify({"counties": counties_schema.dump(counties)}), 200


@api_bp.route("/counties/<int:county_id>", methods=["GET"])
def get_county(county_id):
    county = db.get_or_404(County, county_id)
    return jsonify({"county": county_schema.dump(county)}), 200


# ─── Seasons ──────────────────────────────────────────────────────────────────

@api_bp.route("/seasons", methods=["GET"])
def get_seasons():
    seasons = Season.query.order_by(Season.year.desc()).all()
    return jsonify({"seasons": seasons_schema.dump(seasons)}), 200


@api_bp.route("/seasons", methods=["POST"])
@admin_required
def create_season_route():
    data = create_season_schema.load(request.get_json())
    season = create_season(data)
    return jsonify({"season": season_schema.dump(season)}), 201


@api_bp.route("/seasons/<int:season_id>", methods=["PUT"])
@admin_required
def update_season_route(season_id):
    data = update_season_schema.load(request.get_json())
    season, error = update_season(season_id, data)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"season": season_schema.dump(season)}), 200


# ─── Competitions ─────────────────────────────────────────────────────────────

@api_bp.route("/competitions", methods=["GET"])
def get_competitions():
    season_id = request.args.get("season_id", type=int)
    region_id = request.args.get("region_id", type=int)
    category = request.args.get("category")
    comp_type = request.args.get("type")

    query = Competition.query
    if season_id:
        query = query.filter_by(season_id=season_id)
    if region_id:
        query = query.filter_by(region_id=region_id)
    if category:
        query = query.filter_by(category=CompetitionCategory(category))
    if comp_type:
        query = query.filter_by(type=CompetitionType(comp_type))

    competitions = query.order_by(Competition.name).all()
    return jsonify({"competitions": competitions_schema.dump(competitions)}), 200


@api_bp.route("/competitions/<int:comp_id>", methods=["GET"])
def get_competition(comp_id):
    competition = db.get_or_404(Competition, comp_id)
    return jsonify({"competition": competition_schema.dump(competition)}), 200


@api_bp.route("/competitions", methods=["POST"])
@admin_required
def create_competition_route():
    data = create_competition_schema.load(request.get_json())
    competition = create_competition(data)
    return jsonify({"competition": competition_schema.dump(competition)}), 201


@api_bp.route("/competitions/<int:comp_id>", methods=["PUT"])
@admin_required
def update_competition_route(comp_id):
    data = update_competition_schema.load(request.get_json())
    competition, error = update_competition(comp_id, data)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"competition": competition_schema.dump(competition)}), 200


@api_bp.route("/competitions/<int:comp_id>/teams", methods=["GET"])
def get_competition_teams(comp_id):
    competition = db.get_or_404(Competition, comp_id)
    teams = competition.teams.order_by(Team.name).all()
    return jsonify({"teams": teams_schema.dump(teams)}), 200


@api_bp.route("/competitions/<int:comp_id>/teams", methods=["POST"])
@admin_required
def add_team_to_competition_route(comp_id):
    data = request.get_json()
    if not data or "team_id" not in data:
        return jsonify({"error": "team_id is required"}), 400
    competition, error = add_team_to_competition(comp_id, data["team_id"])
    if error:
        status = 409 if "already" in error else 404
        return jsonify({"error": error}), status
    return jsonify({"message": "Team added to competition"}), 200


@api_bp.route("/competitions/<int:comp_id>/teams/batch", methods=["POST"])
@admin_required
def batch_add_teams_to_competition(comp_id):
    data = request.get_json()
    if not data or "team_ids" not in data:
        return jsonify({"error": "team_ids is required"}), 400

    competition = db.session.get(Competition, comp_id)
    if not competition:
        return jsonify({"error": "Competition not found"}), 404

    existing_ids = {t.id for t in competition.teams}
    added = 0
    for team_id in data["team_ids"]:
        if team_id in existing_ids:
            continue
        team = db.session.get(Team, team_id)
        if team:
            competition.teams.append(team)
            existing_ids.add(team_id)
            added += 1

    db.session.commit()
    return jsonify({"message": f"{added} team(s) added", "added": added}), 200


# ─── Teams ────────────────────────────────────────────────────────────────────

@api_bp.route("/teams", methods=["GET"])
def get_teams():
    region_id = request.args.get("region_id", type=int)
    county_id = request.args.get("county_id", type=int)
    category = request.args.get("category")
    status = request.args.get("status")

    query = Team.query
    if region_id:
        query = query.filter_by(region_id=region_id)
    if county_id:
        query = query.filter_by(county_id=county_id)
    if category:
        query = query.filter_by(category=TeamCategory(category))
    if status:
        query = query.filter_by(status=TeamStatus(status))

    teams = query.order_by(Team.name).all()
    return jsonify({"teams": teams_schema.dump(teams)}), 200


@api_bp.route("/teams/<int:team_id>", methods=["GET"])
def get_team(team_id):
    team = db.get_or_404(Team, team_id)
    return jsonify({"team": team_schema.dump(team)}), 200


@api_bp.route("/teams", methods=["POST"])
@role_required("super_admin", "county_admin")
def create_team_route():
    data = create_team_schema.load(request.get_json())
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    auto_activate = user.role.value in ("county_admin", "super_admin")
    team, error = create_team(data, auto_activate=auto_activate)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"team": team_schema.dump(team)}), 201


@api_bp.route("/teams/<int:team_id>", methods=["PUT"])
@role_required("super_admin", "county_admin", "coach")
def update_team_route(team_id):
    data = update_team_schema.load(request.get_json())
    team, error = update_team(team_id, data)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"team": team_schema.dump(team)}), 200


@api_bp.route("/teams/<int:team_id>/approve", methods=["POST"])
@admin_required
def approve_team_route(team_id):
    team, error = approve_team(team_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"team": team_schema.dump(team)}), 200


@api_bp.route("/teams/<int:team_id>", methods=["DELETE"])
@admin_required
def delete_team_route(team_id):
    team, error = delete_team(team_id)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"message": "Team deleted"}), 200


# ─── Players ──────────────────────────────────────────────────────────────────

@api_bp.route("/players", methods=["GET"])
def get_players():
    team_id = request.args.get("team_id", type=int)
    query = Player.query
    if team_id:
        query = query.filter_by(team_id=team_id)
    players = query.order_by(Player.last_name).all()
    return jsonify({"players": players_schema.dump(players)}), 200


@api_bp.route("/players/<int:player_id>", methods=["GET"])
def get_player(player_id):
    player = db.get_or_404(Player, player_id)
    return jsonify({"player": player_schema.dump(player)}), 200


@api_bp.route("/players", methods=["POST"])
@role_required("super_admin", "county_admin", "coach")
def create_player_route():
    data = create_player_schema.load(request.get_json())
    user_id = int(get_jwt_identity())
    player, error = create_player(data, user_id)
    if error:
        return jsonify({"error": error}), 403
    return jsonify({"player": player_schema.dump(player)}), 201


@api_bp.route("/players/<int:player_id>", methods=["PUT"])
@role_required("super_admin", "county_admin", "coach")
def update_player_route(player_id):
    data = update_player_schema.load(request.get_json())
    user_id = int(get_jwt_identity())
    player, error = update_player(player_id, data, user_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"player": player_schema.dump(player)}), 200


@api_bp.route("/players/<int:player_id>", methods=["DELETE"])
@role_required("super_admin", "coach")
def delete_player_route(player_id):
    user_id = int(get_jwt_identity())
    player, error = delete_player(player_id, user_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"message": "Player deleted"}), 200


# ─── Users ────────────────────────────────────────────────────────────────────

@api_bp.route("/users", methods=["GET"])
@admin_required
def get_users():
    role = request.args.get("role")
    is_active = request.args.get("is_active")

    query = User.query
    if role:
        query = query.filter_by(role=UserRole(role))
    if is_active is not None:
        query = query.filter_by(is_active=is_active.lower() == "true")

    users = query.order_by(User.last_name).all()
    return jsonify({"users": users_schema.dump(users)}), 200


@api_bp.route("/users/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    current_user_id = int(get_jwt_identity())
    current_user = db.session.get(User, current_user_id)

    # Users can only view their own profile, admins can view anyone
    if current_user.role.value != "super_admin" and current_user_id != user_id:
        return jsonify({"error": "Insufficient permissions"}), 403

    user = db.get_or_404(User, user_id)
    return jsonify({"user": user_schema.dump(user)}), 200


@api_bp.route("/users/<int:user_id>", methods=["PUT"])
@admin_required
def update_user(user_id):
    user = db.get_or_404(User, user_id)
    data = request.get_json()
    if "first_name" in data:
        user.first_name = data["first_name"]
    if "last_name" in data:
        user.last_name = data["last_name"]
    if "role" in data:
        user.role = UserRole(data["role"])
    if "is_active" in data:
        user.is_active = data["is_active"]
    if "team_id" in data:
        user.team_id = data["team_id"]
    if "county_id" in data:
        user.county_id = data["county_id"]
    db.session.commit()
    return jsonify({"user": user_schema.dump(user)}), 200


@api_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def reset_user_password(user_id):
    user = db.get_or_404(User, user_id)
    data = request.get_json()
    password = data.get("password", "") if data else ""
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    user.set_password(password)
    db.session.commit()
    return jsonify({"message": "Password updated"}), 200


@api_bp.route("/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    user = db.get_or_404(User, user_id)
    current_user_id = int(get_jwt_identity())
    if user.id == current_user_id:
        return jsonify({"error": "Cannot delete your own account"}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted"}), 200


# ─── Matches ──────────────────────────────────────────────────────────────────

@api_bp.route("/matches", methods=["GET"])
def get_matches():
    competition_id = request.args.get("competition_id", type=int)
    season_id = request.args.get("season_id", type=int)
    team_id = request.args.get("team_id", type=int)
    region_id = request.args.get("region_id", type=int)
    competition_type = request.args.get("competition_type")
    status = request.args.get("status")
    date_str = request.args.get("date")  # YYYY-MM-DD
    matchday = request.args.get("matchday", type=int)
    stage = request.args.get("stage")
    group_name = request.args.get("group_name")

    query = Match.query
    if region_id or competition_type:
        query = query.join(Competition)
        if region_id:
            query = query.filter(Competition.region_id == region_id)
        if competition_type:
            query = query.filter(Competition.type == CompetitionType(competition_type))
    if competition_id:
        query = query.filter_by(competition_id=competition_id)
    if season_id:
        query = query.filter_by(season_id=season_id)
    if team_id:
        query = query.filter(
            (Match.home_team_id == team_id) | (Match.away_team_id == team_id)
        )
    if status:
        query = query.filter_by(status=MatchStatus(status))
    if matchday:
        query = query.filter_by(matchday=matchday)
    if stage:
        query = query.filter_by(stage=MatchStage(stage))
    if group_name:
        query = query.filter_by(group_name=group_name)
    if date_str:
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            query = query.filter(db.func.date(Match.match_date) == date)
        except ValueError:
            pass

    matches = query.order_by(Match.match_date.desc()).all()
    return jsonify({"matches": matches_schema.dump(matches)}), 200


@api_bp.route("/matches/<int:match_id>", methods=["GET"])
def get_match(match_id):
    match = db.get_or_404(Match, match_id)
    return jsonify({"match": match_schema.dump(match)}), 200


@api_bp.route("/matches", methods=["POST"])
@admin_required
def create_match_route():
    data = create_match_schema.load(request.get_json())
    match = create_match(data)
    return jsonify({"match": match_schema.dump(match)}), 201


@api_bp.route("/matches/<int:match_id>/submit-result", methods=["POST"])
@role_required("super_admin", "coach")
def submit_match_result(match_id):
    data = submit_result_schema.load(request.get_json())
    user_id = int(get_jwt_identity())

    match, error = submit_result(
        match_id, data["home_score"], data["away_score"], user_id
    )
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"match": match_schema.dump(match)}), 200


@api_bp.route("/matches/<int:match_id>/confirm-result", methods=["POST"])
@admin_required
def confirm_match_result(match_id):
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    penalty_winner_id = data.get("penalty_winner_id")
    match, error = confirm_result(match_id, user_id, penalty_winner_id)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"match": match_schema.dump(match)}), 200


# ─── Standings ────────────────────────────────────────────────────────────────

@api_bp.route("/standings", methods=["GET"])
def get_standings():
    competition_id = request.args.get("competition_id", type=int)
    season_id = request.args.get("season_id", type=int)
    region_id = request.args.get("region_id", type=int)
    competition_type = request.args.get("competition_type")
    group_name = request.args.get("group_name")

    if not season_id:
        return jsonify({"error": "season_id is required"}), 400

    # Region-wide standings: fetch all standings for competitions in the region,
    # sort each competition's standings independently, return flattened.
    if region_id or competition_type:
        query = Standing.query.join(Competition).filter(Standing.season_id == season_id)
        if region_id:
            query = query.filter(Competition.region_id == region_id)
        if competition_type:
            query = query.filter(Competition.type == CompetitionType(competition_type))
        raw = query.all()

        # Group by competition_id, sort each group
        from itertools import groupby
        raw.sort(key=lambda s: s.competition_id)
        all_sorted = []
        for comp_id, group in groupby(raw, key=lambda s: s.competition_id):
            all_sorted.extend(sort_standings(list(group), comp_id, season_id))

        return jsonify({"standings": standings_schema.dump(all_sorted)}), 200

    if not competition_id:
        return jsonify({"error": "competition_id or region_id is required"}), 400

    query = Standing.query.filter_by(
        competition_id=competition_id, season_id=season_id
    )
    if group_name:
        query = query.filter_by(group_name=group_name)

    raw = query.all()
    standings = sort_standings(raw, competition_id, season_id)

    return jsonify({"standings": standings_schema.dump(standings)}), 200


# ─── Scheduling ───────────────────────────────────────────────────────────────

@api_bp.route("/competitions/<int:comp_id>/generate-fixtures", methods=["POST"])
@admin_required
def generate_fixtures_route(comp_id):
    data = generate_fixtures_schema.load(request.get_json())
    result, error = generate_round_robin(
        comp_id, data["start_date"], data.get("interval_days", 7), data.get("end_date")
    )
    if error:
        return jsonify({"error": error}), 409 if "already" in error.lower() else 400
    return jsonify({
        "message": "Fixtures generated",
        "match_count": len(result),
    }), 201


@api_bp.route("/competitions/<int:comp_id>/generate-county-fixtures", methods=["POST"])
@admin_required
def generate_county_fixtures_route(comp_id):
    data = generate_fixtures_schema.load(request.get_json())
    result, error = generate_county_round_robin(
        comp_id, data["start_date"], data.get("end_date")
    )
    if error:
        return jsonify({"error": error}), 409 if "already" in error.lower() else 400
    return jsonify({
        "message": "County fixtures generated",
        "match_count": len(result),
    }), 201


@api_bp.route("/competitions/<int:comp_id>/generate-regional-groups", methods=["POST"])
@admin_required
def generate_regional_groups_route(comp_id):
    data = generate_fixtures_schema.load(request.get_json())
    result, error = generate_regional_groups(
        comp_id, data["start_date"]
    )
    if error:
        return jsonify({"error": error}), 409 if "already" in error.lower() else 400
    return jsonify({
        "message": "Regional group draw completed",
        "groups": result["groups"],
        "match_count": len(result["matches"]),
    }), 201


@api_bp.route("/competitions/<int:comp_id>/generate-groups", methods=["POST"])
@admin_required
def generate_groups_route(comp_id):
    data = generate_fixtures_schema.load(request.get_json())
    result, error = generate_cl_groups(
        comp_id, data["start_date"], data.get("interval_days", 7)
    )
    if error:
        return jsonify({"error": error}), 409 if "already" in error.lower() else 400
    return jsonify({
        "message": "Group draw completed",
        "groups": result["groups"],
        "match_count": len(result["matches"]),
    }), 201


@api_bp.route("/competitions/<int:comp_id>/advance-knockout", methods=["POST"])
@admin_required
def advance_knockout_route(comp_id):
    result, error = advance_cl_knockout(comp_id)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({
        "message": "Knockout teams determined",
        "qualified_team_ids": result["qualified_team_ids"],
        "pairings": result["pairings"],
    }), 200


@api_bp.route("/competitions/<int:comp_id>/generate-knockout", methods=["POST"])
@admin_required
def generate_knockout_route(comp_id):
    data = generate_knockout_schema.load(request.get_json())
    body = request.get_json()
    team_pairs = body.get("team_pairs")

    if not team_pairs:
        return jsonify({"error": "team_pairs is required"}), 400

    result, error = generate_cl_knockout_bracket(
        comp_id, team_pairs, data["start_date"]
    )
    if error:
        return jsonify({"error": error}), 409 if "already" in error.lower() else 400
    return jsonify({
        "message": "Full knockout bracket generated (QF → SF → Final)",
        "match_count": len(result),
    }), 201


@api_bp.route("/competitions/<int:comp_id>/generate-cup-draw", methods=["POST"])
@admin_required
def generate_cup_draw_route(comp_id):
    data = generate_cup_draw_schema.load(request.get_json())
    result, error = generate_cup_draw(comp_id, data["start_date"])
    if error:
        return jsonify({"error": error}), 409 if "already" in error.lower() else 400
    return jsonify({
        "message": "Full cup bracket generated",
        "total_matches": len(result["matches"]),
        "round1_matches": len(result["round1_matches"]),
        "bye_team_ids": result["bye_team_ids"],
        "num_byes": result["num_byes"],
        "total_rounds": result["total_rounds"],
    }), 201


@api_bp.route("/competitions/<int:comp_id>/bracket", methods=["GET"])
def get_bracket_route(comp_id):
    bracket, error = get_bracket(comp_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"bracket": bracket}), 200


@api_bp.route("/competitions/<int:comp_id>/bracket", methods=["DELETE"])
@admin_required
def reset_bracket_route(comp_id):
    competition = db.get_or_404(Competition, comp_id)
    bracket_matches = Match.query.filter_by(
        competition_id=comp_id
    ).filter(Match.bracket_position.isnot(None)).all()

    if not bracket_matches:
        return jsonify({"error": "No bracket to reset"}), 404

    # Block if any match is confirmed (results would be lost)
    confirmed = [m for m in bracket_matches if m.status == MatchStatus.CONFIRMED]
    if confirmed:
        return jsonify({"error": f"Cannot reset — {len(confirmed)} match(es) already confirmed"}), 409

    for m in bracket_matches:
        db.session.delete(m)
    db.session.commit()

    return jsonify({"message": f"Bracket reset — {len(bracket_matches)} match(es) deleted"}), 200


@api_bp.route("/fixtures/reset-all", methods=["DELETE"])
@admin_required
def reset_all_fixtures_route():
    """[TEMP] Delete all league matches and standings across every competition."""
    league_matches = Match.query.filter_by(stage=MatchStage.LEAGUE).all()
    standings = Standing.query.all()

    match_count = len(league_matches)
    standing_count = len(standings)

    for m in league_matches:
        db.session.delete(m)
    for s in standings:
        db.session.delete(s)
    db.session.commit()

    return jsonify({
        "message": f"Reset complete — {match_count} match(es) and {standing_count} standing(s) deleted"
    }), 200


@api_bp.route("/fixtures/reset-county", methods=["DELETE"])
@admin_required
def reset_county_fixtures_route():
    """[TEMP] Delete ALL county league matches and standings across every county competition."""
    county_comp_ids = [
        c.id for c in Competition.query.filter_by(
            type=CompetitionType.COUNTY
        ).all()
    ]
    if not county_comp_ids:
        return jsonify({"error": "No county competitions found"}), 404

    league_matches = Match.query.filter(
        Match.competition_id.in_(county_comp_ids),
        Match.stage == MatchStage.LEAGUE,
    ).all()
    standings = Standing.query.filter(
        Standing.competition_id.in_(county_comp_ids)
    ).all()

    match_count = len(league_matches)
    standing_count = len(standings)

    for m in league_matches:
        db.session.delete(m)
    for s in standings:
        db.session.delete(s)
    db.session.commit()

    return jsonify({
        "message": f"County reset — {match_count} match(es) and {standing_count} standing(s) deleted"
    }), 200


# ─── Qualification ────────────────────────────────────────────────────────

@api_bp.route("/competitions/<int:comp_id>/status", methods=["GET"])
def competition_status_route(comp_id):
    """Check how many matches are confirmed vs total for a competition."""
    status, error = get_competition_status(comp_id)
    if error:
        return jsonify({"error": error}), 404
    return jsonify(status), 200


@api_bp.route("/competitions/<int:comp_id>/top-teams", methods=["GET"])
def top_teams_route(comp_id):
    """Get the top N teams from a competition's standings (h2h tiebreakers)."""
    count = request.args.get("count", 3, type=int)
    competition = db.session.get(Competition, comp_id)
    if not competition:
        return jsonify({"error": "Competition not found"}), 404

    team_ids, error = get_top_teams(comp_id, competition.season_id, count=count)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"team_ids": team_ids, "count": len(team_ids)}), 200


@api_bp.route("/seasons/<int:season_id>/qualify-for-cl", methods=["POST"])
@admin_required
def qualify_for_cl_route(season_id):
    """Qualify top 3 from every completed regional league into a CL competition.

    Body: { "cl_competition_id": 42 }
    """
    data = request.get_json()
    if not data or "cl_competition_id" not in data:
        return jsonify({"error": "cl_competition_id is required"}), 400

    result, error = qualify_for_champions_league(
        season_id, data["cl_competition_id"], top_n=data.get("top_n", 3)
    )
    if error:
        return jsonify({"error": error}), 400
    return jsonify(result), 200


@api_bp.route("/seasons/<int:season_id>/qualify-for-regional", methods=["POST"])
@admin_required
def qualify_for_regional_route(season_id):
    """Qualify top teams from completed county leagues into a regional competition.

    Body: { "regional_competition_id": 42, "top_n": 4 }
    """
    data = request.get_json()
    if not data or "regional_competition_id" not in data:
        return jsonify({"error": "regional_competition_id is required"}), 400

    result, error = qualify_for_regional(
        season_id, data["regional_competition_id"], top_n=data.get("top_n", 4)
    )
    if error:
        return jsonify({"error": error}), 400
    return jsonify(result), 200


# ─── SSE Events ──────────────────────────────────────────────────────────

@api_bp.route("/events/stream", methods=["GET"])
def event_stream():
    import queue as _queue
    from app.events import event_bus

    def generate():
        q = event_bus.subscribe()
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield f"data: {msg}\n\n"
                except _queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            event_bus.unsubscribe(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Transfers ────────────────────────────────────────────────────────────────

@api_bp.route("/transfers", methods=["GET"])
@jwt_required()
def get_transfers():
    status = request.args.get("status")
    team_id = request.args.get("team_id", type=int)

    query = Transfer.query
    if status:
        query = query.filter_by(status=TransferStatus(status))
    if team_id:
        query = query.filter(
            (Transfer.from_team_id == team_id) | (Transfer.to_team_id == team_id)
        )

    transfers = query.order_by(Transfer.created_at.desc()).all()
    return jsonify({"transfers": transfers_schema.dump(transfers)}), 200


@api_bp.route("/transfers", methods=["POST"])
@role_required("super_admin", "coach")
def create_transfer():
    data = create_transfer_schema.load(request.get_json())
    user_id = int(get_jwt_identity())

    transfer, error = initiate_transfer(data, user_id)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"transfer": transfer_schema.dump(transfer)}), 201


@api_bp.route("/transfers/<int:transfer_id>/approve", methods=["PUT"])
@admin_required
def approve_transfer_route(transfer_id):
    user_id = int(get_jwt_identity())
    transfer, error = approve_transfer(transfer_id, user_id)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"transfer": transfer_schema.dump(transfer)}), 200


@api_bp.route("/transfers/<int:transfer_id>/reject", methods=["PUT"])
@admin_required
def reject_transfer_route(transfer_id):
    user_id = int(get_jwt_identity())
    transfer, error = reject_transfer(transfer_id, user_id)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"transfer": transfer_schema.dump(transfer)}), 200
