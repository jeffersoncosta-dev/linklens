from flask import Flask, jsonify

from app import extensions
from app.api.v1 import api_v1_bp
from app.config import config

# from app.public.routes import public_bp
from app.core.tracker import start_click_worker
from app.extensions import db, init_redis, jwt, limiter, migrate
from app.redirects import redirects_bp


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    """Callback function to verify if a JWT has been revoked.

    Checks the Redis blocklist for the presence of the token's JTI.

    Args:
        jwt_header (dict): The JWT header data.
        jwt_payload (dict): The JWT payload data.

    Returns:
        bool: True if the token is in the blocklist (revoked), False otherwise.
    """
    jti = jwt_payload["jti"]
    sid = jwt_payload.get("sid")
    if extensions.redis_conn.get(f"bl:{jti}") is not None:
        return True
    return bool(sid and extensions.redis_conn.get(f"bl:sess:{sid}") is not None)


def create_app(config_name="default"):
    """Application factory function to initialize and configure the Flask app."""
    app = Flask(__name__)

    config_class = config.get(config_name, config["default"])
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    jwt.init_app(app)
    init_redis(app)

    # Register routes
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")
    app.register_blueprint(redirects_bp)

    # Import models in app context
    with app.app_context():
        from app.models import Click, ShortURL, User

    # Shell Context Processor
    @app.shell_context_processor
    def make_shell_context():
        """Registers variables to be automatically imported in the Flask shell."""
        from app.models import Click, ShortURL, User

        return {
            "db": db,
            "User": User,
            "ShortURL": ShortURL,
            "Click": Click,
        }

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"error": "not_found", "message": str(e)}), 404

    @app.errorhandler(405)
    def handle_not_allowed(e):
        return jsonify({"error": "method_not_allowed", "message": str(e)}), 405

    @app.errorhandler(429)
    def handle_too_many(e):
        return jsonify({"error": "rate_limit_exceeded", "message": str(e)}), 429

    @app.errorhandler(500)
    def handle_internal_server(e):
        db.session.rollback()
        return jsonify({"error": "internal_server_error", "message": str(e)}), 500

    if not app.config.get("TESTING"):
        start_click_worker(app)

    return app
