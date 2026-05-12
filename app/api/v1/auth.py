from flask import Blueprint, request
from app.extensions import db, limiter
from app.models import User
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
