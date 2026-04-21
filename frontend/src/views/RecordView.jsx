import { useState, useEffect, useRef, useCallback } from 'react';
import { useToast } from '../components/Toast';
import { useLocation } from 'react-router-dom';
import { RefreshCw, Phone, Archive, Trash2 } from 'lucide-react';

// ── Drag resize hook (right-side panel: drag left edge, drag left = wider) ───
function useDragResize(defaultWidth, { min = 240, max = 600 } = {}) {
  const [width, setWidth] = useState(defaultWidth);
  const dragging = useRef(false);
  const startX   = useRef(0);
  const startW   = useRef(0);
  const onMouseDown = useCallback((e) => {
    dragging.current = true;
    startX.current   = e.clientX;
    startW.current   = width;
    e.preventDefault();
  }, [width]);
  useEffect(() => {
    function onMove(e) {
      if (!dragging.current) return;
      const delta = startX.current - e.clientX;
      setWidth(Math.max(min, Math.min(max, startW.current + delta)));
    }
    function onUp() { dragging.current = false; }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [min, max]);
  return { width, onMouseDown };
}
import Breadcrumb from '../components/Breadcrumb';
import RecordSidebar from './record/RecordSidebar';
import RecordToolbar from './record/RecordToolbar';
import NotesEditor from './record/NotesEditor';
import BriefingNotes from './record/BriefingNotes';
import EmailDraftCard from './record/EmailDraftCard';
import TranscriptPanel from './record/TranscriptPanel';
import ChatRail from './record/ChatRail';
import ChatPanel from './record/ChatPanel';
import CallPanel from './record/CallPanel';
import SessionView from './record/SessionView';
import UploadModal from '../components/UploadModal';
import { fetchFiles, fetchEmailThreads, fetchClientSessions, getSession, deleteSession } from '../api/index';

// ── Archive / delete persistence ──────────────────────────────────────────────
const ARCHIVE_KEY = 'sundial_archived_calls';
const DELETED_KEY = 'sundial_deleted_items'; // [{id, deletedAt}]
const SOFT_DELETE_DAYS = 30;

function loadSet(key) { try { return new Set(JSON.parse(localStorage.getItem(key) || '[]')); } catch { return new Set(); } }
function saveSet(key, set) { localStorage.setItem(key, JSON.stringify([...set])); }

// Soft-delete helpers (store {id, deletedAt} so we can purge after 30 days)
function loadDeletedSet() {
  try {
    const raw = JSON.parse(localStorage.getItem(DELETED_KEY) || '[]');
    // Handle both old (string[]) and new ({id,deletedAt}[]) formats
    const items = Array.isArray(raw) ? raw : [];
    return new Set(items.map(x => (typeof x === 'string' ? x : x.id)));
  } catch { return new Set(); }
}
function softDeleteItem(id) {
  try {
    const raw = JSON.parse(localStorage.getItem(DELETED_KEY) || '[]');
    const items = Array.isArray(raw) ? raw.map(x => typeof x === 'string' ? { id: x, deletedAt: new Date().toISOString() } : x) : [];
    const updated = [...items.filter(x => x.id !== id), { id, deletedAt: new Date().toISOString() }];
    localStorage.setItem(DELETED_KEY, JSON.stringify(updated));
  } catch {}
}
function undoSoftDelete(id) {
  try {
    const raw = JSON.parse(localStorage.getItem(DELETED_KEY) || '[]');
    const items = Array.isArray(raw) ? raw : [];
    localStorage.setItem(DELETED_KEY, JSON.stringify(items.filter(x => (typeof x === 'string' ? x : x.id) !== id)));
  } catch {}
}
function purgeExpiredDeletes(onExpired) {
  try {
    const raw = JSON.parse(localStorage.getItem(DELETED_KEY) || '[]');
    const items = Array.isArray(raw) ? raw.map(x => typeof x === 'string' ? { id: x, deletedAt: new Date(0).toISOString() } : x) : [];
    const cutoff = Date.now() - SOFT_DELETE_DAYS * 24 * 60 * 60 * 1000;
    const expired = items.filter(x => new Date(x.deletedAt).getTime() < cutoff);
    const remaining = items.filter(x => new Date(x.deletedAt).getTime() >= cutoff);
    localStorage.setItem(DELETED_KEY, JSON.stringify(remaining));
    expired.forEach(x => onExpired(x.id));
  } catch {}
}
import { formatDate, formatDateShort } from '../api/index';

// ── Processing state ──────────────────────────────────────────────────────────

function ProcessingState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-5">
      <div className="relative w-11 h-11">
        <div className="absolute inset-0 rounded-full border-2 border-[#f0f0f0]" />
        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-[#f59e0b] animate-spin" />
      </div>
      <div className="text-center">
        <div className="text-[15px] font-semibold text-[#333] mb-1.5">Processing transcript</div>
        <div className="text-[13px] text-[#aaa] leading-relaxed">
          The AI is reading your notes.<br />This usually takes 30–60 seconds.
        </div>
      </div>
      <button
        onClick={() => window.location.reload()}
        className="flex items-center gap-2 text-[12px] font-medium text-[#888] hover:text-[#333] border border-[#e8e8e8] hover:border-[#bbb] rounded-lg px-3.5 py-2 bg-white hover:bg-[#fafafa] transition-all cursor-pointer font-inherit"
      >
        <RefreshCw size={12} />
        Check for updates
      </button>
    </div>
  );
}

