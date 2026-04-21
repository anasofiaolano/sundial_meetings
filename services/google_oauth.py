# services/google_oauth.py
#
# Google OAuth 2.0 for web server applications.
# Handles the full token lifecycle: auth URL → code exchange → refresh → revoke.
#
# Implementation notes (verified against Google docs, April 2025):
#
# - All HTTP calls are async (httpx.AsyncClient) — compatible with FastAPI.
# - Userinfo endpoint: openidconnect.googleapis.com/v1/userinfo (not the older oauth2 URL)
# - Scopes: "openid email profile" + gmail.readonly
# - access_type=offline + prompt=consent are both required to guarantee a refresh_token
#   in the response. Without prompt=consent, returning users get no refresh_token (silently).
# - IMPORTANT: While the OAuth consent screen is in "Testing" mode, refresh tokens expire
#   after 7 days. Publish the app to Production before giving reps access.
# - Google's granular permissions UI lets users uncheck individual scopes. Always verify
#   which scopes were actually granted in the token response — don't assume all were approved.
# - Refresh token is NOT returned on refresh — only a new access_token. Store the original
#   refresh_token permanently until the user disconnects.

import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx

GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:3004/api/email/callback/google")

AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL    = "https://oauth2.googleapis.com/token"
REVOKE_URL   = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
])

REQUIRED_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


def build_auth_url(state: str) -> str:
    """
    Return the Google OAuth consent screen URL to redirect the user to.
    The state parameter is a CSRF token — generate with generate_state() and
    store it server-side to verify on callback.
    """
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",   # required to receive a refresh_token
        "prompt":        "consent",   # required to always receive a refresh_token (even for returning users)
        "state":         state,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def generate_state() -> str:
    """Generate a cryptographically random state token for CSRF protection."""
    return secrets.token_urlsafe(32)


async def exchange_code(code: str) -> dict:
    """
    Exchange an authorization code for access_token + refresh_token.

    Returns the full token response dict. Key fields:
      - access_token     (short-lived, ~1 hour)
      - refresh_token    (long-lived — store this permanently)
      - expires_in       (seconds until access_token expires)
      - scope            (what was actually granted — may be less than requested)
      - id_token         (JWT with user identity, present because we included 'openid')

    Raises httpx.HTTPStatusError on failure.
    """
    async with httpx.AsyncClient() as client:
        r = await client.post(TOKEN_URL, data={
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri":  GOOGLE_REDIRECT_URI,
            "grant_type":    "authorization_code",
        })
        r.raise_for_status()
        tokens = r.json()

        # Verify the user granted Gmail access (granular permissions — user can uncheck scopes)
        granted = tokens.get("scope", "").split()
        if REQUIRED_SCOPE not in granted:
            raise ValueError(
                f"Gmail access was not granted. Granted scopes: {granted}. "
                f"Required: {REQUIRED_SCOPE}"
            )

        return tokens


async def refresh_access_token(refresh_token: str) -> dict:
    """
    Use a refresh token to get a new access_token.

    Returns dict with: access_token, expires_in, token_type, scope.
    Does NOT return a new refresh_token — the original stays valid.

    Raises httpx.HTTPStatusError if the refresh token is invalid or revoked
    (e.g. user changed password, revoked access, or Testing-mode 7-day expiry hit).
    Catch this and mark the connection as broken in the DB.
    """
    async with httpx.AsyncClient() as client:
        r = await client.post(TOKEN_URL, data={
            "refresh_token": refresh_token,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "grant_type":    "refresh_token",
        })
        r.raise_for_status()
        return r.json()


async def revoke_token(token: str) -> bool:
    """
    Revoke a token (pass the refresh_token to invalidate all derived access tokens).
    Call this when the user clicks Disconnect so access is fully removed from their
    Google account — not just deleted from our DB.
    Returns True on success, False if already revoked/invalid.
    """
    async with httpx.AsyncClient() as client:
        r = await client.post(
            REVOKE_URL,
            data={"token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return r.status_code == 200


async def get_user_info(access_token: str) -> dict:
    """
    Fetch the user's Google profile using the OIDC userinfo endpoint.
    Returns: { sub, email, email_verified, name, picture }
    Call this right after exchange_code() to get the email address to store.
    """
    async with httpx.AsyncClient() as client:
        r = await client.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        return r.json()


def token_expiry_from_response(token_response: dict) -> str:
    """
    Calculate absolute UTC expiry from a token response's expires_in field.
    Returns ISO 8601 string. Subtract 60s as a safety buffer.
    """
    expires_in = token_response.get("expires_in", 3600)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
    return expiry.isoformat()


def is_token_expired(expiry_iso: str) -> bool:
    """
    Return True if the access token is expired or within 60 seconds of expiry.
    Used to decide whether to refresh before making a Gmail API call.
    """
    try:
        expiry = datetime.fromisoformat(expiry_iso)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expiry
    except Exception:
        return True  # unparseable — treat as expired and refresh
