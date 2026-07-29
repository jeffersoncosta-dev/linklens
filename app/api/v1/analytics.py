"""imports"""
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, cast, Date
from datetime import datetime 
from app.extensions import db, redis_conn
from app.models import Click, ShortURL, User
import uuid     
import logging
import json

"""blueprint"""
analytics_bp = Blueprint("analytics", __name__)

"""rotas"""
@analytics_bp.route("/<slug>/analytics", methods=["GET"])
@jwt_required()
def get_analytics(slug):
    cache_key = f"analytics:{slug}"
    try:
        cached_data = redis_conn.get(cache_key)
        if cached_data:
            return jasonify(json.loads(cached_data)), 200
    except Exception as e:
        current_app.logger.warning(f"Redis unavailable (read): {e}")

    user_id = uuid.UUID(get_jwt_identity())
    url = ShortURL.query.filter_by(slug=slug).first()
    if not url:
        return {"error": "not_found", "message": "URL not found."}, 404
    if uuid.UUID(url.user_id) != user_id:
        return {"error": "forbidden", "message": "This resource does not belong to the authenticated user."}, 403

    clicks_per_day_query = db.session.query(
        cast(Click.clicked_at, Date).label("date"),
        func.count(Click.id).label("clicks"),
        func.sum(cast(Click.is_unique, db.Integer)).label("unique_clicks")
    ).filter(
        Click.url_id == url.id
    ).group_by(
        cast(Click.clicked_at, Date)
    ).order_by(
        cast(Click.clicked_at, Date).desc()
    ).all()

    clicks_per_day_list = [
        {"date": date.strftime("%Y-%m-%d"), "clicks": clicks, "unique_clicks": unique_clicks}
        for date, clicks, unique_clicks in clicks_per_day_query]
    
    clicks_per_country_query = db.session.query(
        Click.country.label("country"),
        func.count(Click.id).label("clicks")
    ).filter(
        Click.url_id == url.id
    ).group_by(
        Click.country
    ).order_by(
        func.count(Click.id).desc()
    ).limit(10).all()
    
    clicks_per_country_list = [
        {"country": country, "clicks": clicks} 
        for country, clicks in clicks_per_country_query
        ]

    clicks_per_device_type_query = db.session.query(
        Click.device_type.label("device_type"),
        func.count(Click.id).label("clicks")
    ).filter(
        Click.url_id == url.id
    ).group_by(
        Click.device_type
    ).order_by(
        func.count(Click.id).desc()
    ).all()
    
    clicks_per_device_type_list = [
        {"device_type":device_type, "clicks": clicks} 
        for device_type, clicks in clicks_per_device_type_query
        ]

    clicks_per_browser_query = db.session.query(
        Click.browser.label("browser"),
        func.count(Click.id).label("clicks")
    ).filter(
        Click.url_id == url.id
    ).group_by(
        Click.browser
    ).order_by(
        func.count(Click.id).desc()
    ).limit(10).all()

    clicks_per_browser_list = [
        {"browser":browser, "clicks": clicks}
        for browser, clicks in clicks_per_browser_query
    ]
    clicks_per_referrer_query = db.session.query(
        Click.referer.label("referrer"),
        func.count(Click.id).label("clicks")
    ).filter(
        Click.url_id == url.id
    ).group_by(
        Click.referer
    ).order_by(
        func.count(Click.id).desc()
    ).limit(10).all()
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
        "clicks_per_referrer": clicks_per_referrer_list        
    }
    try:
        redis_conn.setex(cache_key, 300, json.dumps(response_dict))
    except Exception as e:
        current_app.logger.warning(f"Redis unavailable (write): {e}")

    return jsonify(response_dict)

@analytics_bp.route("/summary", methods=["GET"])
@jwt_required()
def get_summary():
    user_id = uuid.UUID(get_jwt_identity())

    user_urls = ShortURL.query.filter_by(user_id=user_id).order_by(ShortURL.created_at).desc().all()

    url_stats = db.session.query(
        func.count(ShortURL.id).label("total_urls"),
        func.sum(ShortURL.click_count).label("total_clicks")
    ).filter(ShortURL.user_id == user_id).first()

    unique_clicks = db.session.querry(
        func.sum(cast(Click.is_unique, db.Integer))
    ).join(ShortURL).filter(ShortURL.user_id == user_id).scalar()
    
    total_urls = url_stats.total_urls or 0
    total_clicks = url_stats.total_clicks or 0
    unique_clicks = unique_clicks or 0

    top_user_urls = ShortURL.query.filter_by(
        user_id=user_id
    ).order_by(
        ShortURL.click_count.desc()
    ).limit(5).all()

    return jsonify({
        "totals": {
            "urls": total_urls,
            "clicks": total_clicks,
            "unique_clicks": unique_clicks
        },
        "top_urls": [
            {"slug": u.slug, "title": u.title, "clicks": u.click_count} 
            for u in top_user_urls
        ],
        "all_urls": [
            {"slug": u.slug, "title": u.title, "clicks": u.click_count, "created_at": u.created_at.isoformat()}
            for u in user_urls
        ]
    }), 200