// ── Sticky scroll header ──────────────────────────────────────────────────────

function StickyCallHeader({ call, briefing }) {
  const rawName = call?.transcript_name || call?.id || 'Untitled';
  const name = rawName.replace(/^\d{6,8}[_\s]+/, '').replace(/_/g, ' ').trim() || rawName;
  const date = formatDateShort(call?.created_at);
  const attendees = briefing?.attendees;

  return (
    <div
      className="sticky top-0 -mx-6 px-6 py-2 z-10 flex items-center gap-2.5"
      style={{
        background: 'rgba(255,255,255,0.92)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        borderBottom: '1px solid rgba(0,0,0,0.06)',
        marginBottom: '20px',
      }}
    >
      <span className="text-[13px] font-semibold text-[#1a1a1a] tracking-[-0.01em] truncate">{name}</span>
      <span className="text-[#e0e0e0] flex-shrink-0">·</span>
      <span className="text-[12px] text-[#aaa] flex-shrink-0">{date}</span>
      {attendees && (
        <>
          <span className="text-[#e0e0e0] flex-shrink-0">·</span>
          <span className="text-[12px] text-[#bbb] truncate">{attendees}</span>
        </>
      )}
    </div>
  );
}

// ── Email thread view ─────────────────────────────────────────────────────────

function EmailMessage({ msg, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const from = msg.from || '';
  const displayFrom = from.replace(/<[^>]+>/, '').trim() || from;

  return (
    <div className="border border-[#f0f0f0] rounded-xl overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left bg-transparent border-none cursor-pointer hover:bg-[#fafafa] transition-colors"
      >
        <div className="flex flex-col min-w-0">
          <span className="text-[13px] font-semibold text-[#1a1a1a] truncate">{displayFrom}</span>
          {!open && (
            <span className="text-[11.5px] text-[#aaa] truncate mt-0.5">{msg.snippet || ''}</span>
          )}
        </div>
        <span className="text-[11px] text-[#bbb] flex-shrink-0 whitespace-nowrap">
          {formatDateShort(msg.date)}
        </span>
      </button>
      {/* Body */}
      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-[#f5f5f5]">
          <pre className="text-[12.5px] text-[#444] leading-[1.65] whitespace-pre-wrap font-inherit m-0">
            {msg.body || msg.snippet || '(No content)'}
          </pre>
        </div>
      )}
    </div>
  );
}

