import os
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException

from app.config import config
from app.extensions import db, migrate, jwt, cors, ma, limiter


def create_app(config_name=None):
    load_dotenv()

    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    config_class = config[config_name]
    app.config.from_object(config_class)

    # Validate production secrets
    if hasattr(config_class, "init_app"):
        config_class.init_app(app)

    # ── Logging ──────────────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO if not app.debug else logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app.logger.setLevel(logging.INFO)

    # ── Extensions ───────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    jwt.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"].split(",")}},
    )
    ma.init_app(app)
    limiter.init_app(app)

    # ── SQLite pragmas ───────────────────────────────────────────────────
    from sqlalchemy import event, Engine

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragmas(dbapi_conn, connection_record):
        import sqlite3

        if isinstance(dbapi_conn, sqlite3.Connection):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA cache_size=-20000")
            cursor.close()

    # ── Error handlers ───────────────────────────────────────────────────
    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        return jsonify({"error": "Validation failed", "messages": e.messages}), 400

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": e.description or "Bad request"}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(422)
    def unprocessable(e):
        return jsonify({"error": "Unprocessable entity"}), 422

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({"error": "Rate limit exceeded. Try again later."}), 429

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        return jsonify({"error": e.description}), e.code

    @app.errorhandler(Exception)
    def handle_generic_exception(e):
        app.logger.exception("Unhandled exception: %s", e)
        return jsonify({"error": "Internal server error"}), 500

    # ── Models ───────────────────────────────────────────────────────────
    from app import models  # noqa: F401

    # ── Blueprints ───────────────────────────────────────────────────────
    from app.auth.routes import auth_bp
    from app.api.routes import api_bp
    from app.api.coach_routes import coach_bp
    from app.api.database_routes import database_bp
    from app.api.super_routes import super_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(coach_bp, url_prefix="/api/coach")
    app.register_blueprint(database_bp, url_prefix="/api")
    app.register_blueprint(super_bp, url_prefix="/api/super")

    # ── Health check ─────────────────────────────────────────────────────
    @app.route("/health")
    def health():
        return jsonify({"status": "healthy"}), 200

    # ── CLI ───────────────────────────────────────────────────────────────
    from app.seeds.cli import seed_cli

    app.cli.add_command(seed_cli, "seed")

    return app
