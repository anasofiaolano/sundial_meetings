# services/gmail.py
#
# All Gmail API interaction lives here. The rest of the app calls two functions:
#   - sync_client_emails(client_id)  — incremental sync, full resync on 404
#   - get_cached_threads(client_id)  — read from DB, no network call
#
# Sync strategy: Gmail History API cursor pattern.
#   First sync  → full thread fetch, store historyId cursor
#   Subsequent  → fetch only what changed since cursor, update cursor
#   On 404      → cursor expired (~1 week TTL), fall back to full resync
#
# This file is intentionally queue-agnostic. sync_client_emails() is a plain
# async function — APScheduler calls it today, a job queue can call it tomorrow.

import base64
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import httpx

import google_oauth
from time_utils import now_pt

logger = logging.getLogger(__name__)

DB_PATH   = Path(__file__).parent.parent / "backend" / "jobs.db"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

# How often we force a full resync even when the cursor is healthy.
# Gmail's messagesAdded entries occasionally miss messages (known API bug),
# so a periodic full resync acts as a safety net.
FULL_RESYNC_INTERVAL_HOURS = 24


# ── DB connection ──────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── Token management ───────────────────────────────────────────────────────────

async def _get_valid_token(account: dict) -> str | None:
    """
    Return a valid access token, refreshing silently if expired.
    On refresh failure, marks the account as 'broken' so the Settings page
    can surface a "reconnect needed" prompt to the user.
    Returns None if the token cannot be obtained — caller should skip the sync.
    """
    if not google_oauth.is_token_expired(account["token_expiry"]):
        return account["access_token"]

    logger.info("[gmail] access token expired for account=%s, refreshing", account["id"])
    try:
        refreshed  = await google_oauth.refresh_access_token(account["refresh_token"])
        new_token  = refreshed["access_token"]
        new_expiry = google_oauth.token_expiry_from_response(refreshed)
        conn = _connect()
        conn.execute(
            "UPDATE email_accounts SET access_token = ?, token_expiry = ?, updated_at = ? WHERE id = ?",
            (new_token, new_expiry, now_pt(), account["id"]),
        )
        conn.close()
        logger.info("[gmail] token refreshed for account=%s", account["id"])
        return new_token
    except Exception:
        # Log the full traceback so we can diagnose whether this is a network
        # issue, a revoked token, or something else.
        logger.error(
            "[gmail] token refresh failed for account=%s — marking broken",
            account["id"],
            exc_info=True,
        )
        conn = _connect()
        conn.execute(
            "UPDATE email_accounts SET status = 'broken', updated_at = ? WHERE id = ?",
            (now_pt(), account["id"]),
        )
        conn.close()
        return None


# ── Gmail query builder ────────────────────────────────────────────────────────

def _build_query(domains: list[str], addresses: list[str]) -> str:
    """
    Build a Gmail search query from filter lists.
    Domains match any from/to on that domain; addresses match a specific address.
    Multiple parts are OR'd together.
    """
    parts = []
    for domain in domains:
        parts.append(f"(from:{domain} OR to:{domain})")
    for addr in addresses:
        parts.append(f"(from:{addr} OR to:{addr})")
    return " OR ".join(parts) if parts else ""


def _thread_matches_filters(thread_data: dict, domains: list[str], addresses: list[str]) -> bool:
    """
    Check whether a thread is relevant to this client's filters.

    This is needed because the History API returns ALL mailbox changes, not just
    those matching a search query. Without this check, incremental sync would pull
    in every new email regardless of domain or contact.

    A thread matches if any participant's email address:
      - ends with one of the client's domains, OR
      - exactly matches one of the client's specific addresses
    """
    all_emails: set[str] = set()
    for msg in thread_data.get("messages", []):
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        for field in ["from", "to", "cc"]:
            for part in headers.get(field, "").split(","):
                part = part.strip()
                # Extract bare email from "Display Name <email@domain.com>" format
                if "<" in part and ">" in part:
                    part = part[part.index("<") + 1 : part.index(">")].strip()
                if part:
                    all_emails.add(part.lower())

    for email in all_emails:
        for domain in domains:
            if email.endswith(f"@{domain.lower()}") or email.endswith(f".{domain.lower()}"):
                return True
        for addr in addresses:
            if email == addr.lower():
                return True

    return False


