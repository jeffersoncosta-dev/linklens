# LinkLens

<div align="center">

**Production-oriented URL shortener API built with Flask, PostgreSQL, Redis and Docker**

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-black.svg)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-Pytest-brightgreen.svg)](#testing)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## Overview

**LinkLens** is a full-featured URL shortening and analytics API designed to demonstrate backend engineering practices beyond a basic CRUD application.

It provides secure short-link creation, fast redirect handling, asynchronous click tracking, device-aware routing, analytics, authentication, rate limiting, health checks and containerized deployment.

The project separates the **redirect hot path** from the **analytics pipeline**: redirects are served immediately from a Redis-backed cache, while click events are queued and processed asynchronously. This reduces redirect latency and prevents analytics failures from affecting user experience.

## Key Differentiators

- **Redis-backed redirect cache** — reduces database reads on the most frequently accessed route.
- **Asynchronous click tracking** — click events are enqueued in Redis and consumed by a background worker, keeping redirects non-blocking.
- **Device-based routing** — the same short link can redirect iOS users to the App Store and Android users to Google Play.
- **Privacy-conscious analytics** — visitor IP addresses are hashed with SHA-256 before persistence; raw IPs are not stored.
- **JWT authentication with Redis blacklist** — supports stateless access tokens and real logout/revocation through token `jti` invalidation.
- **HATEOAS-oriented API responses** — resource representations include navigational links.
- **Production readiness signals** — Dockerized environment, non-root container user, database migrations, health checks, structured error responses and rate limiting.
- **Testable architecture** — Application Factory pattern, dependency injection-friendly extensions and a pytest suite with coverage reporting.

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Web framework | Flask |
| Database | PostgreSQL 16 |
| ORM / migrations | SQLAlchemy + Flask-SQLAlchemy + Alembic |
| Cache / queue | Redis 7 |
| Authentication | Flask-JWT-Extended, JWT access and refresh tokens |
| Rate limiting | Flask-Limiter |
| Testing | Pytest, pytest-cov |
| HTTP client | Requests |
| QR codes | qrcode |
| Containerization | Docker, Docker Compose |
| Production server | Gunicorn |

## Features

### URL shortening

- Create short URLs with optional authentication.
- Generate cryptographically random slugs using `secrets`.
- Create custom slugs with validation and reserved-word protection.
- Set expiration dates and maximum click limits.
- Activate, deactivate, update and delete short URLs.
- Retrieve paginated lists of URLs owned by the authenticated user.
- Generate QR codes for short links.

### Redirect engine

- Redirect users using HTTP `302` responses.
- Serve redirects from Redis cache when available.
- Fall back to PostgreSQL when cache is missing.
- Invalidate cache when a URL is updated, deactivated or deleted.
- Return `410 Gone` for inactive, expired or click-limited links.
- Return structured JSON errors for invalid or unknown slugs.

### Analytics

- Track clicks asynchronously through a Redis queue.
- Identify unique visitors using an anonymized IP hash.
- Detect browser, operating system and device type.
- Store referrer domain rather than the full referrer URL.
- Aggregate analytics by day, country, device type, browser and referrer.
- Provide account-level analytics summaries and top-performing links.

### Security and reliability

- JWT-based authentication with short-lived access tokens.
- Refresh token flow for obtaining new access tokens.
- Logout implemented through Redis-backed JWT blacklist.
- Password hashing with Werkzeug.
- API key rotation.
- Rate limiting for sensitive endpoints.
- Health checks for PostgreSQL and Redis.
- Global JSON error handlers for `404`, `405`, `429` and `500`.
- Non-root Docker user and graceful Gunicorn shutdown.

## Architecture

```text
Client
  │
  ├── POST /api/v1/urls ─────────────► Flask API ──► PostgreSQL
  │                                        │
  │                                        └──► Redis cache
  │
  ├── GET /<slug> ────────────────────► Redirect hot path
  │                                        │
  │                                        ├── Redis cache hit ──► 302 redirect
  │                                        └── PostgreSQL fallback ──► 302 redirect
  │
  └── Click event ───────────────────► Redis queue ──► Background worker ──► PostgreSQL
```

### Architectural decisions

| Decision | Reason |
|---|---|
| Redis cache for redirects | Avoids repeated PostgreSQL queries for high-traffic slugs and keeps the redirect path fast. |
| Redis queue for analytics | Separates the critical redirect path from non-critical analytics processing. |
| Background worker | Processes click events asynchronously, preventing geolocation or parsing failures from delaying redirects. |
| SHA-256 IP hashing | Avoids persisting raw IP addresses, supporting privacy-conscious data handling and LGPD/GDPR-oriented design. |
| UUID primary keys | Avoids exposing sequential identifiers and is suitable for distributed systems. |
| Composite database indexes | Optimizes common analytics queries, such as clicks grouped by URL and timestamp. |
| JWT blacklist in Redis | Enables immediate token revocation while retaining a stateless authentication model. |
| Application Factory | Makes the application testable and allows distinct configurations for development, testing and production. |

## Quick Start

### Prerequisites

- Python 3.12
- Docker Desktop
- Git

For Python version management, this project uses `pyenv`. On Linux/macOS, install it with:

```bash
curl -fsSL [https://pyenv.run](https://pyenv.run) | bash
```

On Windows, use `pyenv-win`, which provides native Windows Python version management. [1][2]

Install and activate the project Python version:

```bash
pyenv install 3.12.3
pyenv local 3.12.3
```

Docker Compose is used to run PostgreSQL, Redis and the application locally. [3]

### Run the project

```bash
git clone [https://github.com/jeffersoncosta/linklens.git](https://github.com/jeffersoncosta/linklens.git)
cd linklens
cp .env.example .env
docker compose up --build
```

The API will be available at:

```text
http://localhost:5000
```

### Health check

```bash
curl http://localhost:5000/api/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "services": {
    "postgres": "ok",
    "redis": "ok"
  }
}
```

## API Documentation

Base URL:

```text
http://localhost:5000/api/v1
```

| Method | Endpoint | Description | Authentication |
|---|---|---|---|
| `POST` | `/auth/register` | Create a new user account | Public |
| `POST` | `/auth/login` | Authenticate and receive JWT tokens | Public |
| `POST` | `/auth/refresh` | Issue a new access token | Refresh token |
| `DELETE` | `/auth/logout` | Revoke the current access token | Bearer token |
| `GET` | `/auth/me` | Retrieve authenticated user profile | Bearer token |
| `POST` | `/auth/api-key` | Rotate the user API key | Bearer token |
| `POST` | `/urls` | Create a short URL | Optional Bearer token |
| `GET` | `/urls` | List authenticated user URLs | Bearer token |
| `GET` | `/urls/<slug>` | Retrieve a specific URL | Bearer token |
| `PATCH` | `/urls/<slug>` | Update a URL | Bearer token |
| `DELETE` | `/urls/<slug>` | Delete a URL | Bearer token |
| `GET` | `/urls/<slug>/qr` | Generate a QR code for a short URL | Public |
| `GET` | `/urls/<slug>/analytics` | Retrieve URL analytics | Bearer token |
| `GET` | `/analytics/summary` | Retrieve account-level analytics | Bearer token |
| `GET` | `/health` | Check PostgreSQL and Redis availability | Public |
| `GET` | `/<slug>` | Redirect to the destination URL | Public |

## Example Requests

### Register

```bash
curl -X POST http://localhost:5000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "strong-password-123"
  }'
```

### Login

```bash
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "strong-password-123"
  }'
```

### Create a short URL

```bash
curl -X POST http://localhost:5000/api/v1/urls \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "url": "[https://example.com](https://example.com)",
    "slug": "my-link",
    "title": "Example campaign"
  }'
```

### Access the short URL

```bash
curl -i http://localhost:5000/my-link
```

Expected response:

```text
HTTP/1.1 302 FOUND
Location: [https://example.com](https://example.com)
```

### Retrieve analytics

```bash
curl http://localhost:5000/api/v1/urls/my-link/analytics \
  -H "Authorization: Bearer <access_token>"
```

## API Response Pattern

Successful responses use a consistent structure:

```json
{
  "data": {},
  "meta": {},
  "links": {}
}
```

Error responses use a predictable JSON format:

```json
{
  "error": "validation_error",
  "message": "Invalid request payload."
}
```

| Status | Meaning |
|---|---|
| `200` | Request succeeded |
| `201` | Resource created |
| `204` | Resource deleted |
| `401` | Missing, invalid or revoked authentication |
| `404` | Resource not found |
| `409` | Resource conflict, such as duplicate email or slug |
| `410` | Short URL is inactive, expired or has reached its click limit |
| `422` | Validation error |
| `429` | Rate limit exceeded |
| `500` | Internal server error |
| `503` | One or more infrastructure dependencies are unavailable |

## Project Structure

```text
linklens/
├── app/
│   ├── __init__.py               # Application Factory and app initialization
│   ├── config.py                  # Development, testing and production settings
│   ├── extensions.py              # SQLAlchemy, Alembic, JWT, Limiter and Redis
│   ├── redirects.py               # High-performance redirect route
│   ├── models/
│   │   ├── user.py                # User, password hashing and API keys
│   │   ├── url.py                 # ShortURL entity and business rules
│   │   └── click.py               # Click analytics and indexed fields
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py            # Authentication endpoints
│   │       ├── urls.py            # URL CRUD and QR code generation
│   │       ├── analytics.py       # Click analytics and summaries
│   │       └── health.py          # Infrastructure health checks
│   └── core/
│       ├── shortener.py           # Slug generation, validation and Redis cache
│       └── tracker.py             # Click queue, worker and analytics enrichment
├── tests/
│   ├── conftest.py                # Pytest fixtures
│   ├── test_auth.py               # Authentication tests
│   ├── test_urls.py               # URL CRUD tests
│   └── test_redirects.py          # Redirect and cache tests
├── migrations/                    # Alembic migrations
├── scripts/
│   └── entrypoint.sh              # Migration execution and Gunicorn startup
├── .env.example                   # Environment variable template
├── docker-compose.yml             # App, PostgreSQL and Redis services
├── Dockerfile                     # Production-oriented container image
├── requirements.txt
├── requirements-dev.txt
├── run.py
└── README.md
```

## Environment Variables

Copy `.env.example` to `.env` before running the application:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `FLASK_ENV` | Application environment: `development`, `testing` or `production` |
| `SECRET_KEY` | Flask secret key |
| `JWT_SECRET_KEY` | Secret key used to sign JWT tokens |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `BASE_URL` | Public base URL used to generate short links |
| `SLUG_LENGTH` | Length of automatically generated slugs |
| `REDIRECT_CACHE_TTL` | Redis cache expiration time in seconds |

Example:

```env
FLASK_ENV=development
SECRET_KEY=change-me
JWT_SECRET_KEY=change-me
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/linklens
REDIS_URL=redis://redis:6379/0
BASE_URL=http://localhost:5000
SLUG_LENGTH=7
REDIRECT_CACHE_TTL=300
```

Never commit real credentials, tokens or production database URLs.

## Database

LinkLens uses PostgreSQL with SQLAlchemy and Alembic migrations.

Main entities:

| Table | Purpose |
|---|---|
| `users` | Stores accounts, hashed passwords and API keys |
| `short_urls` | Stores shortened links, ownership, limits and status |
| `clicks` | Stores anonymized click analytics |

Important indexes:

- `users.email`
- `users.api_key`
- `short_urls.slug`
- `short_urls.user_id`
- `short_urls.click_count`
- `short_urls.user_id` + `short_urls.is_active`
- `clicks.url_id`
- `clicks.clicked_at`
- `clicks.url_id` + `clicks.clicked_at`
- `clicks.url_id` + `clicks.country`

## Testing

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
pytest -v
```

Run tests with coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

Coverage target:

```text
80% or higher
```

Test coverage includes:

- User registration and login
- Invalid credentials and duplicate accounts
- JWT refresh and logout revocation
- URL creation, validation and ownership
- Custom slug validation
- Pagination
- URL update and deletion
- Redirect behavior
- Cache invalidation
- Expired, inactive and click-limited links

## Docker

Build and start all services:

```bash
docker compose up --build
```

Check running services:

```bash
docker compose ps
```

View application logs:

```bash
docker compose logs -f app
```

Stop the environment:

```bash
docker compose down
```

The application container runs as a non-root user and uses Gunicorn as the production WSGI server.

## Security Considerations

- Passwords are stored only as hashes.
- JWT access tokens have a short expiration window.
- Refresh tokens enable session renewal without exposing long-lived access tokens.
- Logout adds the token `jti` to a Redis blacklist until its expiration.
- Login responses do not reveal whether an email exists.
- IP addresses are hashed before persistence.
- Referrer values are reduced to domain-level data.
- Rate limiting protects authentication and URL creation endpoints.
- Error responses avoid exposing internal stack traces.

## Roadmap

- [ ] Add OpenAPI/Swagger documentation.
- [ ] Add CI pipeline with GitHub Actions.
- [ ] Add Redis Sentinel or managed Redis support.
- [ ] Add background worker as a separate container.
- [ ] Add pagination metadata links using RFC 5988.
- [ ] Add integration tests with Testcontainers.
- [ ] Add observability with structured logs and metrics.
- [ ] Add A/B testing for device-based routing.
- [ ] Add webhook notifications for click milestones.
- [ ] Add admin dashboard for link management.



## Author

Built as a backend engineering portfolio project focused on Flask, PostgreSQL, Redis, asynchronous processing, API design, security and containerized deployment.