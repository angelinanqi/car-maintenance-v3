"""Application profile and access status for a verified Supabase session."""
from datetime import datetime, timezone
import time
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from supabase_auth.errors import AuthError

from backend import auth, db, supabase_identity

router = APIRouter(prefix="/accounts", tags=["Accounts"])


class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    created_at: datetime
    updated_at: datetime
    role: Literal["user", "admin"] = "user"


class LoginResult(BaseModel):
    valid: bool
    user: UserPublic
    expires_at: datetime
    mfa_required: bool = False
    access_allowed: bool = True
    factor_ids: list[str] = Field(default_factory=list)


@router.get("/me", response_model=LoginResult)
def me(response: Response, identity=Depends(auth.current_session)):
    response.headers["Cache-Control"] = "no-store"
    return account_response(identity)


def account_response(identity):
    return {
        "valid": True,
        "user": identity["user"],
        "expires_at": datetime.fromtimestamp(identity["session"]["expires_at"], timezone.utc),
        "mfa_required": identity["mfa_required"],
        "access_allowed": identity["access_allowed"],
        "factor_ids": [factor.id for factor in identity["factors"]],
    }


class ProfileUpdate(BaseModel):
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def verified_account(identity=Depends(auth.current_session)):
    supabase_identity.require_full_access(identity)
    return identity


@router.patch("/me", response_model=LoginResult)
def update_profile(profile: ProfileUpdate, response: Response, identity=Depends(verified_account)):
    user = db.update("app_users", identity["user"]["id"], {"display_name": profile.display_name})
    response.headers["Cache-Control"] = "no-store"
    return account_response({**identity, "user": user})


class SignedInSession(BaseModel):
    id: UUID
    device: str
    last_active_at: datetime
    current: bool


def device_label(agent):
    agent = (agent or "").lower()
    platform = next(
        (label for markers, label in (
            (("iphone", "ipad"), "iOS"),
            (("android",), "Android"),
            (("windows",), "Windows"),
            (("macintosh",), "macOS"),
            (("linux",), "Linux"),
        ) if any(marker in agent for marker in markers)),
        "",
    )
    for marker, label in (
        ("edg/", "Edge"), ("edga/", "Edge"), ("edgios/", "Edge"),
        ("firefox", "Firefox"), ("fxios", "Firefox"),
        ("chrome", "Chrome"), ("crios", "Chrome"), ("safari", "Safari"),
    ):
        if marker in agent:
            return f"{label} on {platform}" if platform else label
    if "dart" in agent or "flutter" in agent:
        return f"MyRoadie on {platform}" if platform else "MyRoadie app"
    return platform or "Device"


def session_ids(identity):
    return {
        "p_user": identity["claims"]["sub"],
        "p_current": identity["claims"]["session_id"],
    }


@router.get("/sessions", response_model=list[SignedInSession])
def list_sessions(response: Response, identity=Depends(verified_account)):
    response.headers["Cache-Control"] = "no-store"
    params = session_ids(identity)
    rows = db.read_rows(db.client().rpc("account_sessions", params))
    return [
        {
            "id": row["id"],
            "device": device_label(row["user_agent"]),
            "last_active_at": row["last_active_at"],
            "current": row["id"] == params["p_current"],
        }
        for row in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: UUID, identity=Depends(verified_account)):
    params = session_ids(identity)
    if str(session_id) == params["p_current"]:
        raise HTTPException(400, "Use Sign out to end your current session.")
    revoked = db.client().rpc(
        "revoke_account_session", {**params, "p_target": str(session_id)}
    ).execute().data
    if not revoked:
        raise HTTPException(404, "This session is no longer available.")


@router.delete("/me", status_code=204)
def delete_account(identity=Depends(verified_account)):
    now = time.time()
    verified_recently = any(
        method.get("method") == "totp"
        and isinstance(method.get("timestamp"), (int, float))
        and now - 300 <= method["timestamp"] <= now + 30
        for method in identity["claims"].get("amr") or []
        if isinstance(method, dict)
    )
    if not verified_recently:
        raise HTTPException(403, "Verify a new authenticator code before deleting your account.")
    try:
        db.client().auth.admin.delete_user(identity["claims"]["sub"])
    except (AuthError, httpx.RequestError):
        raise HTTPException(
            503, "Account deletion could not be confirmed. Check your connection before trying again."
        ) from None
