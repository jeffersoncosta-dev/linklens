from flask import jsonify

from app import extensions
from app.api.v1 import api_v1_bp
from app.extensions import db


@api_v1_bp.route("/health", methods=["GET"], strict_slashes=False)
def health_check():
    """Checks the health of the API and its dependent services.

    Verifies connectivity to the PostgreSQL database and the Redis cache.

    Returns:
        tuple: (dict containing health status, 200) if all services are operational.
        tuple: (dict containing degraded status, 503) if any service is down.
    """
    payload = {"status": "ok", "services": {"postgres": "ok", "redis": "ok"}}

    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        payload["status"] = "degraded"
        payload["services"]["postgres"] = "error"

    try:
        extensions.redis_conn.ping()
    except Exception:
        payload["status"] = "degraded"
        payload["services"]["redis"] = "error"

    if payload["status"] == "degraded":
        return jsonify(payload), 503

    return jsonify(payload), 200
