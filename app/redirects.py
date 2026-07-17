from flask import Blueprint, redirect, request, jsonify
from app.models import ShortURL
from app.core.shortener import get_cached_redirect, cache_redirect
from app.core.tracker import enqueue_click

redirects_bp = Blueprint("redirects", __name__)

@redirects_bp.route("/<slug>", methods=["GET"])
def redirect_url(slug):
    cached_url = get_cached_redirect(slug)
    if cached_url:
        _track(slug)
        return redirect(cached_url, code=302)
    url = ShortURL.query.filter_by(slug=slug).first()
    if not url:
        return jsonify({"error": "not_found", "message": f"Slug '{slug}' not found."}), 404
    if not url.is_accessible:
        if url.is_expired:
            return jsonify({"error": "link_unavailable", "reason": "expired"}), 410
        elif url.is_click_limit_reached:
            return jsonify({"error": "link_unavailable", "reason": "reached clicks limit"}), 410
        else:
            return jsonify({"error": "link_unavailable", "reason": "inactive"}), 410 
    cache_redirect(slug, url.original_url)
    _track(slug, url.id)
    return redirect(url.original_url, code=302)           

def _track(slug, url_id=None):
    try:
        if not url_id:
            url = ShortURL.query.filter_by(slug=slug).first()
            url_id = url.id
        enqueue_click(url_id=url_id, ip=request.remote_addr, user_agent=request.user_agent.string, referer=request.referrer)

    except Exception:
        pass