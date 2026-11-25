import json
import uuid

from flask import current_app, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import Date, cast, func

from app import extensions
from app.api.v1 import api_v1_bp
from app.extensions import db
from app.models import Click, ShortURL


@api_v1_bp.route("/analytics/<slug>", methods=["GET"])
@jwt_required()
def get_analytics(slug):
    """Retrieves detailed analytics for a specific shortened URL.

    Expected Path Parameter:
        slug (str): The alias of the shortened URL.

    Returns:
        tuple: (dict containing analytics data, 200) on success.
        tuple: (dict containing error message, 403/404) on failure.
    """
    cache_key = f"analytics:{slug}"
    try:
        cached_data = extensions.redis_conn.get(cache_key)
        if cached_data:
            return jsonify(json.loads(cached_data)), 200
    except Exception as e:
        current_app.logger.warning(f"Redis unavailable (read): {e}")

    user_id = uuid.UUID(get_jwt_identity())
    url = ShortURL.query.filter_by(slug=slug).first()

    if not url:
        return jsonify({"error": "not_found", "message": "URL not found."}), 404

    if url.user_id != user_id:
        return (
            jsonify(
                {
                    "error": "forbidden",
                    "message": "This resource does not belong to the authenticated user.",
                }
            ),
            403,
        )

    clicks_per_day_query = (
        db.session.query(
            cast(Click.clicked_at, Date).label("date"),
            func.count(Click.id).label("clicks"),
            func.sum(cast(Click.is_unique, db.Integer)).label("unique_clicks"),
        )
        .filter(Click.url_id == url.id)
        .group_by(cast(Click.clicked_at, Date))
        .order_by(cast(Click.clicked_at, Date).desc())
        .all()
    )

    clicks_per_day_list = [
        {
            "date": date.strftime("%Y-%m-%d"),
            "clicks": clicks,
            "unique_clicks": unique_clicks,
        }
        for date, clicks, unique_clicks in clicks_per_day_query
    ]

    clicks_per_country_query = (
        db.session.query(
            Click.country.label("country"), func.count(Click.id).label("clicks")
        )
        .filter(Click.url_id == url.id)
        .group_by(Click.country)
        .order_by(func.count(Click.id).desc())
        .limit(10)
        .all()
    )

    clicks_per_country_list = [
        {"country": country, "clicks": clicks}
        for country, clicks in clicks_per_country_query
    ]

    clicks_per_device_type_query = (
        db.session.query(
            Click.device_type.label("device_type"), func.count(Click.id).label("clicks")
        )
        .filter(Click.url_id == url.id)
        .group_by(Click.device_type)
        .order_by(func.count(Click.id).desc())
        .all()
    )

    clicks_per_device_type_list = [
        {"device_type": device_type, "clicks": clicks}
        for device_type, clicks in clicks_per_device_type_query
    ]

    clicks_per_browser_query = (
        db.session.query(
            Click.browser.label("browser"), func.count(Click.id).label("clicks")
        )
        .filter(Click.url_id == url.id)
        .group_by(Click.browser)
        .order_by(func.count(Click.id).desc())
        .limit(10)
        .all()
    )

    clicks_per_browser_list = [
        {"browser": browser, "clicks": clicks}
        for browser, clicks in clicks_per_browser_query
    ]

    clicks_per_referrer_query = (
        db.session.query(
            Click.referer.label("referrer"), func.count(Click.id).label("clicks")
        )
        .filter(Click.url_id == url.id)
        .group_by(Click.referer)
        .order_by(func.count(Click.id).desc())
        .limit(10)
        .all()
    )

    clicks_per_referrer_list = [
        {"referrer": referrer, "clicks": clicks}
        for referrer, clicks in clicks_per_referrer_query
    ]

    response_dict = {
        "slug": url.slug,
        "original_url": url.original_url,
        "title": url.title,
        "click_count": url.click_count,
        "clicks_per_day": clicks_per_day_list,
        "clicks_per_country": clicks_per_country_list,
        "clicks_per_device_type": clicks_per_device_type_list,
        "clicks_per_browser": clicks_per_browser_list,
        "clicks_per_referrer": clicks_per_referrer_list,
    }

    try:
        extensions.redis_conn.setex(cache_key, 300, json.dumps(response_dict))
    except Exception as e:
        current_app.logger.warning(f"Redis unavailable (write): {e}")

    return jsonify(response_dict), 200


@api_v1_bp.route("/analytics/summary", methods=["GET"])
@jwt_required()
def get_summary():
    """Retrieves an aggregated analytics summary for all URLs owned by the user.

    Returns:
        tuple: (dict containing total stats and lists of urls, 200) on success.
    """
    user_id = uuid.UUID(get_jwt_identity())

    user_urls = (
        ShortURL.query.filter_by(user_id=user_id)
        .order_by(ShortURL.created_at.desc())
        .all()
    )

    url_stats = (
        db.session.query(
            func.count(ShortURL.id).label("total_urls"),
            func.sum(ShortURL.click_count).label("total_clicks"),
        )
        .filter(ShortURL.user_id == user_id)
        .first()
    )

    unique_clicks = (
        db.session.query(func.sum(cast(Click.is_unique, db.Integer)))
        .join(ShortURL)
        .filter(ShortURL.user_id == user_id)
        .scalar()
    )

    total_urls = url_stats.total_urls or 0
    total_clicks = url_stats.total_clicks or 0
    unique_clicks = unique_clicks or 0

    top_user_urls = (
        ShortURL.query.filter_by(user_id=user_id)
        .order_by(ShortURL.click_count.desc())
        .limit(5)
        .all()
    )

    return (
        jsonify(
            {
                "totals": {
                    "urls": total_urls,
                    "clicks": total_clicks,
                    "unique_clicks": unique_clicks,
                },
                "top_urls": [
                    {"slug": u.slug, "title": u.title, "clicks": u.click_count}
                    for u in top_user_urls
                ],
                "all_urls": [
                    {
                        "slug": u.slug,
                        "title": u.title,
                        "clicks": u.click_count,
                        "created_at": u.created_at.isoformat(),
                    }
                    for u in user_urls
                ],
            }
        ),
        200,
    )
