import { useState, useEffect, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Bold, Italic, List, ListOrdered, Undo2, Redo2, Archive } from 'lucide-react';
import { formatDate } from '../../api/index';
import { updateNote, deleteNote, addNote } from '../../api/index';

// ── Toolbar ───────────────────────────────────────────────────────────────────

function ToolbarBtn({ active, onMouseDown, title, children }) {
  return (
    <button
      onMouseDown={onMouseDown}
      title={title}
      className={`w-6 h-6 flex items-center justify-center rounded text-[12px] border-none cursor-pointer transition-colors font-inherit
        ${active ? 'bg-[#1a1a1a] text-white' : 'bg-transparent text-[#999] hover:bg-[#f0f0f0] hover:text-[#333]'}`}
    >
      {children}
    </button>
  );
}

function Toolbar({ editor }) {
  if (!editor) return null;
  const cmd = fn => e => { e.preventDefault(); fn(); };
  return (
    <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-[#f0f0f0]">
      <ToolbarBtn active={editor.isActive('bold')} onMouseDown={cmd(() => editor.chain().focus().toggleBold().run())} title="Bold"><Bold size={13} /></ToolbarBtn>
      <ToolbarBtn active={editor.isActive('italic')} onMouseDown={cmd(() => editor.chain().focus().toggleItalic().run())} title="Italic"><Italic size={13} /></ToolbarBtn>
      <div className="w-px h-3.5 bg-[#e8e8e8] mx-1" />
      <ToolbarBtn active={editor.isActive('bulletList')} onMouseDown={cmd(() => editor.chain().focus().toggleBulletList().run())} title="Bullet list"><List size={13} /></ToolbarBtn>
      <ToolbarBtn active={editor.isActive('orderedList')} onMouseDown={cmd(() => editor.chain().focus().toggleOrderedList().run())} title="Numbered list"><ListOrdered size={13} /></ToolbarBtn>
      <div className="w-px h-3.5 bg-[#e8e8e8] mx-1" />
      <ToolbarBtn active={false} onMouseDown={cmd(() => editor.chain().focus().undo().run())} title="Undo"><Undo2 size={13} /></ToolbarBtn>
      <ToolbarBtn active={false} onMouseDown={cmd(() => editor.chain().focus().redo().run())} title="Redo"><Redo2 size={13} /></ToolbarBtn>
    </div>
  );
}

// ── Note group config ─────────────────────────────────────────────────────────

const NOTE_TYPES = {
  note:        { label: 'Notes',              color: '#444',    border: '#e0e0e0', bg: '#fafafa'  },
  action:      { label: 'Action items',       color: '#1d4ed8', border: '#bfdbfe', bg: '#eff6ff'  },
  question:    { label: 'Questions',          color: '#7c3aed', border: '#ddd6fe', bg: '#f5f3ff'  },
  commitment:  { label: 'They committed to',  color: '#065f46', border: '#a7f3d0', bg: '#ecfdf5'  },
  private:     { label: 'Private',            color: '#92400e', border: '#fde68a', bg: '#fffbeb'  },
};

// Build a bullet-list TipTap JSON from note array
function notesToDoc(notes) {
  if (!notes.length) return { type: 'doc', content: [{ type: 'paragraph' }] };
  return {
    type: 'doc',
    content: [{
      type: 'bulletList',
      content: notes.map(n => ({
        type: 'listItem',
        content: [{ type: 'paragraph', content: n.text ? [{ type: 'text', text: n.text }] : [] }],
      })),
    }],
  };
}

// Extract text lines from a TipTap doc JSON
function docToLines(doc) {
  const lines = [];
  function walk(node) {
    if (node.type === 'text') return node.text || '';
    if (!node.content) return '';
    const inner = node.content.map(walk).join('');
    // Block-level nodes produce a line entry
    const blocks = new Set(['paragraph', 'listItem', 'heading', 'blockquote', 'codeBlock']);
    if (blocks.has(node.type)) { if (inner.trim()) lines.push(inner.trim()); return ''; }
    return inner;
  }
  walk(doc);
  return lines;
}

// ── NoteGroup — one shared TipTap editor for all notes in the group ───────────

function NoteGroup({ type, notes, sessionId, onGroupChanged }) {
  const cfg = NOTE_TYPES[type];
  const [focused, setFocused] = useState(false);
  const notesRef = useRef(notes);
  useEffect(() => { notesRef.current = notes; }, [notes]);

  const editor = useEditor({
    extensions: [StarterKit],
    content: notesToDoc(notes),
    editorProps: {
      attributes: { class: 'outline-none text-[13px] leading-[1.65]' },
    },
    onFocus: () => setFocused(true),
    onBlur:  () => { setFocused(false); handleSave(); },
  });

  // Re-sync editor content if notes change externally (e.g. parent re-fetch)
  // but only when not focused to avoid disrupting typing
  const prevNotesKey = useRef(notes.map(n => n.id + n.text).join('|'));
  useEffect(() => {
    if (!editor || focused) return;
    const key = notes.map(n => n.id + n.text).join('|');
    if (key !== prevNotesKey.current) {
      prevNotesKey.current = key;
      editor.commands.setContent(notesToDoc(notes));
    }
  }, [notes, focused, editor]);

  async function handleSave() {
    if (!editor) return;
    const newLines = docToLines(editor.getJSON());
    const oldNotes = notesRef.current;

    const updates = [];
    const maxLen = Math.max(newLines.length, oldNotes.length);

    for (let i = 0; i < maxLen; i++) {
      if (i < newLines.length && i < oldNotes.length) {
        // Update if changed
        if (newLines[i] !== oldNotes[i].text) {
          updates.push(updateNote(sessionId, oldNotes[i].id, { text: newLines[i] }));
        }
      } else if (i < newLines.length) {
        // New note
        updates.push(addNote(sessionId, { text: newLines[i], type }));
      } else {
        // Deleted note
        updates.push(deleteNote(sessionId, oldNotes[i].id));
      }
    }

    if (updates.length) {
      await Promise.allSettled(updates);
      onGroupChanged();
    }
  }

  return (
    <div
      className="rounded-xl flex flex-col"
      style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}
    >
      <div className="px-4 pt-3 pb-1 text-[11px] font-bold uppercase tracking-wider" style={{ color: cfg.color }}>
        {cfg.label}
      </div>

      <div
        className={`mx-3 mb-3 rounded-lg border transition-all
          ${focused
            ? 'border-[#d0d0d0] bg-white shadow-sm'
            : 'border-transparent hover:border-[#e0e0e0] hover:bg-white cursor-text'
          }`}
        onClick={() => !focused && editor?.commands.focus('end')}
      >
        {focused && <Toolbar editor={editor} />}
        <div className={focused ? 'px-3 pb-3 pt-1' : 'px-3 py-2'} style={{ color: cfg.color }}>
          <EditorContent editor={editor} />
        </div>
      </div>
    </div>
  );
}

