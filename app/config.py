import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration shared across all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    IP_HASH_SECRET = os.environ.get("IP_HASH_SECRET", JWT_SECRET_KEY)

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", REDIS_URL)
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_ENABLED = True

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
    SLUG_LENGTH = 7
    REDIRECT_CACHE_TTL = 300


class DevelopmentConfig(Config):
    """Local development configuration."""

    DEBUG = True


class TestingConfig(Config):
    """Isolated testing configuration using dedicated Postgres DB and Redis DB 15."""

    TESTING = True
    SECRET_KEY = "test-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret-key"
    IP_HASH_SECRET = "test-ip-hash-secret-key"

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/linklens_test",
    )
    REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
    RATELIMIT_STORAGE_URI = REDIS_URL
    RATELIMIT_ENABLED = False

    BASE_URL = "http://localhost:5000"


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
