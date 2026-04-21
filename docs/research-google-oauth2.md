# Research: Google OAuth 2.0 for Web Server Applications (2024-2025)

**Date researched:** 2026-04-14
**Sources:** Official Google Identity documentation, Google Cloud blog, googleapis.dev

---

## 1. Endpoint URLs

### Authorization Endpoint
```
https://accounts.google.com/o/oauth2/v2/auth
```
This is the current v2 endpoint. The older `https://accounts.google.com/o/oauth2/auth` also works but v2 is canonical.

### Token Exchange Endpoint (authorization code -> tokens, AND refresh)
```
https://oauth2.googleapis.com/token
```
Used for BOTH the initial code exchange AND refreshing access tokens. Same endpoint, different `grant_type`.

### Token Revocation Endpoint
```
https://oauth2.googleapis.com/revoke
```
Method: POST
Headers: `Content-Type: application/x-www-form-urlencoded`
Body param: `token=<access_token_or_refresh_token>`

You can pass either an access token or a refresh token. Revoking a refresh token invalidates all access tokens derived from it.

### Userinfo Endpoint
```
https://openidconnect.googleapis.com/v1/userinfo
```
Method: GET
Headers: `Authorization: Bearer <access_token>`

Returns JSON with `email`, `email_verified`, `name`, `picture`, `sub` (Google user ID), etc., depending on scopes granted.

Also discoverable via the OpenID Connect discovery document:
```
https://accounts.google.com/.well-known/openid-configuration
```

---

## 2. Scopes

### For Gmail read-only access:
```
https://www.googleapis.com/auth/gmail.readonly
```

### For getting user email address (two equivalent options):
```
email
```
or the fully qualified form:
```
https://www.googleapis.com/auth/userinfo.email
```
The short form `email` is the OpenID Connect scope and is preferred for OIDC flows.

### For profile info (name, picture):
```
profile
```
or:
```
https://www.googleapis.com/auth/userinfo.profile
```

### Typical combined scope string for this project:
```
openid email profile https://www.googleapis.com/auth/gmail.readonly
```

**Note on `openid` scope:** Including `openid` puts you in OIDC mode and causes the token response to include an `id_token` (a signed JWT with user identity claims). You can decode the `id_token` to get the email without calling the userinfo endpoint, but calling userinfo is also fine.

---

## 3. Authorization URL Parameters

### Required:
| Parameter | Value |
|-----------|-------|
| `client_id` | Your OAuth 2.0 client ID from Google Cloud Console |
| `redirect_uri` | Must exactly match a URI registered in Cloud Console; must be HTTPS in production (localhost exempted) |
| `response_type` | `code` |
| `scope` | Space-delimited scope string |

### Required for offline access (refresh tokens):
| Parameter | Value | Notes |
|-----------|-------|-------|
| `access_type` | `offline` | **Required** to receive a refresh token. Without this, you only get an access token (1-hour lifetime). |
| `prompt` | `consent` | **Required** to reliably receive the refresh token on EVERY authorization, not just the first one. See gotcha below. |

### Highly recommended:
| Parameter | Value | Notes |
|-----------|-------|-------|
| `state` | Random CSRF token | Server MUST validate this on callback. Prevents CSRF attacks. |
| `include_granted_scopes` | `true` | Enables incremental authorization - previously granted scopes are included in new auth requests |

### Optional:
| Parameter | Value | Notes |
|-----------|-------|-------|
| `login_hint` | email or sub | Pre-fills the email field or bypasses account chooser |
| `prompt` | `select_account` | Forces account chooser even if user is already signed in |
| `prompt` | `none` | Silent auth - returns error if interaction required |

### The `prompt=consent` gotcha (CRITICAL):
Google only returns a `refresh_token` in the token exchange response **the first time** a user authorizes your app, or when you force re-consent with `prompt=consent`. If a user has already authorized and you don't include `prompt=consent`, the token exchange response will NOT contain a `refresh_token`. This is a very common source of bugs where apps work in development but fail for returning users.

**When to use `prompt=consent`:**
- Always, if you need a refresh token on every auth flow (e.g., storing per-user tokens in a database)
- Or: handle the case where `refresh_token` is absent by checking if you already have one stored

**Example full authorization URL:**
```
https://accounts.google.com/o/oauth2/v2/auth
  ?client_id=YOUR_CLIENT_ID
  &redirect_uri=https://yourapp.com/oauth/callback
  &response_type=code
  &scope=openid%20email%20profile%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.readonly
  &access_type=offline
  &prompt=consent
  &state=RANDOM_CSRF_TOKEN
```

---

## 4. Token Exchange Request

