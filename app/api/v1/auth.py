from flask import Blueprint, request
from app.extensions import db, limiter, redis_conn
from app.models import User
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt
from datetime import datetime, timezone

auth_bp = Blueprint("auth", __name__)

 



@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password or len(password) < 8:
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
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return {"access_token": access_token}, 200 

@auth_bp.route("/logout", methods=["DELETE"])
@jwt_required()
def logout():
    token_date = get_jwt()
    jti = token_data["jti"]
    exp = token_data["exp"]
    now = int(datetime.now(timezone.utc).timestamp())
    ttl = exp - now
    redis_conn.setex(f"bl:{jti}", max(ttl,1), "1")
    return {"message": "successfully logged out"}, 200

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    identity = get_jwt_identity()
    user = db.session.get(User, identity)
    return user.to_dict(), 200