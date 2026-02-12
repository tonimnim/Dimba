from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.extensions import db
from app.models.user import User


def role_required(*roles):
    """Decorator to restrict access to specific roles."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = db.session.get(User, user_id)

            if not user:
                return jsonify({"error": "User not found"}), 404

            if not user.is_active:
                return jsonify({"error": "Account is deactivated"}), 403

            if user.role.value not in [r.value if hasattr(r, "value") else r for r in roles]:
                return jsonify({"error": "Insufficient permissions"}), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(fn):
    """Decorator to restrict access to super admins only."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user_id = int(get_jwt_identity())
        user = db.session.get(User, user_id)

        if not user or not user.is_active:
            return jsonify({"error": "Access denied"}), 403

        if user.role.value != "super_admin":
            return jsonify({"error": "Admin access required"}), 403

        return fn(*args, **kwargs)

    return wrapper
