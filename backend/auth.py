"""Application sessions and the administrative access boundary."""
import hashlib
import os
import secrets
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from threading import Lock
from urllib.parse import urlsplit
import jwt

from fastapi import Depends, HTTPException, Request

from backend import db
from backend import settings

COOKIE_NAME = "car_session"
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS") or "86400")
# Plain HTTP cookies are permitted by default only for local development.
local_origins = all(urlsplit(origin).hostname in {"localhost", "127.0.0.1", "::1"}
                    for origin in settings.CORS_ORIGINS)
COOKIE_SECURE = (os.getenv("SESSION_COOKIE_SECURE") or str(not local_origins)).lower() == "true"
if SESSION_TTL <= 0:
    raise ValueError("SESSION_TTL_SECONDS must be positive")

_attempts = OrderedDict()
_attempt_lock = Lock()


def limit_account_requests(request: Request):
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _attempt_lock:
        recent = [stamp for stamp in _attempts.pop(key, []) if now - stamp < 300]
        if len(recent) >= 20:
            _attempts[key] = recent
            raise HTTPException(429, "Too many account requests. Try again later.", headers={"Retry-After": "300"})
        recent.append(now)
        _attempts[key] = recent
        if len(_attempts) > 10000:
            _attempts.popitem(last=False)


def check_origin(request: Request):
    origin = request.headers.get("origin")
    if not origin:
        try:
            referer = urlsplit(request.headers.get("referer", ""))
        except ValueError:
            raise HTTPException(403, "Request origin is not allowed.") from None
        origin = f"{referer.scheme}://{referer.netloc}" if referer.netloc else ""
    if origin not in settings.CORS_ORIGINS:
        raise HTTPException(403, "Request origin is not allowed.")


def token_hash(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id):
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=SESSION_TTL)
    token = jwt.encode({
        "sub": str(user_id), "jti": secrets.token_urlsafe(32),
        "iat": now, "exp": expires, "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }, signing_key(), algorithm="HS256")
    row = db.insert("app_sessions", {
        "id": token_hash(token), "user_id": str(user_id),
        "created_at": now.isoformat(), "expires_at": expires.isoformat(),
        "csrf_token": secrets.token_urlsafe(32),
    })
    return token, row


def signing_key():
    if len(settings.JWT_SECRET.encode()) < 32:
        raise HTTPException(503, "Configure a strong JWT_SECRET on the backend.")
    return settings.JWT_SECRET


def session_token(request: Request):
    authorization = request.headers.get("authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Invalid authentication credentials.")
        return token, "bearer"
    return request.cookies.get(COOKIE_NAME), "cookie"


def current_session(request: Request):
    token, transport = session_token(request)
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    try:
        claims = jwt.decode(token, signing_key(), algorithms=["HS256"],
                            issuer=settings.JWT_ISSUER, audience=settings.JWT_AUDIENCE,
                            options={"require": ["sub", "jti", "iat", "exp", "iss", "aud"]})
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Your session is invalid or expired. Sign in again.") from None
    try:
        session = db.get("app_sessions", token_hash(token))
        if claims["sub"] != str(session["user_id"]):
            raise HTTPException(401, "Invalid authentication credentials.")
        expires = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
        if expires <= datetime.now(timezone.utc):
            raise HTTPException(401, "Your session has expired. Sign in again.")
        user = db.get("app_users", session["user_id"])
    except HTTPException as error:
        if error.status_code == 404:
            raise HTTPException(401, "Your session is no longer valid. Sign in again.") from None
        raise
    return {"session": session, "user": user, "transport": transport}


def check_csrf(request: Request, identity):
    if identity["transport"] == "cookie":
        check_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(supplied.encode(), identity["session"]["csrf_token"].encode()):
            raise HTTPException(403, "Invalid CSRF token. Reload and try again.")


def require_admin(request: Request, identity=Depends(current_session)):
    if identity["user"].get("role", "user") != "admin":
        raise HTTPException(403, "Administrator access is required.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_csrf(request, identity)
    return identity


def require_draft_access(request: Request):
    return require_admin(request, current_session(request))


def clear_session_cookie(response):
    response.delete_cookie(COOKIE_NAME, path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax")


def require_user(request: Request, identity=Depends(current_session)):
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        check_csrf(request, identity)
    return identity['user']