# ── Message parsing ────────────────────────────────────────────────────────────

def _decode_body(part: dict) -> str:
    """Decode a base64url-encoded email body part."""
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        logger.warning("[gmail] failed to decode body part", exc_info=True)
        return ""


def _extract_message(msg: dict) -> dict:
    """Extract key fields from a raw Gmail message object."""
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

    # Prefer plain text body; fall back to HTML
    def find_body(part) -> str:
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            return _decode_body(part)
        if mime == "text/html":
            return _decode_body(part)
        for sub in part.get("parts", []):
            result = find_body(sub)
            if result:
                return result
        return ""

    body = find_body(msg.get("payload", {}))

    return {
        "id":      msg.get("id"),
        "date":    headers.get("date", ""),
        "from":    headers.get("from", ""),
        "to":      headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "snippet": msg.get("snippet", ""),
        "body":    body,
    }


# ── Thread upsert ──────────────────────────────────────────────────────────────

def _upsert_thread(conn: sqlite3.Connection, client_id: str, thread_data: dict, now: str) -> dict | None:
    """
    Parse a full Gmail thread object and upsert it into email_threads.
    Returns the thread dict for the API response, or None if the thread has no messages.
    """
    messages = thread_data.get("messages", [])
    if not messages:
        return None

    gmail_thread_id = thread_data["id"]
    extracted       = [_extract_message(m) for m in messages]
    latest          = extracted[-1]

    # Collect unique participant emails across all messages in the thread
    all_participants = list({
        e.strip()
        for msg in extracted
        for field in [msg["from"], msg["to"]]
        for e in field.split(",")
        if e.strip()
    })

    conn.execute(
        """INSERT INTO email_threads
           (id, client_id, gmail_thread_id, subject, snippet, from_email,
            participants, thread_date, message_count, messages_json, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(client_id, gmail_thread_id) DO UPDATE SET
             subject       = excluded.subject,
             snippet       = excluded.snippet,
             from_email    = excluded.from_email,
             participants  = excluded.participants,
             thread_date   = excluded.thread_date,
             message_count = excluded.message_count,
             messages_json = excluded.messages_json,
             fetched_at    = excluded.fetched_at""",
        (
            f"email-{gmail_thread_id}",
            client_id,
            gmail_thread_id,
            latest["subject"],
            latest["snippet"],
            latest["from"],
            json.dumps(all_participants),
            latest["date"],
            len(messages),
            json.dumps(extracted),
            now,
        ),
    )

    return {
        "id":              f"email-{gmail_thread_id}",
        "type":            "email",
        "client_id":       client_id,
        "gmail_thread_id": gmail_thread_id,
        "subject":         latest["subject"],
        "snippet":         latest["snippet"],
        "from_email":      latest["from"],
        "participants":    all_participants,
        "thread_date":     latest["date"],
        "message_count":   len(messages),
        "messages":        extracted,
        "fetched_at":      now,
    }


# ── Sync state helpers ─────────────────────────────────────────────────────────

def _get_sync_state(conn: sqlite3.Connection, client_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM gmail_sync_state WHERE client_id = ?", (client_id,)
    ).fetchone()
    return dict(row) if row else None


def _save_sync_state(conn: sqlite3.Connection, client_id: str, account_id: str,
                     history_id: str, full_sync: bool = False) -> None:
    now = now_pt()
    conn.execute(
        """INSERT INTO gmail_sync_state (client_id, account_id, history_id, last_full_sync, last_synced_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(client_id) DO UPDATE SET
             account_id     = excluded.account_id,
             history_id     = excluded.history_id,
             last_full_sync = CASE WHEN ? THEN excluded.last_full_sync ELSE last_full_sync END,
             last_synced_at = excluded.last_synced_at""",
        (client_id, account_id, history_id, now if full_sync else None, now,
         full_sync),
    )


def _needs_full_resync(sync_state: dict | None) -> bool:
    """
    Returns True if we should do a full resync rather than an incremental one.
    We force a full resync daily as a safety net against Gmail's known bug where
    messagesAdded history entries occasionally omit new messages.
    """
    if sync_state is None:
        return True  # No cursor stored — first sync
    last_full = sync_state.get("last_full_sync")
    if not last_full:
        return True
    try:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(last_full)
        return delta.total_seconds() > FULL_RESYNC_INTERVAL_HOURS * 3600
    except Exception:
        return True


