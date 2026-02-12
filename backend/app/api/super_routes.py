from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.models.match import Match
from app.schemas import MatchSchema
from app.auth.decorators import admin_required
from app.services.super_service import create_super_match

super_bp = Blueprint("super", __name__)

match_schema = MatchSchema()


@super_bp.route("/create-match", methods=["POST"])
@admin_required
def create_super_match_route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    competition_id = data.get("competition_id")
    home_team_id = data.get("home_team_id")
    away_team_id = data.get("away_team_id")
    match_date_str = data.get("match_date")
    venue = data.get("venue")

    if not competition_id or not home_team_id or not away_team_id or not match_date_str:
        return jsonify({"error": "competition_id, home_team_id, away_team_id, and match_date are required"}), 400

    try:
        match_date = datetime.fromisoformat(match_date_str)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid match_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}), 400

    match, error = create_super_match(
        competition_id, home_team_id, away_team_id, match_date, venue
    )
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"match": match_schema.dump(match)}), 201


@super_bp.route("/match/<int:competition_id>", methods=["GET"])
@jwt_required()
def get_super_match(competition_id):
    match = Match.query.filter_by(competition_id=competition_id).first()
    if not match:
        return jsonify({"match": None}), 200

    return jsonify({"match": match_schema.dump(match)}), 200
