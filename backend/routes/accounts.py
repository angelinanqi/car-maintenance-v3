from datetime import datetime
from uuid import UUID

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from postgrest.exceptions import APIError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend import accounts, auth, db, passwords

router = APIRouter(prefix="/accounts", tags=["Accounts"])


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class Registration(AccountInput):
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=1024)

    @field_validator("display_name")
    @classmethod
    def normalize_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Name is required")
        return value


class LoginInput(AccountInput):
    session_transport: Literal["cookie", "bearer"] = "cookie"


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
    csrf_token: str | None = None
    access_token: str | None = None
    token_type: str | None = None


@router.post("/register", response_model=UserPublic, status_code=201)
def register(request: Registration, http_request: Request):
    auth.limit_account_requests(http_request)
    password_hash = passwords.hash_password(request.password)
    try:
        return accounts.create_user(request.email, request.display_name, password_hash)
    except APIError as error:
        if error.code == "23505":
            raise HTTPException(409, "An account with this email already exists.") from None
        raise


@router.post("/login", response_model=LoginResult, response_model_exclude_none=True)
def login(request: LoginInput, http_request: Request, response: Response):
    auth.limit_account_requests(http_request)
    if request.session_transport == "cookie":
        auth.check_origin(http_request)
    user = accounts.find_by_email(request.email)
    if user is None or not passwords.verify_password(request.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")
    token, session = auth.create_session(user["id"])
    response.headers["Cache-Control"] = "no-store"
    result = {"valid": True, "user": user, "expires_at": session["expires_at"]}
    if request.session_transport == "cookie":
        response.set_cookie(auth.COOKIE_NAME, token, max_age=auth.SESSION_TTL,
                            secure=auth.COOKIE_SECURE, httponly=True, samesite="lax", path="/")
        result["csrf_token"] = session["csrf_token"]
    else:
        result.update(access_token=token, token_type="bearer")
    return result


@router.get("/me", response_model=LoginResult, response_model_exclude_none=True)
def me(response: Response, identity=Depends(auth.current_session)):
    response.headers["Cache-Control"] = "no-store"
    result = {"valid": True, "user": identity["user"], "expires_at": identity["session"]["expires_at"]}
    if identity["transport"] == "cookie":
        result["csrf_token"] = identity["session"]["csrf_token"]
    return result


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response):
    token, transport = auth.session_token(request)
    if token:
        try:
            identity = auth.current_session(request)
        except HTTPException as error:
            if error.status_code != 401:
                raise
            if transport == "cookie":
                auth.check_origin(request)
        else:
            auth.check_csrf(request, identity)
            db.delete("app_sessions", identity["session"]["id"])
    auth.clear_session_cookie(response)
    response.headers["Cache-Control"] = "no-store"
