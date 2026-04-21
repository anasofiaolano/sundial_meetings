# Co-pilot UI/UX Decisions

Small notes on non-obvious frontend choices.

---

## WebSocket disconnect handling

**Behavior:** If the WebSocket drops unexpectedly (network blip, server
restart), the mic button resets to inactive and a toast appears:
"Mic disconnected — click to reconnect."

**Why the toast matters:** Without it, the button just goes gray. The rep
can't tell if they accidentally clicked stop or the connection died. The toast
makes it clear they need to re-click.

**How it works:** `ws.onclose` owns all cleanup. If `isListening` is true when
`onclose` fires, it was an unexpected drop — reset UI and show toast. If
`isListening` is already false (rep clicked stop first), `onclose` fires but
the guard is false — silent, no toast.

`ws.onerror` only logs; it doesn't call `stopMic()` directly because `onclose`
always follows an error and handles it.

---

## Concurrent in-flight analysis

Multiple `/api/copilot/analyze` requests can be in flight simultaneously —
one fires on every Vosk "final" utterance without waiting for the previous
to return. The status area shows "Analyzing... (N)" when more than one is
pending.

Deduplication is handled client-side: a `seenQuestions` Set stores normalized
question strings (lowercased, alphanumeric only). Even if two concurrent
requests detect the same question, only the first one renders a card.

---

## No debounce

Analysis fires immediately on each Vosk "final" event rather than waiting for
a pause. On a live sales call there's no reliable silence — people talk
continuously. A debounce either fires too late or not at all.

---

## Light / dark mode

Theme is stored in `localStorage` under `copilot-theme` and applied on load.
Toggle button in the top-right corner switches between modes.

Answer text uses a CSS class `.qa-answer` (not inline color) so that
`[data-theme="light"] .qa-answer` can override it. Dynamically created cards
inherit the class and respond correctly to theme switches.
