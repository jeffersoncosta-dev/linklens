import logging

from flask import Blueprint, jsonify, redirect, request

from app.core.shortener import cache_redirect, get_cached_redirect
from app.core.tracker import enqueue_click
from app.models import ShortURL

logger = logging.getLogger(__name__)

redirects_bp = Blueprint("redirects", __name__)


@redirects_bp.route("/<slug>", methods=["GET"])
def redirect_url(slug):
    url = ShortURL.query.filter_by(slug=slug).first()

    if url is None:
        return (
            jsonify(
                {
                    "error": "not_found",
                    "message": f"Slug '{slug}' not found.",
                }
            ),
            404,
        )

    if not url.is_accessible:
        if url.is_expired:
            reason = "expired"
        elif url.is_click_limit_reached:
            reason = "reached clicks limit"
        else:
            reason = "inactive"

        return (
            jsonify(
                {
                    "error": "link_unavailable",
                    "reason": reason,
                }
            ),
            410,
        )

    # O banco é a fonte de verdade; cache antigo não define o destino.
    target_url = url.original_url

    try:
        cached_url = get_cached_redirect(slug)

        if cached_url != target_url:
            cache_redirect(slug, target_url)
    except Exception:
        logger.exception("Redirect cache failed for slug=%s", slug)

    _track(url.id)

    return redirect(target_url, code=302)


def _track(url_id):
    """Enqueue analytics without blocking the redirect on failure."""
    try:
        enqueue_click(
            url_id=url_id,
            ip=request.remote_addr,
            user_agent=request.user_agent.string,
            referer=request.referrer,
        )
    except Exception:
        logger.exception(
            "Failed to enqueue click tracking for url_id=%s",
            url_id,
        )