### Authorization code -> tokens (initial exchange):
```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

code=AUTHORIZATION_CODE
&client_id=YOUR_CLIENT_ID
&client_secret=YOUR_CLIENT_SECRET
&redirect_uri=YOUR_REDIRECT_URI
&grant_type=authorization_code
```

### Access token refresh:
```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

refresh_token=STORED_REFRESH_TOKEN
&client_id=YOUR_CLIENT_ID
&client_secret=YOUR_CLIENT_SECRET
&grant_type=refresh_token
```
Note: `redirect_uri` is NOT needed for refresh requests.

---

## 5. Token Exchange Response Fields

```json
{
  "access_token": "ya29.a0AfH6SM...",
  "expires_in": 3599,
  "token_type": "Bearer",
  "scope": "openid https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/userinfo.email",
  "refresh_token": "1//0gABCD...",
  "id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6...",
  "refresh_token_expires_in": 2591999
}
```

| Field | Always Present? | Notes |
|-------|----------------|-------|
| `access_token` | Yes | ~1 hour lifetime |
| `expires_in` | Yes | Seconds until access token expires; typically 3599 |
| `token_type` | Yes | Always `"Bearer"` |
| `scope` | Yes | **May differ from requested scopes** — check this with granular permissions (see below) |
| `refresh_token` | Only on first auth, or when `prompt=consent` is used with `access_type=offline` | Store this persistently |
| `id_token` | Only when `openid` scope was requested | Signed JWT; decode to get `email`, `sub`, `name`, etc. without userinfo call |
| `refresh_token_expires_in` | Only for time-limited access grants | Seconds until refresh token expires |

---

## 6. Refresh Token Behavior (2024-2025)

### When refresh tokens expire or are revoked:
1. **User revokes access** — via Google Account settings
2. **Inactivity** — token unused for 6 months
3. **Password change** — for tokens with Gmail/Workspace scopes, password change revokes tokens
4. **Token limit exceeded** — max 100 refresh tokens per (user, client_id) pair. The 101st token creation invalidates the oldest. This can bite you in testing if you run many auth flows.
5. **App in Testing mode** — if your OAuth consent screen is in "Testing" publishing status, refresh tokens expire after **7 days**. This is a major gotcha for development. Must publish (even just to "In Production" for internal use) to get non-expiring tokens.
6. **Admin policy** — Google Workspace admins can set session length limits that cause token expiry.
7. **Automated protection** — Google security systems may revoke tokens for suspicious activity.

### Token limit details:
- Max **100 live refresh tokens** per Google Account per OAuth client ID
- When the limit is exceeded, the **oldest token is silently invalidated**
- This means if 100 users all re-auth, the first user's token stops working

### No rotation:
Google does NOT rotate refresh tokens on use (unlike e.g. Stripe or some OIDC providers). The same refresh token remains valid until one of the above events occurs.

### `refresh_token_expires_in` field:
New-ish field (appeared ~2023-2024) that appears in responses when there is a time-limited grant (e.g., a Workspace admin has set a session control). If your app stores tokens, you should store and check this field.

---

## 7. Granular Permissions (Major 2023-2024 Change)

**This is the most significant recent change.** Google now shows a checkbox-style consent UI where users can selectively grant individual scopes rather than approving all-or-nothing.

**Impact on your code:**
- The `scope` field in the token response may be SMALLER than the scope you requested
- You CANNOT assume all requested scopes were granted
- You MUST check `response["scope"]` after token exchange
- If a user denied `gmail.readonly`, you need to handle this gracefully (show a UI prompt, disable the feature, etc.)
- You may only re-request a denied scope after the user clearly indicates intent to use that feature

**Example handling:**
```python
granted_scopes = token_response["scope"].split(" ")
gmail_scope = "https://www.googleapis.com/auth/gmail.readonly"
if gmail_scope not in granted_scopes:
    # User denied Gmail access - store this state, do not call Gmail API
    user.gmail_access_granted = False
```

**Note:** Workspace accounts may bypass granular permissions and get the old all-or-nothing flow. Consumer Google accounts always get granular permissions.

---

## 8. Unused OAuth Client Deletion Policy (October 2025)

Google will delete OAuth clients that have been:
- Unused in token exchanges for 6+ months AND
- Have had no configuration edits for 6+ months

Deleted clients can be restored via Google Cloud Console within 30 days.

**Implication:** If you have a staging/dev OAuth client that isn't actively used, it may get deleted. Document your client IDs.

---

## 9. httpx vs google-auth-oauthlib

### google-auth-oauthlib (Google's official library)
**Pros:**
- Google-maintained, handles all protocol details correctly
- `Flow` class manages the authorization URL building and code exchange
- Integrates with `google-api-python-client` for calling Google APIs
- Handles token refresh automatically via `google.oauth2.credentials.Credentials`

