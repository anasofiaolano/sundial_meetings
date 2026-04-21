import { useState, useRef, useEffect, useCallback } from 'react';
import { LayoutGrid, Phone, Mail, Search, Upload, Pencil, X, ChevronLeft, NotebookPen, Archive, Trash2 } from 'lucide-react';
import { formatDateShort, renameCall } from '../../api/index';
import { useToast } from '../../components/Toast';

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatCallName(raw) {
  if (!raw) return 'Untitled';
  return raw.replace(/^\d{6,8}[_\s]+/, '').replace(/_/g, ' ').trim() || raw;
}

function monthKey(iso) {
  if (!iso) return 'Unknown';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function dayKey(iso) {
  if (!iso) return 'Unknown';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
}

// Returns: [{ monthLabel, days: [{ dayLabel, items }] }]
function groupByMonthAndDay(items) {
  const monthOrder = [];
  const monthMap = {};  // monthLabel -> { dayOrder, dayMap }

  for (const item of items) {
    const mk = monthKey(item.date);
    const dk = dayKey(item.date);
    if (!monthMap[mk]) { monthMap[mk] = { dayOrder: [], dayMap: {} }; monthOrder.push(mk); }
    const m = monthMap[mk];
    if (!m.dayMap[dk]) { m.dayMap[dk] = []; m.dayOrder.push(dk); }
    m.dayMap[dk].push(item);
  }

  return monthOrder.map(mk => ({
    monthLabel: mk,
    days: monthMap[mk].dayOrder.map(dk => ({ dayLabel: dk, items: monthMap[mk].dayMap[dk] })),
  }));
}

function callPreview(call) {
  let b = call.briefing;
  if (!b) return null;
  if (typeof b === 'string') { try { b = JSON.parse(b); } catch { return null; } }
  const s = b?.summary;
  if (!s || typeof s !== 'string') return null;
  const sentence = s.split(/[.!?]/)[0].trim();
  return sentence.length > 72 ? sentence.slice(0, 70) + '…' : sentence;
}

function callStatus(call) {
  let b = call.briefing;
  if (b) {
    if (typeof b === 'string') { try { b = JSON.parse(b); } catch { b = null; } }
    if (b && typeof b === 'object' && Object.keys(b).length > 0) return 'done';
  }
  if (call.status === 'running') return 'running';
  if (call.status === 'pending') return 'pending';
  if (call.status === 'failed') return 'failed';
  return 'none';
}

// ── Normalize items ───────────────────────────────────────────────────────────

function normalizeItems(calls, emails, sessions, archivedIds, deletedIds, showArchived) {
  const callItems = calls
    .filter(c => !deletedIds.has(c.id) && (showArchived ? archivedIds.has(c.id) : !archivedIds.has(c.id)))
    .map(c => ({ id: c.id, type: 'call', date: c.created_at, name: formatCallName(c.transcript_name), raw: c }));

  const emailItems = emails
    .filter(e => !deletedIds.has(e.id) && (showArchived ? archivedIds.has(e.id) : !archivedIds.has(e.id)))
    .map(e => ({ id: e.id, type: 'email', date: e.thread_date, name: e.subject || '(No subject)', raw: e }));

  const sessionItems = sessions
    .filter(s => s.status === 'ended' && !s.job_id && !deletedIds.has(s.id) && (showArchived ? archivedIds.has(s.id) : !archivedIds.has(s.id)))
    .map(s => ({ id: s.id, type: 'session', date: s.started_at, name: 'Call notes', raw: s }));

  return [...callItems, ...emailItems, ...sessionItems].sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));
}

// ── Status dot ────────────────────────────────────────────────────────────────

