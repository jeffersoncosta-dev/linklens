import hashlib
import ipaddress
import threading
import logging
import requests
import json
import time
from urllib.parse import urlparse
from user_agents import parse as ua_parse
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from app import extensions
from app.models import ShortURL, Click
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

CLICK_QUEUE = "queue:clicks"

def process_click_queue(app):
    """Continuously consumes the Redis queue and triggers click persistence.
    
    Runs in an infinite loop waiting for events in the CLICK_QUEUE via blpop.
    Requires the application context to instantiate database communication.

    Args:
        app (Flask): Main application instance.
    """
    

    while True:
        try:
            with app.app_context():
                raw = extensions.redis_conn.blpop(CLICK_QUEUE, timeout=5)
                if not raw:
                    continue
                _, payload = raw
                event = json.loads(payload)
                _persist_click(event)
        except Exception as exc:
            logger.error(f"Error persisting click:{exc}")
            time.sleep(5)

def start_click_worker(app):
    """Starts the click consumer process in a daemon thread.

    Args:
        app (Flask): Application instance injected into the worker.
    """

    t = threading.Thread(target=process_click_queue, args=(app,), daemon=True)
    t.start()

def _hash_ip(ip):
    """Anonymizes the IP address using the SHA-256 algorithm for privacy compliance.

    Args:
        ip (str): Visitor's IP address.

    Returns:
        str: Hexadecimal IP hash or an empty string.
    """

    if ip:
        return hashlib.sha256(ip.encode()).hexdigest()
    return ""

def _check_is_unique(url_id, ip_hash):
    """Checks if this is the first access from this IP to the URL in the last 30 days.

    Uses a Redis set with an expiration time to guarantee the unique visitors 
    metric without burdening the relational database.

    Args:
        url_id (int): Accessed URL ID.
        ip_hash (str): Anonymized IP hash.

    Returns:
        bool: True if it is a unique access, False otherwise.
    """

    key = f"unique:{url_id}:{ip_hash}"
    is_new = extensions.redis_conn.set(key, 1, nx=True, ex=86400*30)    
    return is_new

def enqueue_click(url_id, ip, user_agent, referer):
    """Assembles the event payload and enqueues it in Redis in a non-blocking manner.

    Args:
        url_id (int): Original URL ID.
        ip (str): Raw IP address of the visitor.
        user_agent (str): Full User-Agent header string.
        referer (str): Origin URL.
    """

    event = {
        "url_id": str(url_id),
        "ip_hash": _hash_ip(ip),
        "ip": ip,
        "user_agent": user_agent,
        "referer": referer,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    extensions.redis_conn.rpush(CLICK_QUEUE, json.dumps(event))

def _persist_click(event):
    """Enriches event data and persists the click in PostgreSQL via a transaction.

    Resolves geolocation and device type. Database failures trigger a silent 
    rollback to prevent the consumer from crashing.

    Args:
        event (dict): Dictionary containing raw click data.
    """

    url = db.session.get(ShortURL, event["url_id"])
    if not url:
        return
    ua = ua_parse(event.get("user_agent", ""))
    device_type = _get_device_type(ua)
    geo = _fetch_geo(event.get("ip", ""))
    ip_hash = event["ip_hash"]
    referer = _clean_referer(event.get("referer"))
    click = Click(
        url_id=url.id, 
        ip_hash=ip_hash, 
        is_unique=_check_is_unique(url.id, ip_hash),
        referer=referer,
        user_agent_raw=event.get("user_agent"),
        browser=ua.browser.family,
        os=ua.os.family,
        device_type=device_type,
        country=geo.get("country"),
        region=geo.get("region"),
        city=geo.get("city"),
    )
    try:
        db.session.add(click)
        url.click_count += 1
        db.session.commit()
    except SQLAlchemyError as e:
        logger.error(f"Database error while persisting click event for URL{event.get('url_id')}: {e}")
        db.session.rollback()


def _get_device_type(ua) -> str:
    """Classifies the parsed user agent into a device category.
    
    Bot check has priority because bot user-agent strings can
    sometimes also match mobile patterns.

    Args:
        ua (UserAgent): Iterable object from the user_agents library.

    Returns:
        str: 'bot', 'mobile', 'tablet', or 'desktop'.
    """

    if ua.is_bot:
        return "bot"
    if ua.is_mobile:
        return "mobile"
    if ua.is_tablet:
        return "tablet"
    return "desktop"

def _fetch_geo(ip):
    """Queries the ip-api.com API to extract geolocation.

    Discards requests for private/localhost network IPs and implements 
    a 2-second security timeout.

    Args:
        ip (str): Raw visitor IP.

    Returns:
        dict: Dictionary containing country, region, and city (or empty on failure).
    """

    if not ip:
        return {}
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return {}

    if address.is_private or address.is_reserved or address.is_loopback or address.is_link_local: 
        return {}
    try:
       response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,city,region", timeout=2)
    except requests.exceptions.RequestException:
        return {}

    data = response.json()
    if data.get("status") != "success":
        return {}
    return data

def _clean_referer(referer):
    """Isolates only the main domain (netloc) from the origin URL.

    Args:
        referer (str): Original HTTP Referer header string.

    Returns:
        str | None: The origin domain or None.
    """

    if not referer:
        return None
    return urlparse(referer).netloc
