from flask import Flask
from app.config import config
from app.extensions import db, limiter, migrate, jwt, redis_conn, init_redis
from app.api.v1 import api_v1_bp

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
    return redis_conn.get(f"bl:{jti}") is not None


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

    # Import models in app context 
    with app.app_context():
        from app.models import User, ShortURL, Click

    # Shell Context Processor
    @app.shell_context_processor
    def make_shell_context():
        """Registers variables to be automatically imported in the Flask shell."""
        from app.models import User, ShortURL, Click
        return {
            "db": db,
            "User": User,
            "ShortURL": ShortURL,
            "Click": Click,
        }

    return app