function StatusDot({ status }) {
  if (status === 'done')    return <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] flex-shrink-0" />;
  if (status === 'running' || status === 'pending') return <span className="w-1.5 h-1.5 rounded-full bg-[#f59e0b] flex-shrink-0 animate-pulse" />;
  if (status === 'failed')  return <span className="w-1.5 h-1.5 rounded-full bg-[#ef4444] flex-shrink-0" />;
  return <span className="w-1.5 h-1.5 rounded-full bg-[#e0e0e0] flex-shrink-0" />;
}

// ── Inline rename ─────────────────────────────────────────────────────────────

function RenameInput({ initialValue, onSave, onCancel }) {
  const [val, setVal] = useState(initialValue);
  return (
    <form
      onSubmit={e => { e.preventDefault(); const t = val.trim(); if (t && t !== initialValue) onSave(t); else onCancel(); }}
      onClick={e => e.stopPropagation()}
      className="flex-1 min-w-0"
    >
      <input
        autoFocus
        value={val}
        onChange={e => setVal(e.target.value)}
        onBlur={() => { const t = val.trim(); if (t && t !== initialValue) onSave(t); else onCancel(); }}
        onKeyDown={e => { if (e.key === 'Escape') onCancel(); }}
        className="w-full text-[12.5px] font-semibold text-[#1a1a1a] bg-white border border-[#4a6cf7] rounded-md px-2 py-0.5 outline-none shadow-[0_0_0_3px_rgba(74,108,247,0.12)]"
      />
    </form>
  );
}

const FADE_MASK = 'linear-gradient(to right, black calc(100% - 18px), transparent 100%)';

// ── Context menu ──────────────────────────────────────────────────────────────

