import uuid
from flask import Blueprint, request
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db, limiter, redis_conn
from app.models import User
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt, jwt_required, get_jwt_identity
from datetime import datetime, timezone

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    """Registers a new user in the system.

    Expected JSON Payload:
        email (str): The user's email address (Required).
        password (str): The user's password, minimum 8 characters (Required).

    Returns:
        tuple: (dict containing success message and user data, 201) on success.
        tuple: (dict containing error message, 422) if validation fails.
        tuple: (dict containing error message, 409) if email is already registered.
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password or len(password) < 8 or len(password) > 128:
        return {"error": "validation_error", "message": "Email and password are required."}, 422
        
    if User.query.filter_by(email=email).first():
        return {"error": "conflict", "message": "email already registered"}, 409
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return {"message": "user created", "user": user.to_dict()}, 201

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("20 per hour")
def login():
    """Authenticates a user and issues JWT tokens.

    Expected JSON Payload:
        email (str): The user's registered email (Required).
        password (str): The user's password (Required).

    Returns:
        tuple: (dict containing access_token, refresh_token, and user data, 200) on success.
        tuple: (dict containing error message, 401) if credentials are invalid.
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user = User.query.filter_by(email=email, is_active=True).first() 
    if not user or not user.check_password(password):
        return {"error": "unauthorized", "message": "Invalid email or password"}, 401

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "user": user.to_dict()
    }, 200

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Generates a new access token using a valid refresh token.

    Returns:
        tuple: (dict containing the new access_token, 200) on success.
    """
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return {"access_token": access_token}, 200 

@auth_bp.route("/logout", methods=["DELETE"])
@jwt_required()
def logout():
    """Logs out the current user by blacklisting their access token in Redis.

    Returns:
        tuple: (dict containing success message, 200) on success.
    """
    token_data = get_jwt()
    jti = token_data["jti"]
    exp = token_data["exp"]
    now = int(datetime.now(timezone.utc).timestamp())
    ttl = exp - now
    redis_conn.setex(f"bl:{jti}", max(ttl,1), "1")
    return {"message": "successfully logged out"}, 200

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """Retrieves the profile information of the authenticated user.

    Returns:
        tuple: (dict containing the user data, 200) on success.
    """
    user_id = uuid.UUID(get_jwt_identity())
    user = db.session.get(User, user_id)
    return user.to_dict(), 200


@auth_bp.route("/api-key", methods=["POST"])
@jwt_required()
def api_key():
    """Rotates and returns a new API key for the authenticated user.

    Returns:
        tuple: (dict containing the new api_key and a security warning, 200) on success.
    """
    user_id = uuid.UUID(get_jwt_identity())
    user = db.session.get(User, user_id)
    user.rotate_api_key()
    try:
        db.session.commit()
        return {
        "api_key": user.api_key,
        "message": "Store it safely- shown only once."
    }, 200

    except SQLAlchemyError:
        db.session.rollback()
        return {"error": "internal_server_error", "message": "Failed to rotate api key."}, 500