# ── Full sync ──────────────────────────────────────────────────────────────────

async def _full_sync(
    client_http: httpx.AsyncClient,
    headers: dict,
    conn: sqlite3.Connection,
    client_id: str,
    account_id: str,
    query: str,
    now: str,
) -> list[dict]:
    """
    Full sync: fetch all matching threads, upsert them, capture a fresh historyId cursor.

    Called on first sync, on cursor expiry (Gmail 404), and daily as a safety net.
    Returns the list of thread dicts fetched.
    """
    logger.info("[gmail] starting full sync for client=%s", client_id)

    # Step 1: Get the current historyId from the most recent message.
    # historyId is NOT in the thread list response — must come from messages API.
    r = await client_http.get(f"{GMAIL_API}/messages", headers=headers, params={"maxResults": 1})
    r.raise_for_status()
    messages_data = r.json().get("messages", [])

    history_id = None
    if messages_data:
        # Fetch the full message to get its historyId
        msg_r = await client_http.get(
            f"{GMAIL_API}/messages/{messages_data[0]['id']}",
            headers=headers,
            params={"format": "minimal"},
        )
        msg_r.raise_for_status()
        history_id = msg_r.json().get("historyId")

    # Step 2: Fetch all threads matching this client's filters (max 50)
    r = await client_http.get(
        f"{GMAIL_API}/threads",
        headers=headers,
        params={"q": query, "maxResults": 50},
    )
    r.raise_for_status()
    thread_list = r.json().get("threads", [])

    threads_out = []
    for t in thread_list:
        tr = await client_http.get(
            f"{GMAIL_API}/threads/{t['id']}",
            headers=headers,
            params={"format": "full"},
        )
        if tr.status_code != 200:
            logger.warning("[gmail] failed to fetch thread=%s status=%s", t["id"], tr.status_code)
            continue
        result = _upsert_thread(conn, client_id, tr.json(), now)
        if result:
            threads_out.append(result)

    # Step 3: Save cursor. If we got a historyId, use it; otherwise leave existing cursor.
    if history_id:
        _save_sync_state(conn, client_id, account_id, history_id, full_sync=True)
        logger.info("[gmail] full sync done for client=%s — %d threads, cursor=%s",
                    client_id, len(threads_out), history_id)
    else:
        logger.warning("[gmail] full sync for client=%s completed but no historyId obtained", client_id)

    return threads_out


# ── Incremental sync ───────────────────────────────────────────────────────────

async def _incremental_sync(
    client_http: httpx.AsyncClient,
    headers: dict,
    conn: sqlite3.Connection,
    client_id: str,
    account_id: str,
    history_id: str,
    domains: list[str],
    addresses: list[str],
    now: str,
) -> list[dict]:
    """
    Incremental sync using the Gmail History API cursor.
    Only fetches threads that changed since the last historyId cursor.

    IMPORTANT: The History API returns ALL mailbox changes, not just those matching
    the client's search filters. We apply _thread_matches_filters() after fetching
    each thread to discard unrelated emails before upserting.

    Returns the list of updated thread dicts.
    Raises httpx.HTTPStatusError with status 404 if the cursor has expired —
    the caller should catch this and fall back to _full_sync().
    """
    logger.info("[gmail] incremental sync for client=%s from cursor=%s", client_id, history_id)

    # Fetch history since our cursor. We only care about messageAdded — for this
    # use case we don't need to handle deletes (we just leave stale threads cached).
    r = await client_http.get(
        f"{GMAIL_API}/history",
        headers=headers,
        params={
            "startHistoryId": history_id,
            "historyTypes":   ["messageAdded"],
            "maxResults":     500,
        },
    )

    # 404 = cursor expired. Caller catches this and does a full resync.
    r.raise_for_status()

    data = r.json()
    new_history_id = data.get("historyId", history_id)

    # Collect unique threadIds that have new messages
    changed_thread_ids: set[str] = set()
    for record in data.get("history", []):
        for msg_added in record.get("messagesAdded", []):
            tid = msg_added.get("message", {}).get("threadId")
            if tid:
                changed_thread_ids.add(tid)

    threads_out = []
    skipped = 0
    for tid in changed_thread_ids:
        tr = await client_http.get(
            f"{GMAIL_API}/threads/{tid}",
            headers=headers,
            params={"format": "full"},
        )
        if tr.status_code != 200:
            logger.warning("[gmail] failed to fetch thread=%s status=%s", tid, tr.status_code)
            continue

        thread_data = tr.json()

        # Filter check: History API is mailbox-wide, not query-scoped.
        # Skip threads that don't involve this client's domains or contacts.
        if not _thread_matches_filters(thread_data, domains, addresses):
            skipped += 1
            continue

        result = _upsert_thread(conn, client_id, thread_data, now)
        if result:
            threads_out.append(result)

    _save_sync_state(conn, client_id, account_id, new_history_id, full_sync=False)
    logger.info(
        "[gmail] incremental sync done for client=%s — %d threads updated, %d skipped, cursor=%s",
        client_id, len(threads_out), skipped, new_history_id,
    )

    return threads_out


