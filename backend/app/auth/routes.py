import re
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
)
from app.extensions import db, limiter
from app.models.user import User, UserRole
from app.schemas.user import UserSchema, RegisterSchema
from app.auth.decorators import admin_required

auth_bp = Blueprint("auth", __name__)
user_schema = UserSchema()
register_schema = RegisterSchema()

PASSWORD_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#]).{8,}$"
)


def validate_password(password):
    """Require 8+ chars with uppercase, lowercase, digit, and special char."""
    if not PASSWORD_RE.match(password):
        return (
            "Password must be at least 8 characters with uppercase, "
            "lowercase, digit, and special character"
        )
    return None


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.get_json()

    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=data["email"]).first()

    if not user or not user.check_password(data["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    if not user.is_active:
        return jsonify({"error": "Account is deactivated"}), 403

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user_schema.dump(user),
        }
    ), 200


@auth_bp.route("/register", methods=["POST"])
@admin_required
def register():
    data = register_schema.load(request.get_json())

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409

    pw_error = validate_password(data["password"])
    if pw_error:
        return jsonify({"error": pw_error}), 400

    user = User(
        email=data["email"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        role=UserRole(data["role"]),
        team_id=data.get("team_id"),
        county_id=data.get("county_id"),
    )
    user.set_password(data["password"])

    db.session.add(user)
    db.session.commit()

    return jsonify({"user": user_schema.dump(user)}), 201


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
@limiter.limit("30 per minute")
def refresh():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if not user or not user.is_active:
        return jsonify({"error": "Account is deactivated"}), 403

    access_token = create_access_token(identity=str(user_id))
    return jsonify({"access_token": access_token}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"user": user_schema.dump(user)}), 200


@auth_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_me():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    if "avatar_url" in data:
        avatar_url = data["avatar_url"]
        if avatar_url is not None and (not isinstance(avatar_url, str) or len(avatar_url) > 500):
            return jsonify({"error": "avatar_url must be a string of max 500 characters"}), 400
        user.avatar_url = avatar_url

    db.session.commit()
    return jsonify({"user": user_schema.dump(user)}), 200