function ContextMenu({ x, y, options, onClose }) {
  useEffect(() => {
    const close = () => onClose();
    window.addEventListener('mousedown', close);
    window.addEventListener('keydown', e => { if (e.key === 'Escape') onClose(); });
    return () => { window.removeEventListener('mousedown', close); };
  }, [onClose]);

  return (
    <div
      style={{ position: 'fixed', left: x, top: y, zIndex: 1000, boxShadow: '0 8px 30px rgba(0,0,0,0.14), 0 0 0 1px rgba(0,0,0,0.07)' }}
      className="bg-white rounded-[10px] py-1 min-w-[150px]"
      onMouseDown={e => e.stopPropagation()}
    >
      {options.map((opt, i) => (
        <button
          key={i}
          onClick={() => { opt.action(); onClose(); }}
          className={`w-full text-left px-3 py-[7px] text-[13px] border-none bg-transparent cursor-pointer hover:bg-[#f5f5f5] transition-colors font-inherit flex items-center gap-2.5
            ${opt.danger ? 'text-[#dc2626] hover:bg-[#fef2f2]' : 'text-[#1a1a1a]'}`}
        >
          {opt.icon && <span className="flex-shrink-0">{opt.icon}</span>}
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ── Call item ─────────────────────────────────────────────────────────────────

function CallItem({ call, isActive, isKeyFocused, onSelect, onRename, onContextMenu, buttonRef }) {
  const [renaming, setRenaming] = useState(false);
  const [localName, setLocalName] = useState(null);
  const addToast = useToast();

  const displayName = localName ?? formatCallName(call.transcript_name);
  const preview = callPreview(call);
  const status = callStatus(call);
  const isHighlighted = isActive || isKeyFocused;

  async function handleRename(newName) {
    setRenaming(false);
    setLocalName(newName);
    try {
      await renameCall(call.id, newName);
      onRename?.(call.id, newName);
      addToast('Call renamed', 'success');
    } catch {
      setLocalName(null);
      addToast('Rename failed', 'error');
    }
  }

  return (
    <div className="relative group/item">
      {isActive && (
        <div className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-[#15803d]" />
      )}
      <button
        ref={buttonRef}
        onClick={() => { if (!renaming) onSelect(call.id); }}
        onContextMenu={e => { e.preventDefault(); onContextMenu(e, call.id, 'call'); }}
        className={`w-full text-left flex items-start gap-2 pl-3 pr-2 py-2.5 rounded-xl border-none cursor-pointer transition-colors font-inherit focus:outline-none
          ${isHighlighted ? 'bg-[#f0f0f0]' : 'bg-transparent hover:bg-black/[0.035]'}`}
      >
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors"
          style={{ background: isActive ? '#bbf7d0' : '#f0fdf4' }}
        >
          <Phone size={13} style={{ color: isActive ? '#15803d' : '#86efac' }} />
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          {renaming ? (
            <RenameInput initialValue={displayName} onSave={handleRename} onCancel={() => setRenaming(false)} />
          ) : (
            <div className="flex items-center gap-1 min-w-0 w-full">
              <StatusDot status={status} />
              <div className="flex-1 min-w-0 overflow-hidden" style={{ maskImage: FADE_MASK, WebkitMaskImage: FADE_MASK }}>
                <span className={`text-[12.5px] font-semibold leading-tight whitespace-nowrap ${isHighlighted ? 'text-[#1a1a1a]' : 'text-[#444]'}`}>
                  {displayName}
                </span>
              </div>
              <button
                onMouseDown={e => { e.stopPropagation(); e.preventDefault(); setRenaming(true); }}
                className="opacity-0 group-hover/item:opacity-100 flex-shrink-0 p-0.5 rounded hover:bg-black/[0.08] text-[#bbb] hover:text-[#555] transition-all border-none bg-transparent cursor-pointer"
              >
                <Pencil size={10} />
              </button>
            </div>
          )}
          <span className="text-[11px] text-[#777] mt-0.5">{formatDateShort(call.created_at)}</span>
          {preview && !renaming && (
            <span className="text-[11.5px] text-[#555] mt-1 leading-[1.45] line-clamp-2 pr-1">{preview}</span>
          )}
        </div>
      </button>
    </div>
  );
}

// ── Email item ────────────────────────────────────────────────────────────────

function EmailItem({ email, isActive, isKeyFocused, onSelect, onContextMenu, buttonRef }) {
  const isHighlighted = isActive || isKeyFocused;
  return (
    <div className="relative">
      {isActive && (
        <div className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-[#6366f1]" />
      )}
      <button
        ref={buttonRef}
        onClick={() => onSelect(email.id)}
        onContextMenu={e => { e.preventDefault(); onContextMenu(e, email.id, 'email'); }}
        className={`w-full text-left flex items-start gap-2 pl-3 pr-2 py-2.5 rounded-xl border-none cursor-pointer transition-colors font-inherit focus:outline-none
          ${isHighlighted ? 'bg-[#f0f0f0]' : 'bg-transparent hover:bg-black/[0.035]'}`}
      >
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
          style={{ background: isActive ? '#e0e7ff' : '#eef2ff' }}
        >
          <Mail size={13} style={{ color: isActive ? '#4338ca' : '#a5b4fc' }} />
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          <div className="flex items-center gap-1 min-w-0 w-full">
            <div className="flex-1 min-w-0 overflow-hidden" style={{ maskImage: FADE_MASK, WebkitMaskImage: FADE_MASK }}>
              <span className={`text-[12.5px] font-semibold leading-tight whitespace-nowrap ${isHighlighted ? 'text-[#1a1a1a]' : 'text-[#444]'}`}>
                {email.subject || '(No subject)'}
              </span>
            </div>
            {email.message_count > 1 && (
              <span className="text-[10.5px] text-[#bbb] flex-shrink-0 font-medium tabular-nums">{email.message_count}</span>
            )}
          </div>
          <span className="text-[11px] text-[#777] mt-0.5">{formatDateShort(email.thread_date)}</span>
          {email.snippet && (
            <span className="text-[11.5px] text-[#555] mt-1 leading-[1.45] line-clamp-2 pr-1">{email.snippet}</span>
          )}
        </div>
      </button>
    </div>
  );
}

// ── Session item ──────────────────────────────────────────────────────────────

function SessionItem({ session, isActive, isKeyFocused, onSelect, onContextMenu, buttonRef }) {
  const isHighlighted = isActive || isKeyFocused;
  return (
    <div className="relative">
      {isActive && (
        <div className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-[#f59e0b]" />
      )}
      <button
        ref={buttonRef}
        onClick={() => onSelect(session.id)}
        onContextMenu={e => { e.preventDefault(); onContextMenu(e, session.id, 'session'); }}
        className={`w-full text-left flex items-start gap-2 pl-3 pr-2 py-2.5 rounded-xl border-none cursor-pointer transition-colors font-inherit focus:outline-none
          ${isHighlighted ? 'bg-[#f0f0f0]' : 'bg-transparent hover:bg-black/[0.035]'}`}
      >
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
          style={{ background: isActive ? '#fef3c7' : '#fffbeb' }}
        >
          <NotebookPen size={13} style={{ color: isActive ? '#d97706' : '#fcd34d' }} />
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          <div className="flex-1 min-w-0 overflow-hidden" style={{ maskImage: FADE_MASK, WebkitMaskImage: FADE_MASK }}>
            <span className={`text-[12.5px] font-semibold leading-tight whitespace-nowrap ${isHighlighted ? 'text-[#1a1a1a]' : 'text-[#444]'}`}>
              Call notes
            </span>
          </div>
          <span className="text-[11px] text-[#777] mt-0.5">{formatDateShort(session.started_at)}</span>
        </div>
      </button>
    </div>
  );
}

// ── RecordSidebar ─────────────────────────────────────────────────────────────

export default function RecordSidebar({
  calls, emails = [], sessions = [],
  activeKey, onSelect, onUpload, onRenameCall,
  archivedIds = new Set(), deletedIds = new Set(), onArchive = () => {}, onDelete = () => {},
}) {
  const [search, setSearch] = useState('');
  const [keyFocusedId, setKeyFocusedId] = useState(null);
  const [showArchived, setShowArchived] = useState(false);
  const [menu, setMenu] = useState(null); // { x, y, id, type }
  const buttonRefs = useRef({});
  const isOverview = activeKey === 'overview';

  const closeMenu = useCallback(() => setMenu(null), []);

  // Esc closes archived panel (if no context menu open)
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key !== 'Escape') return;
      if (menu) return; // let context menu handle it
      if (showArchived) { e.stopPropagation(); setShowArchived(false); }
    }
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [menu, showArchived]);

  function openContextMenu(e, id, type) {
    // Clamp to viewport
    const x = Math.min(e.clientX, window.innerWidth - 160);
    const y = Math.min(e.clientY, window.innerHeight - 120);
    setMenu({ x, y, id, type });
  }

  function menuOptions(id, type) {
    const opts = [
      {
        label: 'Archive',
        icon: <Archive size={13} />,
        action: () => onArchive(id),
      },
    ];
    // Only sessions (unlinked call notes) can be deleted
    if (type === 'session') {
      opts.push({
        label: 'Delete',
        icon: <Trash2 size={13} />,
        danger: true,
        action: () => onDelete(id),
      });
    }
    return opts;
  }

  const allItems = normalizeItems(calls, emails, sessions, archivedIds, deletedIds, false);
  const filtered = search.trim()
    ? allItems.filter(item => item.name.toLowerCase().includes(search.toLowerCase()))
    : allItems;
  const groups = groupByMonthAndDay(filtered);

  const archivedAll = normalizeItems(calls, emails, sessions, archivedIds, deletedIds, true);

  function handleKeyNav(e) {
    if (!['ArrowDown', 'ArrowUp', 'Enter'].includes(e.key)) return;
    e.preventDefault();
    const ids = filtered.map(item => item.id);
    if (ids.length === 0) return;
    if (e.key === 'Enter' && keyFocusedId) { onSelect(keyFocusedId); return; }
    const curr = ids.indexOf(keyFocusedId ?? activeKey);
    const next = e.key === 'ArrowDown'
      ? (curr < ids.length - 1 ? curr + 1 : 0)
      : (curr > 0 ? curr - 1 : ids.length - 1);
    const nextId = ids[next];
    setKeyFocusedId(nextId);
    buttonRefs.current[nextId]?.scrollIntoView({ block: 'nearest' });
  }

  return (
    <>
      <div
        className="flex flex-col flex-shrink-0 h-full overflow-hidden rounded-[10px] bg-white focus:outline-none"
        style={{ width: '280px', boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.05)' }}
        tabIndex={-1}
        onKeyDown={handleKeyNav}
        onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget)) setKeyFocusedId(null); }}
      >
        {/* Overview */}
        <div className="pt-2 pb-1 px-1 flex-shrink-0">
          <div className="relative">
            {isOverview && <div className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-[#4a6cf7]" />}
            <button
              onClick={() => onSelect('overview')}
              className={`w-full text-left flex items-center gap-2.5 pl-3 pr-2 py-2 rounded-xl border-none cursor-pointer transition-colors font-inherit focus:outline-none
                ${isOverview ? 'bg-[#f0f0f0]' : 'bg-transparent hover:bg-black/[0.035]'}`}
            >
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: isOverview ? '#eef1ff' : '#f5f5f5' }}>
                <LayoutGrid size={13} style={{ color: isOverview ? '#4a6cf7' : '#ccc' }} />
              </div>
              <span className={`text-[12.5px] font-semibold leading-tight ${isOverview ? 'text-[#1a1a1a]' : 'text-[#555]'}`}>
                Overview
              </span>
            </button>
          </div>
        </div>

        {/* Timeline header */}
        <div className="flex-shrink-0 border-t border-[#f2f2f2] px-4 pt-3 pb-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.09em] text-[#ccc]">Timeline</span>
        </div>

        {/* Search + Archived button */}
        <div className="px-2 pb-2 flex-shrink-0 flex flex-col gap-1.5">
          <div className="flex items-center gap-2 bg-[#f5f5f5] rounded-lg px-2.5 py-1.5">
            <Search size={11} className="text-[#c5c5c5] flex-shrink-0" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search…"
              className="flex-1 min-w-0 text-[12px] bg-transparent border-none outline-none placeholder-[#d0d0d0] text-[#333] font-inherit"
            />
            {search && (
              <button onClick={() => setSearch('')} className="text-[#bbb] hover:text-[#666] border-none bg-transparent cursor-pointer p-0 leading-none flex-shrink-0">
                <X size={10} />
              </button>
            )}
          </div>
          {archivedAll.length > 0 && (
            <button
              onClick={() => setShowArchived(true)}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11.5px] font-medium text-[#999] hover:text-[#555] hover:bg-[#f5f5f5] border-none bg-transparent cursor-pointer font-inherit transition-colors"
            >
              <Archive size={11} className="flex-shrink-0" />
              Archived
              <span className="ml-auto text-[10.5px] tabular-nums text-[#c0c0c0]">{archivedAll.length}</span>
            </button>
          )}
        </div>

        {/* Timeline list OR Archived panel */}
        {showArchived ? (
          <div className="flex flex-col flex-1 min-h-0">
            {/* Panel header */}
            <div className="flex-shrink-0 px-2 pb-2">
              <button
                onClick={() => setShowArchived(false)}
                className="flex items-center gap-1.5 text-[12px] font-medium text-[#888] hover:text-[#333] border-none bg-transparent cursor-pointer font-inherit transition-colors p-0"
              >
                <ChevronLeft size={14} />
                Back
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto px-1">
              {archivedAll.length === 0 ? (
                <div className="px-4 py-4 text-[12px] text-[#ccc] text-center">Nothing archived.</div>
              ) : (
                <div className="flex flex-col gap-px">
                  {archivedAll.map(item => (
                    <div key={item.id} className="flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-black/[0.03] group/archived">
                      {item.type === 'call'
                        ? <Phone size={12} className="text-[#ccc] flex-shrink-0" />
                        : item.type === 'email'
                        ? <Mail size={12} className="text-[#ccc] flex-shrink-0" />
                        : <NotebookPen size={12} className="text-[#ccc] flex-shrink-0" />}
                      <span className="flex-1 min-w-0 text-[12px] text-[#888] overflow-hidden whitespace-nowrap truncate">{item.name}</span>
                      <button
                        onClick={() => onArchive(item.id)}
                        className="opacity-0 group-hover/archived:opacity-100 text-[11px] text-[#4a6cf7] hover:text-[#2a4cd7] border-none bg-transparent cursor-pointer transition-all font-inherit px-0 whitespace-nowrap"
                      >
                        Restore
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
        <div className="flex flex-col flex-1 min-h-0 overflow-y-auto px-1">
          {calls.length === 0 && emails.length === 0 && sessions.length === 0 ? (
            <div className="px-4 py-6 text-[12px] text-[#ccc] text-center leading-relaxed">
              No activity yet.<br />
              <span className="text-[11px]">Upload a transcript to get started.</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="px-4 py-4 text-[12px] text-[#ccc] text-center">No results.</div>
          ) : (
            groups.map(group => (
              <div key={group.monthLabel} className="mb-1">
                {/* Month header */}
                <div className="px-3 pt-3 pb-1">
                  <span className="text-[10px] font-bold uppercase tracking-[0.09em] text-[#999]">{group.monthLabel}</span>
                </div>
                {group.days.map(day => (
                  <div key={day.dayLabel}>
                    {/* Day header */}
                    <div className="px-3 pt-1.5 pb-0.5">
                      <span className="text-[11px] font-semibold text-[#555]">{day.dayLabel}</span>
                    </div>
                    <div className="flex flex-col gap-px">
                  {day.items.map(item =>
                    item.type === 'call' ? (
                      <CallItem
                        key={item.id}
                        call={item.raw}
                        isActive={activeKey === item.id}
                        isKeyFocused={keyFocusedId === item.id}
                        onSelect={id => { setKeyFocusedId(null); onSelect(id); }}
                        onRename={onRenameCall}
                        onContextMenu={openContextMenu}
                        buttonRef={el => { buttonRefs.current[item.id] = el; }}
                      />
                    ) : item.type === 'email' ? (
                      <EmailItem
                        key={item.id}
                        email={item.raw}
                        isActive={activeKey === item.id}
                        isKeyFocused={keyFocusedId === item.id}
                        onSelect={id => { setKeyFocusedId(null); onSelect(id); }}
                        onContextMenu={openContextMenu}
                        buttonRef={el => { buttonRefs.current[item.id] = el; }}
                      />
                    ) : (
                      <SessionItem
                        key={item.id}
                        session={item.raw}
                        isActive={activeKey === item.id}
                        isKeyFocused={keyFocusedId === item.id}
                        onSelect={id => { setKeyFocusedId(null); onSelect(id); }}
                        onContextMenu={openContextMenu}
                        buttonRef={el => { buttonRefs.current[item.id] = el; }}
                      />
                    )
                  )}
                    </div>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
        )}

        {/* Upload button */}
        {onUpload && (
          <div className="flex-shrink-0 px-2 py-2 border-t border-[#f2f2f2]">
            <button
              onClick={onUpload}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-[12px] font-medium text-[#888] hover:text-[#333] border border-dashed border-[#e0e0e0] hover:border-[#bbb] hover:bg-[#fafafa] transition-all cursor-pointer bg-transparent font-inherit"
            >
              <Upload size={12} />
              Upload transcript
            </button>
          </div>
        )}
      </div>

      {/* Context menu portal */}
      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          options={menuOptions(menu.id, menu.type)}
          onClose={closeMenu}
        />
      )}
    </>
  );
}
