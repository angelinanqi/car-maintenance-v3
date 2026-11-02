"""Supabase user authentication and the administrative access boundary."""
from fastapi import Depends, HTTPException, Request

from backend import supabase_identity


def current_session(request: Request):
    authorization = request.headers.get("authorization", "")
    if not authorization:
        raise HTTPException(401, "Sign in to continue.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(401, "Invalid authentication credentials.")
    return supabase_identity.verified_identity(token)


def require_admin(request: Request, identity=Depends(current_session)):
    if identity["user"].get("role", "user") != "admin":
        raise HTTPException(403, "Administrator access is required.")
    supabase_identity.require_full_access(identity)
    return identity


def require_draft_access(request: Request):
    return require_admin(request, current_session(request))


def require_user(request: Request, identity=Depends(current_session)):
    supabase_identity.require_full_access(identity)
    return identity["user"]
