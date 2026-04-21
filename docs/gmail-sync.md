# Research: Gmail History API — Incremental Sync

## Purpose
How to avoid re-fetching all 50 threads on every sync. Instead, only fetch what changed since our last sync using Gmail's History API.

---

## The Endpoint

```
GET /gmail/v1/users/me/history
```

**Parameters:**
- `startHistoryId` (required) — cursor from last sync
- `historyTypes[]` (optional) — filter to specific change types: `messageAdded`, `messageDeleted`, `labelAdded`, `labelRemoved`
- `maxResults` (default 100, max 500)
- `pageToken` — for pagination

**Response:**
```json
{
  "history": [
    {
      "id": "string",
      "messagesAdded": [{ "message": { "id": "...", "threadId": "..." } }],
      "messagesDeleted": [{ "message": { "id": "...", "threadId": "..." } }]
    }
  ],
  "nextPageToken": "string",
  "historyId": "string"   ← store this for next time
}
```

History responses only contain `id` and `threadId` per message — you must fetch the full thread separately if you need headers/body.

---

## Where historyId Comes From (Initial Sync)

**Not** from the threads list response. Must come from the **messages API**:

```
GET /gmail/v1/users/me/messages?maxResults=1
→ messages[0].historyId  ← store this
```

Do this once at initial setup, then use it as `startHistoryId` on all future incremental syncs.

---

## Error: Expired historyId

**HTTP 404** — historyId is too old (valid for ~1 week, sometimes only hours).

**Recovery:** Full resync. Call `messages.list()` again, get new historyId, resume.

---

## Implementation Pattern

```
FIRST SYNC:
1. GET /messages?maxResults=1 → store historyId
2. Full thread fetch (existing logic)
3. Save historyId to DB

SUBSEQUENT SYNCS:
1. GET /history?startHistoryId={saved}&historyTypes[]=messageAdded,messageDeleted
2. Collect unique threadIds from messagesAdded + messagesDeleted
3. For each changed threadId: GET /threads/{id}?format=full
4. Upsert into email_threads
5. Store new historyId from response

ON 404:
1. Full resync (back to step 1 of FIRST SYNC)
```

---

## DB Change Needed

Add `gmail_history_id` column to `email_accounts` (or a dedicated `gmail_sync_state` table per client, since one Google account may serve multiple clients).

Per-client state makes more sense because each client has a different search query — the historyId is per-mailbox but the filtered thread set is per-client.

Proposed: `gmail_sync_state` table:
```sql
CREATE TABLE gmail_sync_state (
    client_id      TEXT PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
    account_id     TEXT NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    history_id     TEXT NOT NULL,
    last_synced_at TEXT NOT NULL
);
```

---

## Key Gotchas

1. **messagesAdded is not exhaustive** — real-world bugs mean some new messages may not appear. Fallback polling (full resync) occasionally is still wise.
2. **History IDs are non-contiguous** — don't iterate them sequentially, just use the cursor pattern.
3. **Push notifications (Pub/Sub watch)** — Gmail also supports push via Google Cloud Pub/Sub (notify on change instead of polling). Requires GCP setup. Worth revisiting for real-time sync in v2. Not worth it now.
4. **Watch expires every 7 days** — if we ever use push notifications, must renew weekly.

---

## Sources

- [Gmail History API reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)
- [Gmail sync guide](https://developers.google.com/workspace/gmail/api/guides/sync)
- [Hiver engineering: Gmail push notification bug workaround](https://medium.com/hiver-engineering/gmail-apis-push-notifications-bug-and-how-we-worked-around-it-at-hiver-a0a114df47b4)
- [Mixmax: Adventures in Gmail PubSub API](https://www.mixmax.com/engineering/adventures-in-the-gmail-pubsub-api)

---

## Synthesis / Implications

- The History API is the correct long-term approach — bandwidth-efficient, scales well
- We need a `gmail_sync_state` table (per client, not per account) to store the cursor
- Full resync on 404 is unavoidable and should be handled gracefully
- Push notifications are a future optimization — polling every 15 min via APScheduler is the right starting point
- Implementation is straightforward: get historyId on first sync, use it on all subsequent ones, handle 404 with full resync
