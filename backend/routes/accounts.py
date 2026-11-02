"""Application profile and access status for a verified Supabase session."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr, Field

from backend import auth

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
    return {
        "valid": True,
        "user": identity["user"],
        "expires_at": datetime.fromtimestamp(identity["session"]["expires_at"], timezone.utc),
        "mfa_required": identity["mfa_required"],
        "access_allowed": identity["access_allowed"],
        "factor_ids": [factor.id for factor in identity["factors"]],
    }
