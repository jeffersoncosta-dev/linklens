import re
import secrets
import string
from urllib.parse import urlparse
from app.models import ShortURL
from app.extensions import redis_conn

# Globals
ALPHABET = string.ascii_letters + string.digits
RESERVED_SLUGS = {"api", "health", "metrics", "admin", "static", "favicon.ico"}

def generate_slug(length=7):

    for attempt in range(10):

        slug = "".join(secrets.choice(ALPHABET) for _ in range(length))

        if not ShortURL.query.filter_by(slug=slug).first():

            return slug

    raise RuntimeError("Could not generate unique slug")

def validate_url(url):
    parsed = urlparse(url)
    
    return  parsed.scheme in ("http", "https") and bool(parsed.netloc)

def validate_custom_slug(slug) -> tuple[bool, str]:
    if slug in RESERVED_SLUGS:
        return (False, "This slug is reserved.")
    if not re.match(r"^[a-zA-Z0-9_-]{3,64}$", slug):
        return (False, "Slug must be 3-64 characters (letters, numbers, hyphens, underscores).")
    if ShortURL.query.filter_by(slug=slug).first(): 
        return (False, "Slug already taken.")
    return (True, "")

def cache_redirect (slug, url, ttl=300):
    return redis_conn.setex(f"redirect:{slug}", ttl, url)

def get_cached_redirect(slug):
    return redis_conn.get(f"redirect:{slug}")

def invalidate_cache(slug):
    return redis_conn.delete(f"redirect:{slug}")

     