**Cons:**
- Synchronous only (no async support)
- Limited credential storage — you must implement your own token persistence
- More opaque; harder to debug OAuth flow issues
- Additional dependency (`google-auth`, `google-auth-oauthlib`, `google-auth-httplib2`)

**Install:**
```
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### httpx (raw HTTP)
**Pros:**
- Async-native, perfect for FastAPI/async Python
- Transparent — you see exactly what's being sent and received
- No hidden magic; easy to debug
- Only one dependency
- Straightforward to implement for a well-documented protocol like Google OAuth

**Cons:**
- You implement the OAuth logic yourself (but Google's OAuth is very well-documented)
- You handle token refresh yourself (but this is simple: POST to the token endpoint)
- No automatic integration with Google API client

### Verdict for this project (FastAPI + async backend):
**httpx is the better choice** for a custom web server implementation. Google OAuth 2.0 is a standard, well-documented protocol. The endpoints, parameters, and response formats are stable and well-known. Using raw httpx gives you:
- Async support (essential for FastAPI)
- Full visibility into the OAuth flow
- Simpler dependency tree
- Easier debugging

`google-auth-oauthlib` makes more sense when you're heavily using the Google API Python client library ecosystem and want automatic token refresh injected into API calls.

**Alternative:** `authlib` provides a higher-level OAuth client that works with `httpx` and is well-maintained. Could be worth adding if you want more OAuth scaffolding without losing async.

---

## 10. Deprecations to Know About

### OOB (Out-of-Band) redirect URI — REMOVED
`urn:ietf:wg:oauth:2.0:oob` as a `redirect_uri` value is fully deprecated and no longer works. Affects desktop/CLI apps that used to use this. Web server apps are unaffected.

### `oauth2client` Python library — DEPRECATED
The old `oauth2client` Python library is deprecated. Use `google-auth` + `google-auth-oauthlib` instead.

### `tokeninfo` endpoint — still available but throttled
`https://oauth2.googleapis.com/tokeninfo?access_token=...` still works for debugging but is throttled. Do not use in production for token validation. Use the userinfo endpoint or local JWT verification instead.

### Implicit flow (JavaScript) — discouraged
The implicit grant type (where tokens are returned directly in the redirect URL fragment) is heavily discouraged for security reasons. Not relevant for web server apps.

---

## Summary: Minimal Working Implementation

### Step 1: Build authorization URL
```python
import urllib.parse, secrets

params = {
    "client_id": GOOGLE_CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
    "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly",
    "access_type": "offline",
    "prompt": "consent",
    "state": secrets.token_urlsafe(32),
}
auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
```

### Step 2: Exchange code for tokens
```python
import httpx

async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        )
        response.raise_for_status()
        return response.json()
        # Returns: access_token, refresh_token, id_token, expires_in, scope, token_type
```

### Step 3: Get user email
```python
async def get_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        return response.json()
        # Returns: sub, email, email_verified, name, picture
```

### Step 4: Refresh access token
```python
async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "refresh_token": refresh_token,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            }
        )
        response.raise_for_status()
        return response.json()
        # Returns: access_token, expires_in, token_type, scope
        # Note: does NOT return a new refresh_token
```

### Step 5: Revoke token
```python
async def revoke_token(token: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/revoke",
            data={"token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        # 200 = success, 400 = token already revoked or invalid
```

---

## Gotchas Summary

1. `access_type=offline` AND `prompt=consent` are BOTH needed to reliably get a refresh token every time
2. `refresh_token` is absent from the response if user already authorized and you didn't use `prompt=consent`
3. Apps in "Testing" publishing status get refresh tokens that expire after 7 days
4. Max 100 refresh tokens per (user, client) — oldest is silently revoked when limit exceeded
5. Scopes in the response may be a subset of what you requested (granular permissions) — always check
6. Refresh tokens can be revoked by password changes, admin policy, or inactivity (6 months)
7. The OOB redirect URI is gone (doesn't affect web server apps)
8. `oauth2client` Python library is deprecated — use `google-auth` ecosystem or raw httpx
9. The `refresh_token_expires_in` field appears for time-limited grants — store it if present

---

## Sources

- [OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
- [OAuth 2.0 API Scopes](https://developers.google.com/identity/protocols/oauth2/scopes)
- [OAuth 2.0 Policies](https://developers.google.com/identity/protocols/oauth2/policies)
- [OAuth 2.0 Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)
- [Granular Permissions](https://developers.google.com/identity/protocols/oauth2/resources/granular-permissions)
- [Token Types - Google Cloud](https://cloud.google.com/docs/authentication/token-types)
- [google-auth-oauthlib reference](https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.html)
- [Increased Account Security via OAuth 2.0 Token Revocation](https://cloud.google.com/blog/products/application-development/increased-account-security-via-oauth-2-0-token-revocation)
