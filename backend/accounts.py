"""Persistence for application accounts."""
from backend import db


def find_by_email(email: str):
    rows = db.client().table("app_users").select("id,email,display_name,password_hash,role,created_at,updated_at").eq("email", email).limit(1).execute().data
    return rows[0] if rows else None


def create_user(email: str, display_name: str, password_hash: str):
    return db.client().table("app_users").insert({
        "email": email, "display_name": display_name, "password_hash": password_hash, "role": "user",
    }).execute().data[0]
