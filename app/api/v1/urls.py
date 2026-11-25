import uuid

from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import api_v1_bp
from app.core.shortener import generate_slug, validate_custom_slug, validate_url
from app.extensions import db, limiter, redis_conn
from app.models import ShortURL


@api_v1_bp.route("/urls", methods=["POST"])
@jwt_required()
@limiter.limit("30 per minute")
def create_url():
    """Creates a new shortened URL for the authenticated user.

    Expected JSON Payload:
        original_url (str): The target URL (Required).
        slug (str): A custom alias (Optional).
        title (str): An optional title for the URL.

    Returns:
        tuple: (dict containing url data, 201) on success.
        tuple: (dict containing error message, 400/409) on failure.
    """
    user_id = uuid.UUID(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    original_url = data.get("original_url")
    if not original_url:
        return (
            jsonify(
                {"error": "validation_error", "message": "original_url is required."}
            ),
            400,
        )
    if not isinstance(original_url, str) or not validate_url(original_url):
        return (
            jsonify(
                {"error": "validation_error", "message": "original_url is invalid."}
            ),
            422,
        )

    custom_slug = data.get("slug")
    if custom_slug:
        if not isinstance(custom_slug, str):
            return (
                jsonify(
                    {"error": "validation_error", "message": "slug must be a string."}
                ),
                422,
            )
        custom_slug = custom_slug.strip()
        valid, message = validate_custom_slug(custom_slug)
        if not valid:
            return jsonify({"error": "validation_error", "message": message}), 422
        slug = custom_slug
    else:
        slug = generate_slug()

    if ShortURL.query.filter_by(slug=slug).first():
        return jsonify({"error": "conflict", "message": "Slug already in use."}), 409

    new_url = ShortURL(
        original_url=original_url,
        slug=slug,
        title=data.get("title", ""),
        user_id=user_id,
    )

    try:
        db.session.add(new_url)
        db.session.commit()
        return jsonify(new_url.to_dict()), 201
    except SQLAlchemyError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": "internal_server_error",
                    "message": "Database error during creation.",
                }
            ),
            500,
        )


@api_v1_bp.route("/urls", methods=["GET"])
@jwt_required()
def list_urls():
    """Retrieves all shortened URLs created by the authenticated user.

    Returns:
        tuple: (list of dicts containing urls data, 200) on success.
    """
    user_id = uuid.UUID(get_jwt_identity())
    urls = (
        ShortURL.query.filter_by(user_id=user_id)
        .order_by(ShortURL.created_at.desc())
        .all()
    )

    return jsonify([url.to_dict() for url in urls]), 200


@api_v1_bp.route("/urls/<slug>", methods=["GET"])
@jwt_required()
def get_url(slug):
    """Retrieves details of a specific shortened URL.

    Returns:
        tuple: (dict containing url data, 200) on success.
        tuple: (dict containing error message, 403/404) on failure.
    """
    user_id = uuid.UUID(get_jwt_identity())
    url = ShortURL.query.filter_by(slug=slug).first()

    if not url:
        return jsonify({"error": "not_found", "message": "URL not found."}), 404

    if url.user_id != user_id:
        return (
            jsonify(
                {
                    "error": "forbidden",
                    "message": "This resource does not belong to the user.",
                }
            ),
            403,
        )

    return jsonify(url.to_dict()), 200


@api_v1_bp.route("/urls/<slug>", methods=["PUT"])
@jwt_required()
def update_url(slug):
    """Updates the original_url or title of a specific shortened URL.

    Returns:
        tuple: (dict containing updated url data, 200) on success.
    """
    user_id = uuid.UUID(get_jwt_identity())
    url = ShortURL.query.filter_by(slug=slug).first()

    if not url:
        return jsonify({"error": "not_found", "message": "URL not found."}), 404

    if url.user_id != user_id:
        return (
            jsonify(
                {
                    "error": "forbidden",
                    "message": "This resource does not belong to the user.",
                }
            ),
            403,
        )

    data = request.get_json(silent=True) or {}
    if "original_url" in data:
        original_url = data["original_url"]
        if not isinstance(original_url, str) or not validate_url(original_url):
            return (
                jsonify(
                    {"error": "validation_error", "message": "original_url is invalid."}
                ),
                422,
            )
        url.original_url = original_url
    if "title" in data:
        url.title = data["title"]

    try:
        db.session.commit()
        # Invalidação do cache para evitar que o worker de redirect use a URL antiga
        redis_conn.delete(f"url:{slug}")
        return jsonify(url.to_dict()), 200
    except SQLAlchemyError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": "internal_server_error",
                    "message": "Database error during update.",
                }
            ),
            500,
        )


@api_v1_bp.route("/urls/<slug>", methods=["DELETE"])
@jwt_required()
def delete_url(slug):
    """Deletes a specific shortened URL.

    Returns:
        tuple: (dict containing success message, 200) on success.
    """
    user_id = uuid.UUID(get_jwt_identity())
    url = ShortURL.query.filter_by(slug=slug).first()

    if not url:
        return jsonify({"error": "not_found", "message": "URL not found."}), 404

    if url.user_id != user_id:
        return (
            jsonify(
                {
                    "error": "forbidden",
                    "message": "This resource does not belong to the user.",
                }
            ),
            403,
        )

    try:
        db.session.delete(url)
        db.session.commit()
        # Invalidação do cache
        redis_conn.delete(f"url:{slug}")
        return jsonify({"message": "URL successfully deleted."}), 200
    except SQLAlchemyError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": "internal_server_error",
                    "message": "Database error during deletion.",
                }
            ),
            500,
        )