// ── SessionView ───────────────────────────────────────────────────────────────

export default function SessionView({ session, onRefresh, onArchive, onEndRecording }) {
  const [notes, setNotes] = useState(session.notes || []);
  useEffect(() => { setNotes(session.notes || []); }, [session.id, session.notes]);

  const sessionId = session.id;
  const nonBookmarks = notes.filter(n => !n.is_bookmark);
  const bookmarks = notes.filter(n => n.is_bookmark);
  const [showPrivate, setShowPrivate] = useState(false);

  const byType = {};
  for (const n of nonBookmarks) {
    const t = n.type || 'note';
    if (!byType[t]) byType[t] = [];
    byType[t].push(n);
  }

  const order = ['action', 'commitment', 'question', 'note'];
  const hasPrivate = (byType.private || []).length > 0;

  // After any group saves, re-fetch session to keep notes state fresh
  async function handleGroupChanged() {
    try {
      const { getSession } = await import('../../api/index');
      const updated = await getSession(sessionId);
      setNotes(updated.notes || []);
    } catch {}
  }

  const duration = session.ended_at && session.started_at
    ? (() => {
        const ms = new Date(session.ended_at) - new Date(session.started_at);
        const m = Math.floor(ms / 60000);
        const s = Math.floor((ms % 60000) / 1000);
        return m > 0 ? `${m}m ${s}s` : `${s}s`;
      })()
    : null;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between px-6 py-4 border-b border-[#f0f0f0] flex-shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <div className="text-[17px] font-bold text-[#1a1a1a] tracking-[-0.02em]">Call notes</div>
            {!session.ended_at && (
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#fee2e2] text-[#dc2626] text-[11px] font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-[#dc2626] animate-pulse flex-shrink-0" />
                Recording
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 text-[12px] text-[#888]">
            <span>{formatDate(session.started_at)}</span>
            {duration && <><span>·</span><span>{duration}</span></>}
            <span>·</span>
            <span>{nonBookmarks.length} note{nonBookmarks.length !== 1 ? 's' : ''}</span>
            {session.job_id && (
              <><span>·</span><span className="text-[#4a6cf7]">Linked to transcript</span></>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 mt-0.5">
          {onEndRecording && !session.ended_at && (
            <button
              onClick={onEndRecording}
              className="flex items-center gap-1.5 text-[12.5px] font-medium px-3 py-[6px] rounded-lg border border-[#e0e0e0] bg-white text-[#ef4444] hover:border-[#ef4444] cursor-pointer transition-colors font-inherit"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#ef4444] animate-pulse flex-shrink-0" />
              Stop recording
            </button>
          )}
          {onArchive && (
            <button
              onClick={onArchive}
              className="flex items-center gap-1.5 text-[12.5px] font-medium px-3 py-[6px] rounded-lg border border-[#e0e0e0] bg-white text-[#555] hover:border-[#bbb] cursor-pointer transition-colors font-inherit"
            >
              <Archive size={12} />
              Archive
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="flex flex-col gap-4 max-w-[580px]">
          {notes.length === 0 && (
            <div className="text-[13px] text-[#bbb] py-8 text-center">No notes in this session.</div>
          )}

          {/* Bookmarks */}
          {bookmarks.length > 0 && (
            <div className="flex flex-col gap-1">
              <div className="text-[11px] font-bold uppercase tracking-wider text-[#aaa]">Bookmarks</div>
              {bookmarks.map(n => (
                <div key={n.id} className="flex items-center gap-2 text-[12.5px] text-[#aaa]">
                  <span>📍</span><span>{n.text}</span>
                </div>
              ))}
            </div>
          )}

          {/* Note groups — one shared editor per group */}
          {order.map(type =>
            byType[type]?.length > 0
              ? <NoteGroup key={type} type={type} notes={byType[type]} sessionId={sessionId} onGroupChanged={handleGroupChanged} />
              : null
          )}

          {/* Private */}
          {hasPrivate && (
            <div>
              <button
                onClick={() => setShowPrivate(v => !v)}
                className="text-[12px] text-[#bbb] hover:text-[#888] bg-transparent border-none cursor-pointer p-0 font-inherit transition-colors"
              >
                {showPrivate ? 'Hide private notes' : `Show ${byType.private.length} private note${byType.private.length !== 1 ? 's' : ''}`}
              </button>
              {showPrivate && (
                <div className="mt-2">
                  <NoteGroup type="private" notes={byType.private} sessionId={sessionId} onGroupChanged={handleGroupChanged} />
                </div>
              )}
            </div>
          )}

          {!session.job_id && notes.length > 0 && (
            <div className="text-[12px] text-[#bbb] border border-dashed border-[#e0e0e0] rounded-xl px-4 py-3 leading-relaxed">
              Upload a transcript and link it to this session to get an AI briefing that incorporates your notes.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
