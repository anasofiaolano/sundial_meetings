const API = 'http://localhost:3004';

export function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function formatDateShort(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export async function fetchClients() {
  const res = await fetch(`${API}/api/clients`);
  if (!res.ok) throw new Error(`Failed to fetch clients: ${res.statusText}`);
  return res.json();
}

export async function fetchCalls(clientId) {
  const res = await fetch(`${API}/api/calls/${clientId}`);
  if (!res.ok) throw new Error(`Failed to fetch calls: ${res.statusText}`);
  return res.json();
}

export async function fetchAllCalls() {
  const res = await fetch(`${API}/api/calls`);
  if (!res.ok) throw new Error(`Failed to fetch calls: ${res.statusText}`);
  return res.json();
}

export async function fetchFiles(clientId) {
  const res = await fetch(`${API}/api/files/${clientId}`);
  if (!res.ok) throw new Error(`Failed to fetch files: ${res.statusText}`);
  return res.json();
}

export async function saveFile(clientId, relPath, content) {
  const res = await fetch(`${API}/api/files/${clientId}/${relPath}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`Failed to save file: ${res.statusText}`);
  return res.json();
}

export async function uploadTranscript({ name, content, clientId, callDate, sessionId }) {
  const res = await fetch(`${API}/api/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, content, client_id: clientId, call_date: callDate || null, session_id: sessionId || null }),
  });
  if (!res.ok) throw new Error(`Failed to upload transcript: ${res.statusText}`);
  return res.json();
}

export async function renameCall(jobId, name) {
  const res = await fetch(`${API}/api/calls/${jobId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transcript_name: name }),
  });
  if (!res.ok) throw new Error(`Failed to rename call: ${res.statusText}`);
  return res.json();
}

export function chatStream(messages, contextItems) {
  return fetch(`${API}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, context_items: contextItems }),
  });
}

// ── Chat threads ──────────────────────────────────────────────────────────────

export async function fetchThreads(clientId) {
  const res = await fetch(`${API}/api/chat/threads/${clientId}`);
  if (!res.ok) throw new Error(`Failed to fetch threads: ${res.statusText}`);
  return res.json();
}

export async function createThread(clientId, title = 'New conversation') {
  const res = await fetch(`${API}/api/chat/threads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientId, title }),
  });
  if (!res.ok) throw new Error(`Failed to create thread: ${res.statusText}`);
  return res.json();
}

export async function updateThreadTitle(threadId, title) {
  const res = await fetch(`${API}/api/chat/threads/${threadId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(`Failed to update thread: ${res.statusText}`);
  return res.json();
}

export async function deleteThread(threadId) {
  const res = await fetch(`${API}/api/chat/threads/${threadId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete thread: ${res.statusText}`);
  return res.json();
}

export async function fetchThreadMessages(threadId) {
  const res = await fetch(`${API}/api/chat/threads/${threadId}/messages`);
  if (!res.ok) throw new Error(`Failed to fetch messages: ${res.statusText}`);
  return res.json();
}

export async function saveThreadMessages(threadId, messages) {
  const res = await fetch(`${API}/api/chat/threads/${threadId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
  });
  if (!res.ok) throw new Error(`Failed to save messages: ${res.statusText}`);
  return res.json();
}

// ── Call sessions ─────────────────────────────────────────────────────────────

export async function createSession(clientId) {
  const res = await fetch(`${API}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientId }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.statusText}`);
  return res.json();
}

export async function getSession(sessionId) {
  const res = await fetch(`${API}/api/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to get session: ${res.statusText}`);
  return res.json();
}

export async function endSession(sessionId, jobId = null) {
  const res = await fetch(`${API}/api/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId }),
  });
  if (!res.ok) throw new Error(`Failed to end session: ${res.statusText}`);
  return res.json();
}

export async function addNote(sessionId, { text = '', type = 'note', isBookmark = false, position = 0 }) {
  const res = await fetch(`${API}/api/sessions/${sessionId}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, type, is_bookmark: isBookmark, position }),
  });
  if (!res.ok) throw new Error(`Failed to add note: ${res.statusText}`);
  return res.json();
}

export async function updateNote(sessionId, noteId, updates) {
  const body = {};
  if (updates.text        !== undefined) body.text        = updates.text;
  if (updates.type        !== undefined) body.type        = updates.type;
  if (updates.isBookmark  !== undefined) body.is_bookmark = updates.isBookmark;
  const res = await fetch(`${API}/api/sessions/${sessionId}/notes/${noteId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed to update note: ${res.statusText}`);
  return res.json();
}

export async function deleteNote(sessionId, noteId) {
  const res = await fetch(`${API}/api/sessions/${sessionId}/notes/${noteId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete note: ${res.statusText}`);
  return res.json();
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${API}/api/sessions/${sessionId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete session: ${res.statusText}`);
  return res.json();
}

export async function fetchClientSessions(clientId) {
  const res = await fetch(`${API}/api/clients/${clientId}/sessions`);
  if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.statusText}`);
  return res.json();
}

export async function linkSessionToJob(sessionId, jobId) {
  const res = await fetch(`${API}/api/sessions/${sessionId}/link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId }),
  });
  if (!res.ok) throw new Error(`Failed to link session: ${res.statusText}`);
  return res.json();
}

export async function fetchPreCallBrief(clientId) {
  const res = await fetch(`${API}/api/clients/${clientId}/pre-call-brief`);
  if (!res.ok) throw new Error(`Failed to fetch pre-call brief: ${res.statusText}`);
  return res.json();
}

// ── Email threads ──────────────────────────────────────────────────────────────

export async function fetchEmailThreads(clientId, { refresh = false } = {}) {
  const url = `${API}/api/clients/${clientId}/emails${refresh ? '?refresh=true' : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch email threads: ${res.statusText}`);
  return res.json();
}
