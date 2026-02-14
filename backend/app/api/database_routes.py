import csv
import io
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, send_file

from app.extensions import db
from app.auth.decorators import admin_required

database_bp = Blueprint("database", __name__)


# ─── Info ────────────────────────────────────────────────────────────────────


@database_bp.route("/database/info", methods=["GET"])
@admin_required
def database_info():
    # Database size
    size_row = db.session.execute(
        db.text("SELECT pg_database_size(current_database())")
    ).fetchone()
    size_bytes = size_row[0] if size_row else 0

    # Table row counts via information_schema
    tables = {}
    result = db.session.execute(
        db.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "AND table_name != 'alembic_version'"
        )
    )
    for (name,) in result:
        count = db.session.execute(
            db.text(f'SELECT COUNT(*) FROM "{name}"')
        ).scalar()
        tables[name] = count

    return jsonify({
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "tables": tables,
    }), 200


# ─── Backup (not supported with PostgreSQL) ──────────────────────────────────


@database_bp.route("/database/backup", methods=["GET"])
@admin_required
def database_backup():
    return jsonify({
        "error": "Database backup download is not supported with PostgreSQL. "
                 "Use pg_dump for backups."
    }), 501


# ─── Snapshots (not supported with PostgreSQL) ───────────────────────────────


@database_bp.route("/database/snapshots", methods=["GET"])
@admin_required
def list_snapshots():
    return jsonify({
        "error": "Snapshots are not supported with PostgreSQL."
    }), 501


@database_bp.route("/database/snapshots", methods=["POST"])
@admin_required
def create_snapshot():
    return jsonify({
        "error": "Snapshots are not supported with PostgreSQL."
    }), 501


@database_bp.route("/database/snapshots/<name>/restore", methods=["POST"])
@admin_required
def restore_snapshot(name):
    return jsonify({
        "error": "Snapshots are not supported with PostgreSQL."
    }), 501


@database_bp.route("/database/snapshots/<name>", methods=["DELETE"])
@admin_required
def delete_snapshot(name):
    return jsonify({
        "error": "Snapshots are not supported with PostgreSQL."
    }), 501


# ─── Export CSV ──────────────────────────────────────────────────────────────

EXPORTABLE = {
    "teams", "players", "matches", "standings", "competitions",
    "regions", "counties", "seasons", "transfers", "users",
}


@database_bp.route("/database/export/<table_name>", methods=["GET"])
@admin_required
def export_csv(table_name):
    if table_name not in EXPORTABLE:
        return jsonify({"error": f"Table '{table_name}' is not exportable"}), 400

    result = db.session.execute(db.text(f'SELECT * FROM "{table_name}"'))
    rows = result.fetchall()
    columns = list(result.keys())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)

    buf = io.BytesIO(output.getvalue().encode("utf-8"))
    buf.seek(0)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"{table_name}_{timestamp}.csv",
    )


# ─── Query (read-only) ──────────────────────────────────────────────────────


@database_bp.route("/database/query", methods=["POST"])
@admin_required
def run_query():
    data = request.get_json()
    sql = (data.get("sql") or "").strip() if data else ""

    if not sql:
        return jsonify({"error": "No SQL provided"}), 400

    # Block write operations
    first_word = sql.split()[0].upper() if sql.split() else ""
    blocked = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "TRUNCATE"}
    if first_word in blocked:
        return jsonify({"error": "Only SELECT queries are allowed"}), 400

    try:
        result = db.session.execute(db.text(sql))
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchmany(500)]
        return jsonify({"columns": columns, "rows": rows, "count": len(rows)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