# ── Public sync entry point ────────────────────────────────────────────────────

async def sync_client_emails(client_id: str) -> list[dict]:
    """
    Sync email threads for a client. Called by both the API endpoint (on page load)
    and the APScheduler background job (every 15 min for all active clients).

    Strategy:
      - If no cursor exists, or daily safety resync is due → full sync
      - Otherwise → incremental sync via History API
      - On 404 (cursor expired) → fall back to full sync

    Always returns the full current cached thread list from the DB.
    """
    conn = _connect()

    # Verify client exists
    client = conn.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        conn.close()
        logger.warning("[gmail] sync requested for unknown client=%s", client_id)
        return []

    # Load this client's email filters
    filters   = conn.execute(
        "SELECT type, value FROM client_email_filters WHERE client_id = ?", (client_id,)
    ).fetchall()
    domains   = [r["value"] for r in filters if r["type"] == "domain"]
    addresses = [r["value"] for r in filters if r["type"] == "address"]

    if not domains and not addresses:
        # No filters configured — nothing to fetch
        conn.close()
        return []

    # Get the active connected Google account
    account = conn.execute(
        "SELECT * FROM email_accounts WHERE provider = 'google' AND status = 'active' LIMIT 1"
    ).fetchone()
    if not account:
        conn.close()
        logger.info("[gmail] no active Google account for client=%s — skipping sync", client_id)
        return []

    account = dict(account)
    sync_state = _get_sync_state(conn, client_id)
    conn.close()

    # Refresh token if needed — returns None if account is broken
    token = await _get_valid_token(account)
    if not token:
        return get_cached_threads(client_id)

    query   = _build_query(domains, addresses)
    headers = {"Authorization": f"Bearer {token}"}
    now     = now_pt()

    try:
        async with httpx.AsyncClient(timeout=20) as client_http:
            conn = _connect()

            if _needs_full_resync(sync_state):
                # First sync, daily safety resync, or cursor never set
                await _full_sync(client_http, headers, conn, client_id, account["id"], query, now)
            else:
                try:
                    # Incremental sync — only fetch what changed
                    await _incremental_sync(
                        client_http, headers, conn, client_id,
                        account["id"], sync_state["history_id"],
                        domains, addresses, now,
                    )
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        # Cursor expired — Gmail only keeps cursors for ~1 week.
                        # Fall back to full resync to get a fresh cursor.
                        logger.warning(
                            "[gmail] cursor expired for client=%s (404) — falling back to full sync",
                            client_id,
                        )
                        await _full_sync(
                            client_http, headers, conn, client_id, account["id"], query, now
                        )
                    else:
                        raise  # Re-raise unexpected HTTP errors

            conn.close()

    except Exception:
        logger.error("[gmail] sync failed for client=%s", client_id, exc_info=True)

    # Always return the full cached set from DB regardless of what the sync fetched
    return get_cached_threads(client_id)


# ── Cache read ─────────────────────────────────────────────────────────────────

def get_cached_threads(client_id: str) -> list[dict]:
    """Return cached email threads from the DB without hitting Gmail."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM email_threads WHERE client_id = ? ORDER BY fetched_at DESC",
        (client_id,),
    ).fetchall()
    conn.close()

    out = []
    for r in rows:
        d = dict(r)
        d["type"]         = "email"
        d["messages"]     = json.loads(d.get("messages_json") or "[]")
        d["participants"] = json.loads(d.get("participants") or "[]")
        out.append(d)
    return out
