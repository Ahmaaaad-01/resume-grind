"""Google OAuth verification, JWT token management, and FastAPI auth dependency.

Flow:
1. Frontend signs in with Google, gets an ID token
2. POST /api/auth/google sends the ID token here
3. We verify it with Google, find-or-create the user, return a JWT
4. All subsequent requests include Authorization: Bearer <jwt>
5. get_current_user() dependency extracts user_id from the JWT
"""

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone

import jwt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi import Depends, HTTPException, Request

log = logging.getLogger(__name__)

# JWT config
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72


def _get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET env var not set")
    return secret


def _get_google_client_id() -> str:
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID env var not set")
    return client_id


# ---------------------------------------------------------------------------
# Google token verification
# ---------------------------------------------------------------------------

def verify_google_token(token: str) -> dict:
    """Verify a Google ID token and return user info.

    Returns: {"email": str, "name": str, "google_id": str, "picture": str | None}
    Raises HTTPException 401 on invalid token.
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            _get_google_client_id(),
        )
        return {
            "email": idinfo["email"],
            "name": idinfo.get("name", ""),
            "google_id": idinfo["sub"],
            "picture": idinfo.get("picture"),
        }
    except ValueError as e:
        log.warning("Google token verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Google token")


# ---------------------------------------------------------------------------
# JWT creation / verification
# ---------------------------------------------------------------------------

def create_jwt(user_id: str, email: str) -> str:
    """Create a signed JWT for the given user."""
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and verify a JWT. Returns the payload dict.

    Raises HTTPException 401 on invalid/expired token.
    """
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_current_user(request: Request) -> dict:
    """FastAPI dependency — extract user from Authorization header.

    Returns: {"user_id": str, "email": str}
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header[7:]  # strip "Bearer "
    payload = decode_jwt(token)
    return {"user_id": payload["sub"], "email": payload["email"]}


def generate_user_id() -> str:
    """Generate a unique user ID."""
    return uuid.uuid4().hex
