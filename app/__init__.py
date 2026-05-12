from flask import Flask
from app.config import config
from app.extensions import db, limiter, migrate, jwt, redis_conn, init_redis
from app.api.v1 import api_v1_bp



def create_app(config_name="default"):
    app = Flask(__name__)

    config_class = config.get(config_name, config["default"])
    app.config.from_object(config_class)

    # inicialize extentions 
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    jwt.init_app(app)
    init_redis(app)

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        return redis_conn.get(f"bl:{jti}") is not None

    # Register routes
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")

    # Import models in app context 
    with app.app_context():
        from app.models import User, ShortURL, Click

    # Shell Context Processor
    @app.shell_context_processor
    def make_shell_context():
        from app.models import User, ShortURL, Click
        return {
            "db": db,
            "User": User,
            "ShortURL": ShortURL,
            "Click": Click,
        }

    return app