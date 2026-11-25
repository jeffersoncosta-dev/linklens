import logging
import uuid
from datetime import datetime, timezone

from flask import jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import extensions
from app.api.v1 import api_v1_bp
from app.extensions import db, limiter
from app.models import User

logger = logging.getLogger(__name__)


def _get_active_user():
    """Return the active user identified by the current JWT."""
    identity = get_jwt_identity()

    if not isinstance(identity, str):
        return None

    try:
        user_id = uuid.UUID(identity)
    except ValueError:
        return None

    user = db.session.get(User, user_id)

    if user is None or not user.is_active:
        return None

    return user


def _unauthorized_response():
    return (
        jsonify(
            {
                "error": "unauthorized",
                "message": "User not found or inactive.",
            }
        ),
        401,
    )


@api_v1_bp.route("/auth/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    """Register a user with an email and an 8–128 character password."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return (
            jsonify(
                {
                    "error": "validation_error",
                    "message": "Request body must be a JSON object.",
                }
            ),
            422,
        )

    email = data.get("email")
    password = data.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        return (
            jsonify(
                {
                    "error": "validation_error",
                    "message": "Email and password must be strings.",
                }
            ),
            422,
        )

    email = email.strip().lower()

    if not email or not 8 <= len(password) <= 128:
        return (
            jsonify(
                {
                    "error": "validation_error",
                    "message": (
                        "Email is required. Password must contain "
                        "between 8 and 128 characters."
                    ),
                }
            ),
            422,
        )

    if User.query.filter_by(email=email).first() is not None:
        return (
            jsonify(
                {
                    "error": "conflict",
                    "message": "Email already registered.",
                }
            ),
            409,
        )

    try:
        user = User(email=email)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        logger.exception("Integrity error while registering user")

        return (
            jsonify(
                {
                    "error": "conflict",
                    "message": "Registration conflicts with existing data.",
                }
            ),
            409,
        )

    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Database error while registering user")

        return (
            jsonify(
                {
                    "error": "internal_server_error",
                    "message": "Failed to register user.",
                }
            ),
            500,
        )

    return (
        jsonify(
            {
                "message": "User created.",
                "user": user.to_dict(),
            }
        ),
        201,
    )


@api_v1_bp.route("/auth/login", methods=["POST"])
@limiter.limit("20 per hour")
def login():
    """Authenticate an active user and issue access and refresh tokens."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return (
            jsonify(
                {
                    "error": "validation_error",
                    "message": "Request body must be a JSON object.",
                }
            ),
            422,
        )

    email = data.get("email")
    password = data.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        return (
            jsonify(
                {
                    "error": "validation_error",
                    "message": "Email and password must be strings.",
                }
            ),
            422,
        )

    email = email.strip().lower()

    if not email or not password or len(password) > 128:
        return (
            jsonify(
                {
                    "error": "unauthorized",
                    "message": "Invalid email or password.",
                }
            ),
            401,
        )

    user = User.query.filter_by(email=email, is_active=True).first()

    if user is None or not user.check_password(password):
        return (
            jsonify(
                {
                    "error": "unauthorized",
                    "message": "Invalid email or password.",
                }
            ),
            401,
        )

    session_id = str(uuid.uuid4())
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"sid": session_id},
    )
    refresh_token = create_refresh_token(
        identity=str(user.id),
        additional_claims={"sid": session_id},
    )

    return (
        jsonify(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "user": user.to_dict(),
            }
        ),
        200,
    )


@api_v1_bp.route("/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Issue an access token only if the user still exists and is active."""
    user = _get_active_user()

    if user is None:
        return _unauthorized_response()

    sid = get_jwt().get("sid")
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"sid": sid},
    )

    return jsonify({"access_token": access_token}), 200


@api_v1_bp.route("/auth/logout", methods=["DELETE"])
@jwt_required(verify_type=False)
def logout():
    """Revoke the entire token session supplied in this request."""
    token_data = get_jwt()
    jti = token_data["jti"]
    expiration = token_data["exp"]
    sid = token_data.get("sid")

    now = int(datetime.now(timezone.utc).timestamp())
    ttl = max(expiration - now, 1)
    if sid:
        ttl = max(ttl, int(30 * 24 * 60 * 60))

    redis_conn = extensions.redis_conn

    if redis_conn is None:
        logger.error("Redis is not initialized during logout")

        return (
            jsonify(
                {
                    "error": "service_unavailable",
                    "message": "Token revocation is temporarily unavailable.",
                }
            ),
            503,
        )

    try:
        redis_conn.setex(f"bl:{jti}", ttl, "1")
        if sid:
            redis_conn.setex(f"bl:sess:{sid}", ttl, "1")
    except RedisError:
        logger.exception("Redis error while revoking token")

        return (
            jsonify(
                {
                    "error": "service_unavailable",
                    "message": "Token revocation is temporarily unavailable.",
                }
            ),
            503,
        )

    return jsonify({"message": "Token successfully revoked."}), 200


@api_v1_bp.route("/auth/me", methods=["GET"])
@jwt_required()
def me():
    """Return the current active user's profile."""
    user = _get_active_user()

    if user is None:
        return _unauthorized_response()

    return jsonify(user.to_dict()), 200


@api_v1_bp.route("/auth/api-key", methods=["POST"])
@jwt_required()
def api_key():
    """Rotate and return the current active user's API key."""
    user = _get_active_user()

    if user is None:
        return _unauthorized_response()

    try:
        user.rotate_api_key()
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Database error while rotating API key")

        return (
            jsonify(
                {
                    "error": "internal_server_error",
                    "message": "Failed to rotate API key.",
                }
            ),
            500,
        )

    return (
        jsonify(
            {
                "api_key": user.api_key,
                "message": "Store it safely — shown only once.",
            }
        ),
        200,
    )
