import { useState, useEffect, useRef, useCallback } from 'react';
import { Bookmark, Minus, X, PhoneOff, ArrowUpRight } from 'lucide-react';
import { createSession, endSession, addNote, updateNote, deleteNote } from '../../api/index';
import PreCallBrief from './PreCallBrief';

// ── Note type config ──────────────────────────────────────────────────────────

const NOTE_TYPES = {
  note:        { label: 'Note',              badge: null,  color: '#1a1a1a', border: 'transparent', bg: 'transparent' },
  action:      { label: 'Action item',       badge: 'A',   color: '#1d4ed8', border: '#bfdbfe',     bg: '#eff6ff'     },
  question:    { label: 'Question',          badge: '?',   color: '#7c3aed', border: '#ddd6fe',     bg: '#f5f3ff'     },
  commitment:  { label: 'They committed to', badge: '🤝',  color: '#065f46', border: '#a7f3d0',     bg: '#ecfdf5'     },
  private:     { label: 'Private',           badge: '🔒',  color: '#92400e', border: '#fde68a',     bg: '#fffbeb'     },
};

// ── usePanelState — combined drag + resize, fixes left/top anchor ─────────────

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function usePanelState(initPos, initSize) {
  const [pos,  setPos]  = useState(initPos);
  const [size, setSize] = useState(initSize);
  const drag = useRef(null);

  const onDragDown = useCallback((e) => {
    if (e.button !== 0) return;
    drag.current = { type: 'drag', x0: e.clientX, y0: e.clientY, px: pos.x, py: pos.y };
    e.preventDefault();
  }, [pos]);

  const onResizeDown = useCallback((e, edge) => {
    if (e.button !== 0) return;
    drag.current = { type: 'resize', edge, x0: e.clientX, y0: e.clientY, px: pos.x, py: pos.y, sw: size.w, sh: size.h };
    e.preventDefault();
    e.stopPropagation();
  }, [pos, size]);

  useEffect(() => {
    function onMove(e) {
      if (!drag.current) return;
      const d = drag.current;
      const dx = e.clientX - d.x0, dy = e.clientY - d.y0;
      if (d.type === 'drag') {
        setPos({ x: d.px + dx, y: d.py + dy });
      } else {
        let nw = d.sw, nh = d.sh, nx = d.px, ny = d.py;
        if (d.edge.includes('right'))  nw = clamp(d.sw + dx, 260, 640);
        if (d.edge.includes('left')) { nw = clamp(d.sw - dx, 260, 640); nx = d.px + d.sw - nw; }
        if (d.edge.includes('bottom')) nh = clamp(d.sh + dy, 300, 900);
        if (d.edge.includes('top'))  { nh = clamp(d.sh - dy, 300, 900); ny = d.py + d.sh - nh; }
        setSize({ w: nw, h: nh });
        setPos({ x: nx, y: ny });
      }
    }
    function onUp() { drag.current = null; }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  return { pos, size, onDragDown, onResizeDown };
}

// ── useTimer ──────────────────────────────────────────────────────────────────

function useTimer(startedAt) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!startedAt) return;
    const start = new Date(startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const s = String(elapsed % 60).padStart(2, '0');
  return `${m}:${s}`;
}

// ── ContextMenu ───────────────────────────────────────────────────────────────

function ContextMenu({ x, y, onSelect, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [onClose]);

  const options = [
    { type: 'note',       label: 'Plain note' },
    { type: 'action',     label: 'Action item' },
    { type: 'question',   label: 'Question' },
    { type: 'commitment', label: 'They committed to this' },
    { type: 'private',    label: 'Private (hidden from briefing)' },
    null,
    { type: '__delete__', label: 'Delete' },
  ];

  return (
    <div
      ref={ref}
      className="fixed z-[10001] bg-white rounded-lg py-1 min-w-[210px]"
      style={{ top: y, left: x, boxShadow: '0 4px 20px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.06)' }}
    >
      {options.map((opt, i) =>
        opt === null ? <div key={i} className="h-px bg-[#f0f0f0] my-1" /> : (
          <button
            key={opt.type}
            onClick={() => { onSelect(opt.type); onClose(); }}
            className={`w-full text-left text-[12.5px] px-3 py-1.5 cursor-pointer bg-transparent border-none font-inherit hover:bg-[#f5f5f5] transition-colors
              ${opt.type === '__delete__' ? 'text-[#dc2626]' : 'text-[#333]'}`}
          >
            {NOTE_TYPES[opt.type]?.badge && (
              <span className="inline-block w-5 text-center mr-1 text-[11px] font-semibold" style={{ color: NOTE_TYPES[opt.type].color }}>
                {NOTE_TYPES[opt.type].badge}
              </span>
            )}
            {opt.label}
          </button>
        )
      )}
    </div>
  );
}

// ── NoteBlock ─────────────────────────────────────────────────────────────────
// Uses note._key as React key (stable across temp→server ID transition) to
// prevent remount/focus-loss when the server ID arrives after addNote.

function NoteBlock({ note, blockRef, onContextMenu, onTextChange, onEnterKey, onDeleteKey }) {
  const cfg = NOTE_TYPES[note.type] || NOTE_TYPES.note;

  if (note.is_bookmark) {
    return (
      <div
        className="flex items-center gap-1.5 py-0.5 text-[11.5px] text-[#bbb] select-none"
        onContextMenu={e => { e.preventDefault(); onContextMenu(e, note); }}
      >
        <Bookmark size={10} className="text-[#f59e0b] fill-[#f59e0b] flex-shrink-0" />
        <span className="font-mono">{note.text}</span>
      </div>
    );
  }

  const hasStyle = cfg.bg !== 'transparent';
  return (
    <div
      className={hasStyle ? 'rounded-md' : ''}
      style={{
        borderLeft: cfg.border !== 'transparent' ? `2px solid ${cfg.border}` : '2px solid transparent',
        background: hasStyle ? cfg.bg : 'transparent',
        padding: hasStyle ? '2px 6px' : '1px 0 1px 8px',
        marginLeft: hasStyle ? '0' : '-2px',
      }}
      onContextMenu={e => { e.preventDefault(); onContextMenu(e, note); }}
    >
      <div
        ref={blockRef}
        contentEditable
        suppressContentEditableWarning
        className="outline-none text-[13px] leading-[1.6] break-words"
        style={{ color: cfg.color, minHeight: '1.6em' }}
        onBlur={e => {
          const v = e.currentTarget.textContent;
          if (v !== note.text) onTextChange(note.id, note._key, v);
        }}
        onKeyDown={e => {
          if (e.key === 'Enter')    { e.preventDefault(); onEnterKey(note._key); }
          if (e.key === 'Backspace' && e.currentTarget.textContent === '') {
            e.preventDefault(); onDeleteKey(note._key);
          }
        }}
      >
        {note.text}
      </div>
    </div>
  );
}

// ── EndConfirm overlay ────────────────────────────────────────────────────────

function EndConfirm({ onConfirm, onCancel }) {
  return (
    <div className="absolute inset-0 bg-white/95 backdrop-blur-sm flex flex-col items-center justify-center z-20 rounded-[14px]">
      <div className="text-[15px] font-bold text-[#1a1a1a] mb-1">End recording?</div>
      <div className="text-[12.5px] text-[#999] mb-5">Your notes will be saved.</div>
      <div className="flex gap-2">
        <button onClick={onCancel}  className="px-5 py-2 text-[13px] text-[#555] border border-[#e0e0e0] rounded-xl bg-transparent cursor-pointer font-inherit hover:border-[#bbb]">Cancel</button>
        <button onClick={onConfirm} className="px-5 py-2 text-[13px] font-semibold text-white bg-[#1a1a1a] border-none rounded-xl cursor-pointer font-inherit hover:bg-[#333]">End call</button>
      </div>
    </div>
  );
}

// ── helpers ───────────────────────────────────────────────────────────────────

let _keyCounter = 0;
function newKey() { return `ck-${++_keyCounter}`; }

function focusEl(el) {
  if (!el) return;
  el.focus();
  try {
    const range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(false);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(range);
  } catch {}
}

// ── CallPanel ─────────────────────────────────────────────────────────────────

export default function CallPanel({ client, autoStart, onClose, onGoToRecord, onRegisterEnd, onSessionStart, hideDock }) {
  const [session,     setSession]     = useState(null);
  const [notes,       setNotes]       = useState([]);
  const [docked,      setDocked]      = useState(false);
  const [agendaItems, setAgendaItems] = useState([]);
  const [contextMenu, setContextMenu] = useState(null);
  const [confirmEnd,  setConfirmEnd]  = useState(false);

  const timer      = useTimer(session?.started_at);
  const noteRefs   = useRef({});   // _key → DOM element
  const sessionRef = useRef(null);
  const notesRef   = useRef([]);
  const autoStarted = useRef(false);

  useEffect(() => { sessionRef.current = session; }, [session]);
  useEffect(() => { notesRef.current   = notes;   }, [notes]);

  const { pos, size, onDragDown, onResizeDown } = usePanelState(
    { x: window.innerWidth - 360, y: window.innerHeight - 560 },
    { w: 320, h: 520 }
  );

  // Expose handleEndCall to parent (for RecordView "Stop" button)
  const endCallRefInternal = useRef(null);
  useEffect(() => { endCallRefInternal.current = handleEndCall; });
  useEffect(() => {
    onRegisterEnd?.(() => endCallRefInternal.current?.());
    return () => onRegisterEnd?.(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-start
  useEffect(() => {
    if (autoStart && !autoStarted.current) { autoStarted.current = true; startCall(); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function startCall() {
    try {
      const s = await createSession(client.id);
      setSession(s);
      onSessionStart?.(s.id);
      // Seed one empty note so the pad is immediately ready
      const k = newKey();
      const first = await addNote(s.id, { text: '', type: 'note', position: 0 });
      setNotes([{ ...first, _key: k }]);
      setTimeout(() => focusEl(noteRefs.current[k]), 60);
    } catch (err) {
      console.error('Failed to start session:', err);
    }
  }

  async function handleEndCall() {
    const s = sessionRef.current;
    if (s) { try { await endSession(s.id); } catch {} }
    onClose();
  }

  // ── Note operations ───────────────────────────────────────────────────────

  // Called from NoteBlock onBlur. noteId may still be a temp id if save is in-flight.
  async function handleTextChange(noteId, noteKey, newText) {
    const s = sessionRef.current;
    if (!s) return;
    setNotes(prev => prev.map(n => n._key === noteKey ? { ...n, text: newText } : n));
    // Only persist if the note has a real server id
    if (noteId && !String(noteId).startsWith('tmp-')) {
      try { await updateNote(s.id, noteId, { text: newText }); } catch {}
    }
  }

  // Called with _key (stable), not id
  async function handleEnterKey(noteKey) {
    const s = sessionRef.current;
    if (!s) return;
    const all = notesRef.current;
    const idx = all.findIndex(n => n._key === noteKey);
    const k = newKey();
    const optimistic = { id: null, _key: k, session_id: s.id, text: '', type: 'note', is_bookmark: false, position: idx + 1 };
    setNotes(prev => { const next = [...prev]; next.splice(idx + 1, 0, optimistic); return next; });
    setTimeout(() => focusEl(noteRefs.current[k]), 10);
    try {
      const saved = await addNote(s.id, { text: '', type: 'note', position: idx + 1 });
      // Merge: preserve any text the user typed during the async gap
      setNotes(prev => prev.map(n => {
        if (n._key !== k) return n;
        const localText = n.text; // text typed while save was in-flight
        const merged = { ...saved, _key: k, text: localText };
        // Persist the text if they already typed something
        if (localText) updateNote(s.id, saved.id, { text: localText }).catch(() => {});
        return merged;
      }));
    } catch {
      setNotes(prev => prev.filter(n => n._key !== k));
    }
  }

  async function handleDeleteKey(noteKey) {
    const s = sessionRef.current;
    if (!s) return;
    const all = notesRef.current;
    const nonBm = all.filter(n => !n.is_bookmark);
    if (nonBm.length <= 1) return; // always keep one block
    const idx = nonBm.findIndex(n => n._key === noteKey);
    const target = nonBm[idx - 1] || nonBm[idx + 1];
    const note = nonBm[idx];
    setNotes(prev => prev.filter(n => n._key !== noteKey));
    if (target) setTimeout(() => focusEl(noteRefs.current[target._key]), 10);
    if (note?.id && !String(note.id).startsWith('tmp-')) {
      try { await deleteNote(s.id, note.id); } catch {}
    }
  }

  async function handleContextAction(actionType, note) {
    const s = sessionRef.current;
    if (!s) return;
    if (actionType === '__delete__') {
      setNotes(prev => prev.filter(n => n._key !== note._key));
      if (note.id && !String(note.id).startsWith('tmp-')) {
        try { await deleteNote(s.id, note.id); } catch {}
      }
      return;
    }
    setNotes(prev => prev.map(n => n._key === note._key ? { ...n, type: actionType } : n));
    if (note.id && !String(note.id).startsWith('tmp-')) {
      try { await updateNote(s.id, note.id, { type: actionType }); } catch {}
    }
  }

  async function submitBookmark() {
    const s = sessionRef.current;
    if (!s) return;
    const k = newKey();
    const text = `📍 ${timer}`;
    const optimistic = { id: null, _key: k, session_id: s.id, text, type: 'note', is_bookmark: true, position: notes.length };
    setNotes(prev => [...prev, optimistic]);
    try {
      const saved = await addNote(s.id, { text, type: 'note', isBookmark: true, position: notes.length });
      setNotes(prev => prev.map(n => n._key === k ? { ...saved, _key: k } : n));
    } catch {
      setNotes(prev => prev.filter(n => n._key !== k));
    }
  }

  function focusLastNote() {
    const nonBm = notes.filter(n => !n.is_bookmark);
    if (nonBm.length > 0) focusEl(noteRefs.current[nonBm[nonBm.length - 1]._key]);
  }

  // ── Dock tab ──────────────────────────────────────────────────────────────

  // hideDock: when user is viewing the active session in the main panel,
  // the dock tab hides (like Gmail's full compose view hiding the mini draft).
  const dockTabEl = hideDock ? null : (
    <div className="fixed bottom-0 right-8 z-[9999] flex items-stretch select-none"
      style={{ boxShadow: '0 -2px 12px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.08)' }}
    >
      <button
        onClick={() => setDocked(false)}
        className="flex items-center gap-2.5 bg-[#1a1a1a] text-white px-4 py-2.5 cursor-pointer border-none font-inherit rounded-tl-xl hover:bg-[#2a2a2a] transition-colors"
      >
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${session ? 'bg-[#ef4444] animate-pulse' : 'bg-[#666]'}`} />
        <span className="text-[13px] font-medium">{client.name}</span>
        {session && <span className="text-[11.5px] font-mono text-[#888]">{timer}</span>}
        {notes.filter(n => !n.is_bookmark && n.text).length > 0 && (
          <span className="text-[11px] bg-white/10 px-1.5 py-0.5 rounded text-[#ccc]">
            {notes.filter(n => !n.is_bookmark && n.text).length}
          </span>
        )}
      </button>
      <button
        onClick={() => setConfirmEnd(true)}
        className="flex items-center px-3 bg-[#111] text-[#666] hover:text-[#ef4444] border-none border-l border-white/10 cursor-pointer transition-colors rounded-tr-xl font-inherit"
        title="End call"
      >
        <X size={13} />
      </button>
    </div>
  );

  if (docked) return (
    <>
      {dockTabEl}
      {confirmEnd && (
        <div className="fixed inset-0 z-[10001] flex items-center justify-center bg-black/20">
          <EndConfirm onConfirm={() => { setConfirmEnd(false); handleEndCall(); }} onCancel={() => setConfirmEnd(false)} />
        </div>
      )}
    </>
  );

  // ── Expanded panel ────────────────────────────────────────────────────────

  const nonBookmarkNotes = notes.filter(n => !n.is_bookmark);

  return (
    <>
      <div
        className="fixed z-[9999] flex flex-col bg-white rounded-[14px] overflow-hidden"
        style={{ left: pos.x, top: pos.y, width: size.w, height: size.h, boxShadow: '0 8px 40px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.07)' }}
      >
        {/* Resize handles */}
        <div className="absolute right-0 top-4 bottom-4 w-1 cursor-ew-resize z-10"  onMouseDown={e => onResizeDown(e, 'right')} />
        <div className="absolute left-0  top-4 bottom-4 w-1 cursor-ew-resize z-10"  onMouseDown={e => onResizeDown(e, 'left')} />
        <div className="absolute bottom-0 left-4 right-4 h-1 cursor-ns-resize z-10" onMouseDown={e => onResizeDown(e, 'bottom')} />
        <div className="absolute bottom-0 right-0 w-4 h-4 cursor-nwse-resize z-10" onMouseDown={e => onResizeDown(e, 'right bottom')} />
        <div className="absolute bottom-0 left-0  w-4 h-4 cursor-nesw-resize z-10" onMouseDown={e => onResizeDown(e, 'left bottom')} />

        {/* Header */}
        <div
          onMouseDown={onDragDown}
          className="flex items-center gap-2 px-3 py-2.5 border-b border-[#f0f0f0] cursor-grab active:cursor-grabbing flex-shrink-0 bg-white select-none"
        >
          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${session ? 'bg-[#ef4444] animate-pulse' : 'bg-[#d1d5db]'}`} />
          <span className="text-[13px] font-semibold text-[#1a1a1a] flex-1 truncate">{client.name}</span>
          {session && <span className="text-[12px] font-mono text-[#999]">{timer}</span>}
          {session && onGoToRecord && (
            <button
              onMouseDown={e => e.stopPropagation()}
              onClick={() => { onGoToRecord(session.id); setDocked(true); }}
              className="flex items-center gap-1 text-[11.5px] font-medium text-[#4a6cf7] hover:text-[#2a4cd7] bg-transparent border-none cursor-pointer px-1.5 py-1 rounded transition-colors font-inherit whitespace-nowrap"
              title="Open in record view"
            >
              <ArrowUpRight size={12} />
              Open
            </button>
          )}
          <button onMouseDown={e => e.stopPropagation()} onClick={() => setDocked(true)}
            className="text-[#ccc] hover:text-[#555] bg-transparent border-none cursor-pointer p-1 rounded transition-colors" title="Minimize">
            <Minus size={13} />
          </button>
          {session ? (
            <button onMouseDown={e => e.stopPropagation()} onClick={() => setConfirmEnd(true)}
              className="text-[#ccc] hover:text-[#ef4444] bg-transparent border-none cursor-pointer p-1 rounded transition-colors" title="End call">
              <PhoneOff size={12} />
            </button>
          ) : (
            <button onMouseDown={e => e.stopPropagation()} onClick={onClose}
              className="text-[#ccc] hover:text-[#e55] bg-transparent border-none cursor-pointer p-1 rounded transition-colors" title="Close">
              <X size={13} />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
          <PreCallBrief clientId={client.id} agendaItems={agendaItems} onAgendaChange={setAgendaItems} />

          {!session ? (
            <div className="flex-1 flex items-center justify-center">
              <span className="text-[12.5px] text-[#ccc]">Starting…</span>
            </div>
          ) : (
            <>
              <div
                className="flex-1 overflow-y-auto px-3 pt-2 pb-1 flex flex-col min-h-0 cursor-text"
                onClick={e => { if (e.target === e.currentTarget) focusLastNote(); }}
              >
                {notes.filter(n => n.is_bookmark).map(note => (
                  <NoteBlock key={note._key} note={note}
                    blockRef={el => { noteRefs.current[note._key] = el; }}
                    onContextMenu={(e, n) => setContextMenu({ x: e.clientX, y: e.clientY, note: n })}
                    onTextChange={handleTextChange} onEnterKey={handleEnterKey} onDeleteKey={handleDeleteKey} />
                ))}
                {nonBookmarkNotes.map(note => (
                  <NoteBlock key={note._key} note={note}
                    blockRef={el => { noteRefs.current[note._key] = el; }}
                    onContextMenu={(e, n) => setContextMenu({ x: e.clientX, y: e.clientY, note: n })}
                    onTextChange={handleTextChange} onEnterKey={handleEnterKey} onDeleteKey={handleDeleteKey} />
                ))}
                <div className="flex-1 min-h-[32px]" onClick={focusLastNote} />
              </div>
              <div className="flex-shrink-0 border-t border-[#f0f0f0] px-3 py-2">
                <button onClick={submitBookmark}
                  className="flex items-center gap-1.5 text-[12px] text-[#aaa] hover:text-[#f59e0b] bg-transparent border-none cursor-pointer p-0 font-inherit transition-colors"
                  title="Drop a timestamped bookmark">
                  <Bookmark size={12} />
                  Bookmark
                  <span className="font-mono text-[11px] ml-1">{timer}</span>
                </button>
              </div>
            </>
          )}
        </div>

        {confirmEnd && (
          <EndConfirm onConfirm={() => { setConfirmEnd(false); handleEndCall(); }} onCancel={() => setConfirmEnd(false)} />
        )}
      </div>

      {contextMenu && (
        <ContextMenu x={contextMenu.x} y={contextMenu.y}
          onSelect={type => handleContextAction(type, contextMenu.note)}
          onClose={() => setContextMenu(null)} />
      )}
    </>
  );
}
