"""Supabase-verified identity; application roles remain server managed."""
import time
from uuid import UUID

import httpx
from fastapi import HTTPException
from postgrest.exceptions import APIError
from supabase_auth.errors import AuthApiError, AuthError, AuthRetryableError, AuthUnknownError

from backend import db, settings


def verified_identity(token):
    try:
        # The SDK verifies asymmetric signatures against project JWKS and uses
        # Auth's user endpoint for legacy symmetric signing keys.
        result = db.client().auth.get_claims(token)
        claims = result['claims'] if result else {}
        audience = claims.get('aud')
        if (claims.get('iss') != settings.SUPABASE_URL.rstrip('/') + '/auth/v1'
                or not (audience == 'authenticated' or
                        isinstance(audience, list) and 'authenticated' in audience)
                or not isinstance(claims.get('exp'), (int, float))
                or claims['exp'] <= time.time()
                or not claims.get('session_id')):
            raise HTTPException(401, 'Your session is invalid or expired. Sign in again.')
        UUID(claims['sub'])
        provider_user = db.client().auth.get_user(token).user
        if provider_user.id != claims['sub']:
            raise HTTPException(401, 'Invalid authentication credentials.')
    except (AuthRetryableError, AuthUnknownError):
        raise HTTPException(503, 'Account verification is temporarily unavailable. Retry shortly.') from None
    except AuthApiError as error:
        if int(error.status or 0) >= 500 or str(error.status) == '429':
            raise HTTPException(503, 'Account verification is temporarily unavailable. Retry shortly.') from None
        raise HTTPException(401, 'Your session is invalid or expired. Sign in again.') from None
    except (AuthError, ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Your session is invalid or expired. Sign in again.') from None
    except httpx.RequestError:
        raise HTTPException(503, 'Account verification is temporarily unavailable. Retry shortly.') from None
    if not provider_user.email_confirmed_at:
        raise HTTPException(403, 'Confirm your email before continuing.')
    user = application_user(provider_user)
    factors = [factor for factor in provider_user.factors or []
               if factor.status == 'verified' and factor.factor_type == 'totp']
    # Enrollment is durable opt-in. Deleting factors directly at the provider
    # must not silently disable the application's MFA requirement.
    if factors and not user['mfa_required']:
        user = db.update('app_users', user['id'], {'mfa_required': True})
    required = user['role'] == 'admin' or user['mfa_required']
    return {'user': user, 'transport': 'supabase', 'claims': claims,
            'provider_user': provider_user, 'factors': factors,
            'mfa_required': required,
            'access_allowed': not required or claims.get('aal') == 'aal2',
            'session': {'expires_at': claims['exp']}}


def application_user(provider_user):
    rows = db.read_rows(db.client().table('app_users').select('*').eq('auth_user_id', provider_user.id))
    if rows:
        return rows[0]
    email = (provider_user.email or '').strip().lower()
    metadata = provider_user.user_metadata or {}
    name = str(metadata.get('display_name') or email.split('@')[0]).strip()[:100] or 'Driver'
    try:
        return db.insert('app_users', {'auth_user_id': provider_user.id,
                                     'email': email, 'display_name': name, 'role': 'user'})
    except APIError as error:
        if error.code != '23505':
            raise
        # A concurrent bootstrap can insert the same identity once.
        rows = db.read_rows(db.client().table('app_users').select('*').eq('auth_user_id', provider_user.id))
        if rows:
            return rows[0]
        raise HTTPException(409, 'This account needs an administrator to link its existing profile.') from None


def require_full_access(identity):
    if identity.get('transport') == 'supabase' and not identity['access_allowed']:
        raise HTTPException(403, 'Complete authenticator verification before accessing account data.')
