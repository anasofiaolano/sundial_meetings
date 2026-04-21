import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Phone, Users, ArrowRight, Command } from 'lucide-react';
import { fetchAllCalls, fetchClients, formatDateShort } from '../api/index';

function formatCallName(raw) {
  if (!raw) return 'Untitled';
  return raw.replace(/^\d{6,8}[_\s]+/, '').replace(/_/g, ' ').trim() || raw;
}

function highlight(text, query) {
  if (!query) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-[#fef08a] text-inherit rounded-sm px-0">{text.slice(idx, idx + query.length)}</mark>
      {text.slice(idx + query.length)}
    </>
  );
}

export default function CommandPalette({ open, onClose }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [calls, setCalls] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  // Load data when opened
  useEffect(() => {
    if (!open) return;
    setQuery('');
    setSelectedIdx(0);
    setLoading(true);
    Promise.all([fetchAllCalls(), fetchClients()])
      .then(([allCalls, allClients]) => {
        setCalls(allCalls);
        setClients(allClients);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  // Build client lookup
  const clientMap = Object.fromEntries(clients.map(c => [c.id, c.name]));

  // Filter calls
  const q = query.trim().toLowerCase();
  const filtered = calls
    .filter(c => {
      const name = formatCallName(c.transcript_name).toLowerCase();
      const client = (clientMap[c.client_id] || '').toLowerCase();
      return !q || name.includes(q) || client.includes(q);
    })
    .slice(0, 12);

  // Clamp selectedIdx
  useEffect(() => {
    setSelectedIdx(i => Math.min(i, Math.max(filtered.length - 1, 0)));
  }, [filtered.length]);

  // Scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.children[selectedIdx];
    el?.scrollIntoView({ block: 'nearest' });
  }, [selectedIdx]);

  function handleSelect(call) {
    onClose();
    navigate(`/client/${call.client_id}`, { state: { openCallId: call.id } });
  }

  function handleKey(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx(i => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[selectedIdx]) {
      handleSelect(filtered[selectedIdx]);
    } else if (e.key === 'Escape') {
      onClose();
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[9990] flex items-start justify-center pt-[15vh]"
      style={{ background: 'rgba(0,0,0,0.35)', backdropFilter: 'blur(4px)' }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-[560px] rounded-[14px] overflow-hidden flex flex-col"
        style={{ background: '#fff', boxShadow: '0 24px 60px rgba(0,0,0,0.22), 0 0 0 1px rgba(0,0,0,0.08)' }}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[#f0f0f0]">
          <Search size={16} className="text-[#bbb] flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => { setQuery(e.target.value); setSelectedIdx(0); }}
            onKeyDown={handleKey}
            placeholder="Search calls across all clients…"
            className="flex-1 text-[14px] text-[#1a1a1a] border-none outline-none bg-transparent placeholder-[#ccc] font-inherit"
          />
          <kbd className="text-[10px] text-[#bbb] border border-[#e8e8e8] rounded px-1.5 py-0.5 font-inherit bg-[#fafafa] flex-shrink-0">
            esc
          </kbd>
        </div>

        {/* Results */}
        <div className="overflow-y-auto max-h-[360px]" ref={listRef}>
          {loading ? (
            <div className="py-8 text-center text-[13px] text-[#bbb]">Loading…</div>
          ) : filtered.length === 0 ? (
            <div className="py-8 text-center text-[13px] text-[#bbb]">
              {q ? 'No calls matched.' : 'No calls yet.'}
            </div>
          ) : (
            filtered.map((call, idx) => {
              const name = formatCallName(call.transcript_name);
              const clientName = clientMap[call.client_id] || '';
              const isSelected = idx === selectedIdx;
              return (
                <button
                  key={call.id}
                  onMouseDown={() => handleSelect(call)}
                  onMouseEnter={() => setSelectedIdx(idx)}
                  className={`w-full text-left flex items-center gap-3 px-4 py-2.5 border-none cursor-pointer font-inherit transition-colors
                    ${isSelected ? 'bg-[#f5f5f5]' : 'bg-transparent'}`}
                >
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ background: isSelected ? '#bbf7d0' : '#f0fdf4' }}
                  >
                    <Phone size={13} style={{ color: isSelected ? '#15803d' : '#86efac' }} />
                  </div>
                  <div className="flex flex-col min-w-0 flex-1">
                    <span className="text-[13px] font-medium text-[#1a1a1a] truncate">
                      {highlight(name, query)}
                    </span>
                    <span className="text-[11.5px] text-[#aaa]">
                      {highlight(clientName, query)}
                      {call.created_at && <> · {formatDateShort(call.created_at)}</>}
                    </span>
                  </div>
                  {isSelected && <ArrowRight size={13} className="text-[#bbb] flex-shrink-0" />}
                </button>
              );
            })
          )}
        </div>

        {/* Footer hint */}
        <div className="flex items-center gap-3 px-4 py-2.5 border-t border-[#f5f5f5] bg-[#fafafa]">
          <span className="text-[11px] text-[#bbb] flex items-center gap-1">
            <kbd className="border border-[#e8e8e8] rounded px-1 py-0.5 bg-white text-[10px]">↑↓</kbd> navigate
          </span>
          <span className="text-[11px] text-[#bbb] flex items-center gap-1">
            <kbd className="border border-[#e8e8e8] rounded px-1 py-0.5 bg-white text-[10px]">↵</kbd> open
          </span>
          <span className="text-[11px] text-[#bbb] flex items-center gap-1">
            <kbd className="border border-[#e8e8e8] rounded px-1 py-0.5 bg-white text-[10px]">esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}