function EmailThreadView({ email, onArchive }) {
  const messages = email.messages || [];
  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Thread header */}
      <div className="flex items-start justify-between px-6 py-4 border-b border-[#f0f0f0] flex-shrink-0">
        <div>
          <div className="text-[17px] font-bold text-[#1a1a1a] tracking-[-0.02em] leading-snug">
            {email.subject || '(No subject)'}
          </div>
          <div className="text-[12px] text-[#888] mt-1">
            {messages.length} message{messages.length !== 1 ? 's' : ''}
            {email.participants?.length > 0 && (
              <span> · {email.participants.slice(0, 3).join(', ')}{email.participants.length > 3 ? ` +${email.participants.length - 3}` : ''}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 mt-0.5">
          {onArchive && (
            <button onClick={onArchive} className="flex items-center gap-1.5 text-[12.5px] font-medium px-3 py-[6px] rounded-lg border border-[#e0e0e0] bg-white text-[#555] hover:border-[#bbb] cursor-pointer transition-colors font-inherit">
              <Archive size={12} />Archive
            </button>
          )}
        </div>
      </div>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="flex flex-col gap-3 max-w-[660px]">
          {messages.map((msg, i) => (
            <EmailMessage key={msg.id || i} msg={msg} defaultOpen={i === messages.length - 1} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── RecordView ────────────────────────────────────────────────────────────────

export default function RecordView({ client, calls: initialCalls, onRenameCall }) {
  const location = useLocation();
  const [calls, setCalls] = useState(initialCalls);
  const [emails, setEmails] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [activeKey, setActiveKey] = useState(location.state?.openCallId ?? 'overview');
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [callPanelOpen, setCallPanelOpen] = useState(false);
  const [confirmStop,   setConfirmStop]   = useState(false);
  const [noteScrolled,  setNoteScrolled]  = useState(false);
  const callEndRef = useRef(null);

  const transcript = useDragResize(340, { min: 240, max: 560 });

  useEffect(() => { setCalls(initialCalls); }, [initialCalls]);
  useEffect(() => {
    if (location.state?.openCallId) setActiveKey(location.state.openCallId);
  }, [location.state?.openCallId]);

  const [archivedIds,        setArchivedIds]        = useState(() => loadSet(ARCHIVE_KEY));
  const [deletedIds,         setDeletedIds]          = useState(() => loadDeletedSet());
  const [confirmDeleteId,    setConfirmDeleteId]     = useState(null);
  const [recordingSessionId, setRecordingSessionId]  = useState(null);
  const addToast = useToast();
  const lastArchivedId = useRef(null);
  const lastDeletedId  = useRef(null);

  useEffect(() => { saveSet(ARCHIVE_KEY, archivedIds); }, [archivedIds]);
  // deletedIds is persisted via softDeleteItem/undoSoftDelete directly (they store timestamps)

  // Purge soft-deleted items older than 30 days on mount
  useEffect(() => {
    purgeExpiredDeletes(id => { deleteSession(id).catch(() => {}); });
  }, []);

  function toggleArchive(id) {
    const isCurrentlyArchived = archivedIds.has(id);
    setArchivedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
    if (!isCurrentlyArchived && activeKey === id) setActiveKey('overview');
  }

  function handleArchive(id) {
    const isCurrentlyArchived = archivedIds.has(id);
    toggleArchive(id);
    if (!isCurrentlyArchived) {
      lastArchivedId.current = id;
      addToast('Archived', 'info', {
        duration: 5000,
        action: { label: 'Undo', onClick: () => { toggleArchive(id); lastArchivedId.current = null; } },
      });
    }
  }

  // Ctrl+Z undoes last archive
  useEffect(() => {
    function onKeyDown(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'z' && lastArchivedId.current) {
        e.preventDefault();
        toggleArchive(lastArchivedId.current);
        lastArchivedId.current = null;
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [archivedIds]);

  function handleDelete(id) {
    // Show confirmation first — actual delete happens in confirmDelete
    setConfirmDeleteId(id);
  }

  function confirmDelete(id) {
    setConfirmDeleteId(null);
    softDeleteItem(id);
    setDeletedIds(prev => new Set([...prev, id]));
    if (activeKey === id) setActiveKey('overview');
    lastDeletedId.current = id;
    addToast('Moved to trash', 'info', {
      duration: 5000,
      action: {
        label: 'Undo',
        onClick: () => {
          undoSoftDelete(id);
          setDeletedIds(prev => { const n = new Set(prev); n.delete(id); return n; });
          lastDeletedId.current = null;
        },
      },
    });
  }

  function refreshSessions() {
    if (!client?.id) return;
    fetchClientSessions(client.id).then(setSessions).catch(() => {});
  }

  useEffect(() => { refreshSessions(); }, [client?.id]);

  // Fetch email threads on mount (refresh=true hits Gmail, then caches)
  useEffect(() => {
    if (!client?.id) return;
    fetchEmailThreads(client.id, { refresh: true })
      .then(setEmails)
      .catch(() => {
        // Fall back to cached threads if Gmail fetch fails
        fetchEmailThreads(client.id).then(setEmails).catch(() => {});
      });
  }, [client?.id]);

  // Reset scroll indicator when switching items
  useEffect(() => { setNoteScrolled(false); }, [activeKey]);

  function handleRenameCall(callId, newName) {
    setCalls(prev => prev.map(c => c.id === callId ? { ...c, transcript_name: newName } : c));
    onRenameCall?.(callId, newName);
  }

  // Overview files
  const [files, setFiles] = useState(null);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState(null);

  const isOverview = activeKey === 'overview';
  const isEmailThread = activeKey.startsWith('email-');
  const isSession = activeKey.startsWith('session-');
  const activeCall = (isOverview || isEmailThread || isSession) ? null : calls.find(c => c.id === activeKey) || null;
  const activeEmail = isEmailThread ? emails.find(e => e.id === activeKey) || null : null;
  const [activeSession, setActiveSession] = useState(null);

  useEffect(() => {
    if (!isSession) { setActiveSession(null); return; }
    getSession(activeKey).then(setActiveSession).catch(() => setActiveSession(null));
  }, [activeKey, isSession]);

  function parseBriefing(call) {
    if (!call) return null;
    const b = call.briefing;
    if (!b) return null;
    if (typeof b === 'object') return b;
    try { return JSON.parse(b); } catch { return null; }
  }

  const briefing = parseBriefing(activeCall);

  // Determine if call is still processing
  const isProcessing = activeCall && !briefing &&
    (activeCall.status === 'pending' || activeCall.status === 'running');

  useEffect(() => {
    if (!isOverview || !client) return;
    setFilesLoading(true);
    setFilesError(null);
    fetchFiles(client.id)
      .then(setFiles)
      .catch(err => setFilesError(err.message))
      .finally(() => setFilesLoading(false));
  }, [isOverview, client?.id]);

  const overviewContent = files?.['project-overview.md'] ?? null;

  return (
    <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">

      {/* Header */}
      <div className="flex-shrink-0 px-6 pt-4 pb-3 flex flex-col gap-2">
        <Breadcrumb items={[{ label: 'Home', to: '/' }, { label: client.name }]} />
        <div className="flex items-center justify-between">
          <div className="text-[22px] font-bold text-[#1a1a1a] tracking-[-0.02em]">{client.name}</div>
          {callPanelOpen ? (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 text-[13px] font-semibold text-[#ef4444]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#ef4444] animate-pulse flex-shrink-0" />
                Recording
              </div>
              <button
                onClick={() => setConfirmStop(true)}
                className="text-[12.5px] font-medium px-2.5 py-[5px] rounded-lg border border-[#e0e0e0] bg-white text-[#555] hover:border-[#bbb] cursor-pointer transition-colors font-inherit"
              >
                Stop
              </button>
            </div>
          ) : (
            <button
              onClick={() => setCallPanelOpen(true)}
              className="flex items-center gap-2 text-[13px] font-medium px-3 py-[6px] rounded-lg border border-[#e0e0e0] bg-white text-[#555] hover:border-[#bbb] cursor-pointer transition-colors font-inherit"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#ef4444] flex-shrink-0" />
              Start recording
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0 gap-3 px-6 pb-6 overflow-hidden">

        <RecordSidebar
          calls={calls}
          emails={emails}
          sessions={sessions}
          activeKey={activeKey}
          onSelect={setActiveKey}
          onUpload={() => setUploadOpen(true)}
          onRenameCall={handleRenameCall}
          archivedIds={archivedIds}
          deletedIds={deletedIds}
          onArchive={handleArchive}
          onDelete={handleDelete}
        />

        {/* Content card */}
        <div
          className="flex-1 flex flex-col min-w-0 overflow-hidden bg-white rounded-[10px]"
          style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.05)' }}
        >
          {activeEmail ? (
            <EmailThreadView
              email={activeEmail}
              onArchive={() => handleArchive(activeEmail.id)}
            />
          ) : isSession && activeSession ? (
            <SessionView
              session={activeSession}
              onArchive={() => handleArchive(activeSession.id)}
              onEndRecording={callPanelOpen && recordingSessionId === activeSession.id ? () => setConfirmStop(true) : null}
            />
          ) : isSession ? (
            <div className="flex-1 flex items-center justify-center text-[#bbb] text-[13px]">Loading…</div>
          ) : isOverview ? (
            <>
              <div className="flex items-center px-6 py-4 flex-shrink-0 border-b border-[#f0f0f0]">
                <div className="text-[17px] font-bold text-[#1a1a1a] tracking-[-0.02em]">Overview</div>
              </div>
              <div className="flex-1 overflow-y-auto min-w-0 px-6 py-5">
                <div className="max-w-[660px]">
                  {filesLoading ? (
                    <div className="flex items-center justify-center py-10 text-[#aaa] text-[13px]">Loading…</div>
                  ) : filesError ? (
                    <div className="text-[13px] text-[#e55] py-4">{filesError}</div>
                  ) : overviewContent != null ? (
                    <NotesEditor markdown={overviewContent} />
                  ) : (
                    <NotesEditor placeholder="No overview file found. Add notes here…" />
                  )}
                </div>
              </div>
            </>
          ) : activeCall ? (
            <>
              <RecordToolbar
                key={activeCall.id}
                call={{ ...activeCall, briefing }}
                transcriptOpen={transcriptOpen}
                onToggleTranscript={() => setTranscriptOpen(o => !o)}
                onArchive={() => handleArchive(activeCall.id)}
              />

              <div className="flex flex-1 min-h-0 overflow-hidden">

                {/* Main notes area */}
                <div
                  className="flex-1 overflow-y-auto min-w-0 px-6 py-5"
                  onScroll={e => setNoteScrolled(e.target.scrollTop > 72)}
                >
                  {/* Sticky context header — appears after 72px of scroll */}
                  {noteScrolled && <StickyCallHeader call={activeCall} briefing={briefing} />}

                  <div className="flex flex-col gap-6 max-w-[660px]">
                    {isProcessing ? (
                      <ProcessingState />
                    ) : briefing ? (
                      <>
                        <BriefingNotes briefing={briefing} />
                        {briefing.email_draft && (
                          <>
                            <div className="h-px bg-[#f0f0f0]" />
                            <EmailDraftCard emailDraft={briefing.email_draft} />
                          </>
                        )}
                      </>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-16 gap-3">
                        <div className="text-[14px] font-medium text-[#bbb]">No briefing available</div>
                        <div className="text-[12.5px] text-[#ccc] text-center leading-relaxed max-w-[200px]">
                          This call hasn't been processed yet, or processing failed.
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Transcript panel — drag-resizable */}
                {transcriptOpen && (
                  <div className="flex flex-shrink-0 h-full" style={{ width: transcript.width }}>
                    {/* Drag handle */}
                    <div
                      onMouseDown={transcript.onMouseDown}
                      className="w-1 flex-shrink-0 cursor-col-resize group flex items-center justify-center border-l border-[#f0f0f0]"
                    >
                      <div className="w-[3px] h-10 rounded-full bg-transparent group-hover:bg-[#d0d0d0] transition-colors" />
                    </div>
                    <div className="flex-1 overflow-hidden">
                      <TranscriptPanel call={activeCall} onClose={() => setTranscriptOpen(false)} />
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-[#bbb] text-[13px]">
              Select an item from the timeline.
            </div>
          )}
        </div>

        {/* Chat rail / panel */}
        {!chatOpen && <ChatRail onOpen={() => setChatOpen(true)} />}
        {chatOpen && (
          <ChatPanel
            clientId={client.id}
            clientName={client.name}
            callId={activeCall?.id || null}
            onClose={() => setChatOpen(false)}
          />
        )}

      </div>

      {uploadOpen && (
        <UploadModal
          defaultClientId={client.id}
          onClose={() => setUploadOpen(false)}
          onSuccess={() => setTimeout(() => window.location.reload(), 400)}
        />
      )}

      {confirmStop && (
        <div className="fixed inset-0 z-[10001] flex items-center justify-center bg-black/20 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 shadow-xl max-w-[280px] mx-4 border border-[#f0f0f0]">
            <div className="text-[16px] font-bold text-[#1a1a1a] mb-1.5">End recording?</div>
            <div className="text-[13px] text-[#888] mb-5 leading-relaxed">Your notes will be saved.</div>
            <div className="flex gap-2">
              <button
                onClick={() => setConfirmStop(false)}
                className="flex-1 py-2 text-[13px] text-[#555] border border-[#e0e0e0] rounded-xl bg-transparent cursor-pointer font-inherit hover:border-[#bbb]"
              >
                Cancel
              </button>
              <button
                onClick={() => { setConfirmStop(false); callEndRef.current?.(); }}
                className="flex-1 py-2 text-[13px] font-semibold text-white bg-[#1a1a1a] border-none rounded-xl cursor-pointer font-inherit hover:bg-[#333]"
              >
                End call
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmDeleteId && (
        <div className="fixed inset-0 z-[10001] flex items-center justify-center bg-black/20 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 shadow-xl max-w-[280px] mx-4 border border-[#f0f0f0]">
            <div className="text-[16px] font-bold text-[#1a1a1a] mb-1.5">Delete session?</div>
            <div className="text-[13px] text-[#888] mb-5 leading-relaxed">Moved to trash. Permanently deleted after 30 days.</div>
            <div className="flex gap-2">
              <button
                onClick={() => setConfirmDeleteId(null)}
                className="flex-1 py-2 text-[13px] text-[#555] border border-[#e0e0e0] rounded-xl bg-transparent cursor-pointer font-inherit hover:border-[#bbb]"
              >
                Cancel
              </button>
              <button
                onClick={() => confirmDelete(confirmDeleteId)}
                className="flex-1 py-2 text-[13px] font-semibold text-white bg-[#dc2626] border-none rounded-xl cursor-pointer font-inherit hover:bg-[#b91c1c]"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {callPanelOpen && (
        <CallPanel
          client={client}
          autoStart
          onClose={() => { setCallPanelOpen(false); setConfirmStop(false); setRecordingSessionId(null); refreshSessions(); }}
          onGoToRecord={(sessionId) => { setActiveKey(sessionId); setRecordingSessionId(sessionId); refreshSessions(); }}
          onRegisterEnd={fn => { callEndRef.current = fn; }}
          onSessionStart={id => setRecordingSessionId(id)}
          hideDock={activeKey === recordingSessionId}
        />
      )}
    </div>
  );
}
