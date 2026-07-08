import secrets
import string
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import ShortURL


urls_bp = Blueprint("urls", __name__)

@urls_bp.route("/", methods=["POST"])
@jwt_required()
def create_url():
    data = request.get_json(silent=True) or {}
    original_url = data.get("original_url")
    if not original_url:
        return {"error": "validation_error", "message": "Url required."}, 422
    title = data.get("title")
    alphabet = string.ascii_letters + string.digits
    slug = "".join(secrets.choice(alphabet) for _ in range(7))
    identity = get_jwt_identity()
    new_url = ShortURL(
        slug=slug,
        original_url=original_url,
        title=title,
        user_id=identity
    )
    db.session.add(new_url)
    db.session.commit()

    return new_url.to_dict(), 201

@urls_bp.route("/", methods=["GET"])
@jwt_required()
def list_urls():
    identity = get_jwt_identity()
    urls = ShortURL.query.filter_by(user_id=identity, is_active=True).all()
    
    return [url.to_dict() for url in urls], 200 