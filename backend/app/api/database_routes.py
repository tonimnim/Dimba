import os
import csv
import io
import shutil
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, send_file, current_app
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.auth.decorators import admin_required

database_bp = Blueprint("database", __name__)

SNAPSHOTS_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
    "snapshots",
)


def _db_path():
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("sqlite:///"):
        return uri.replace("sqlite:///", "", 1)
    return None


# ─── Info ────────────────────────────────────────────────────────────────────


@database_bp.route("/database/info", methods=["GET"])
@admin_required
def database_info():
    path = _db_path()
    if not path or not os.path.exists(path):
        return jsonify({"error": "Database file not found"}), 404

    size_bytes = os.path.getsize(path)
    modified = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()

    # Table row counts
    tables = {}
    result = db.session.execute(
        db.text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'")
    )
    for (name,) in result:
        count = db.session.execute(db.text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
        tables[name] = count

    # WAL size
    wal_path = path + "-wal"
    wal_size = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0

    return jsonify({
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "wal_size_bytes": wal_size,
        "last_modified": modified,
        "tables": tables,
        "path": os.path.basename(path),
    }), 200


# ─── Backup (download) ──────────────────────────────────────────────────────


@database_bp.route("/database/backup", methods=["GET"])
@admin_required
def database_backup():
    path = _db_path()
    if not path or not os.path.exists(path):
        return jsonify({"error": "Database file not found"}), 404

    # Checkpoint WAL first to ensure backup is consistent
    db.session.execute(db.text("PRAGMA wal_checkpoint(TRUNCATE)"))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return send_file(
        path,
        mimetype="application/x-sqlite3",
        as_attachment=True,
        download_name=f"premia_backup_{timestamp}.db",
    )


# ─── Snapshots ───────────────────────────────────────────────────────────────


@database_bp.route("/database/snapshots", methods=["GET"])
@admin_required
def list_snapshots():
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    snapshots = []
    for f in sorted(os.listdir(SNAPSHOTS_DIR)):
        if f.endswith(".db"):
            fpath = os.path.join(SNAPSHOTS_DIR, f)
            snapshots.append({
                "name": f,
                "size_bytes": os.path.getsize(fpath),
                "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(
                    os.path.getmtime(fpath), tz=timezone.utc
                ).isoformat(),
            })
    return jsonify({"snapshots": snapshots}), 200


@database_bp.route("/database/snapshots", methods=["POST"])
@admin_required
def create_snapshot():
    path = _db_path()
    if not path or not os.path.exists(path):
        return jsonify({"error": "Database file not found"}), 404

    label = request.json.get("label", "") if request.is_json else ""
    label = label.strip().replace(" ", "_")[:40] if label else ""

    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

    # Checkpoint WAL first
    db.session.execute(db.text("PRAGMA wal_checkpoint(TRUNCATE)"))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snap_name = f"snapshot_{timestamp}{'_' + label if label else ''}.db"
    snap_path = os.path.join(SNAPSHOTS_DIR, snap_name)

    shutil.copy2(path, snap_path)

    return jsonify({
        "message": "Snapshot created",
        "snapshot": {
            "name": snap_name,
            "size_bytes": os.path.getsize(snap_path),
            "size_mb": round(os.path.getsize(snap_path) / (1024 * 1024), 2),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }), 201


@database_bp.route("/database/snapshots/<name>/restore", methods=["POST"])
@admin_required
def restore_snapshot(name):
    snap_path = os.path.join(SNAPSHOTS_DIR, name)
    if not os.path.exists(snap_path):
        return jsonify({"error": "Snapshot not found"}), 404

    path = _db_path()
    if not path:
        return jsonify({"error": "Database file not found"}), 404

    # Auto-snapshot current state before restoring
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    pre_restore = os.path.join(SNAPSHOTS_DIR, f"pre_restore_{timestamp}.db")

    db.session.execute(db.text("PRAGMA wal_checkpoint(TRUNCATE)"))
    db.session.close()
    db.engine.dispose()

    shutil.copy2(path, pre_restore)
    shutil.copy2(snap_path, path)

    # Remove stale WAL/SHM
    for ext in ("-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.remove(p)

    return jsonify({"message": f"Restored from {name}. Pre-restore backup saved."}), 200


@database_bp.route("/database/snapshots/<name>", methods=["DELETE"])
@admin_required
def delete_snapshot(name):
    snap_path = os.path.join(SNAPSHOTS_DIR, name)
    if not os.path.exists(snap_path):
        return jsonify({"error": "Snapshot not found"}), 404

    os.remove(snap_path)
    return jsonify({"message": "Snapshot deleted"}), 200


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
    blocked = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX"}
    if first_word in blocked:
        return jsonify({"error": "Only SELECT queries are allowed"}), 400

    try:
        result = db.session.execute(db.text(sql))
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchmany(500)]
        return jsonify({"columns": columns, "rows": rows, "count": len(rows)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
