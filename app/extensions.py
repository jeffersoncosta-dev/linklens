import redis
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

redis_conn = None

limiter = Limiter(key_func=get_remote_address)
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def init_redis(app):
    global redis_conn
    redis_conn = redis.from_url(app.config["REDIS_URL"], decode_responses=True)
    return redis_conn
