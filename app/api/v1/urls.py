import uuid
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.extensions import db
from app.models import ShortURL
from app.core.shortener import generate_slug, validate_url, validate_custom_slug, cache_redirect, invalidate_cache

urls_bp = Blueprint("urls", __name__)

@urls_bp.route("/", methods=["POST"])
@jwt_required()
def create_url():
    """ Creates a new shortened URL associated with authenticated user.
    Expected JSON Payload:
        original_url(str): The destination URL to be shortened (Required)
        title (str, optional): A descriptive title for the link.

    Returns:
        tuple: (dict containing the Short_URL data, 201) on success.
        tuple: (dict containing validation error message, 422) if original_url is missing.
    """
    data = request.get_json(silent=True) or {}
    original_url = data.get("original_url")
    if not original_url or not validate_url(original_url):
        return {"error": "validation_error", "message": "Invalid URL."}, 422
    title = data.get("title")
    custom_slug = data.get("slug")
    if custom_slug: 
        is_valid, error = validate_custom_slug(custom_slug)
        if not is_valid:
            return {"error": "validation_error", "message": error}, 422
        slug = custom_slug
    else:
        slug = generate_slug()
    user_id = uuid.UUID(get_jwt_identity())
    new_url = ShortURL(
        slug=slug,
        original_url=original_url,
        title=title,
        user_id=user_id 
    )
    db.session.add(new_url)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"error": "conflict", "message": "Slug collision, try again."}, 409  

    except SQLAlchemyError:
        db.session.rollback()
        return {"error": "internal_server_error", "message": "Failed to save URL."}, 500
    
    cache_redirect(slug, original_url)
    return new_url.to_dict(), 201
@urls_bp.route("/", methods=["GET"])
@jwt_required()
def list_urls():
    """Lists active URLs associated with authenticated user.
    Returns: 
        tuple: (list of dicts containing the ShortURL data, 200) on success.
    """
    user_id = uuid.UUID(get_jwt_identity())
    urls = ShortURL.query.filter_by(user_id=user_id, is_active=True).all()
    
    return [url.to_dict() for url in urls], 200 

@urls_bp.route("/<slug>", methods=["GET"])
@jwt_required()
def get_url(slug):
    """ Retrieves details of a unique URL associated with authenticated user.
    Args:
        slug (str): unique URL string identifier.
    
    Raises: 
        werkzeug.exceptions.NotFound (HTTP 404): If the URL does not exist or does not belong to the user.
    Returns:
        tuple: (dict containing ShortURL data, 200)  on success.
    """
    user_id = uuid.UUID(get_jwt_identity())
    url = ShortURL.query.filter_by(slug=slug, user_id=user_id).first_or_404()

    return url.to_dict(), 200

@urls_bp.route("/<slug>", methods=["PATCH"])
@jwt_required()
def update_url(slug):
    """ Updates an existing specific URL associated with the authenticated user.
    Args:
        slug (str): The unique string identifier for the URL.
    Expected JSON Payload:
        original_url (str, optional): The destination URL to be shortened.
        title (str, optional): A descriptive title for the link.
    Raises: 
        werkzeug.exceptions.NotFound (HTTP 404): If the URL does not exist or does not belong to the user.
    
    Returns:
        tuple: (dict containing ShortURL data, 200)  on success.    
    """
    user_id = uuid.UUID(get_jwt_identity())
    url = ShortURL.query.filter_by(slug=slug, user_id=user_id).first_or_404()
    updated_data = request.get_json(silent=True) or {}
    if "original_url" in updated_data:
        updated_url = updated_data.get("original_url")
        if not updated_url or not validate_url(updated_url):
            return {"error": "validation_error", "message": "Invalid URL."}, 422
        url.original_url = updated_url
    if "title" in updated_data:
        url.title = updated_data.get("title")
    
    try:
        db.session.commit()
        invalidate_cache(slug)
        return url.to_dict(), 200
    except SQLAlchemyError:
        db.session.rollback()
        return {"error": "internal_server_error", "message": "Failed to update URL."}, 500


@urls_bp.route("/<slug>", methods=["DELETE"])
@jwt_required()
def delete_url(slug):
    """Marks a specific URL as inactive (soft delete) specific URL associated with the authenticated user.
    Args:
        slug (str): The unique string identifier for the URL.
    Raises: 
        werkzeug.exceptions.NotFound (HTTP 404): If the URL does not exist or does not belong to the user.
    Returns:
        tuple: (empty string, 204)  on success.
        tuple: (dict containing error message, 409) if the URL is already inactive.  

    """
    user_id = uuid.UUID(get_jwt_identity())
    url = ShortURL.query.filter_by(slug=slug, user_id=user_id).first_or_404()

    if not url.is_active:
        return {"error": "already_inactive", "message": "Url already inactive."}, 409
    url.is_active = False
    try:
        db.session.commit()
        invalidate_cache(slug)
        return "", 204
    except SQLAlchemyError:
        db.session.rollback()
        return {"error": "internal_server_error", "message": "Failed to delete URL."}, 500


    





