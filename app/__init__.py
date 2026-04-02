from flask import current_app, Blueprint, render_template, Flask
from app.config import config
from app.extensions import db, limiter, migrate, jwt, redis_conn, init_redis


def create_app(config_name="default"):
    app = Flask(__name__)

    config_class = config.get(config_name, config["default"])
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    jwt.init_app(app)
    init_redis(app)

    ping_bp = Blueprint("ping", __name__)

    @ping_bp.route("/ping", methods=["GET"])
    def ping():
        return {"status": "ok"}

    # 🔹 registra o blueprint no app
    app.register_blueprint(ping_bp)

    return app