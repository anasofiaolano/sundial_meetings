import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, X } from 'lucide-react';
import { fetchPreCallBrief, formatDate } from '../../api/index';

export default function PreCallBrief({ clientId, agendaItems, onAgendaChange }) {
  const [open, setOpen]             = useState(true);
  const [brief, setBrief]           = useState(null);
  const [agendaInput, setAgendaInput] = useState('');

  useEffect(() => {
    fetchPreCallBrief(clientId).then(setBrief).catch(() => {});
  }, [clientId]);

  function addAgendaItem(e) {
    if (e.key === 'Enter' && agendaInput.trim()) {
      onAgendaChange([...agendaItems, agendaInput.trim()]);
      setAgendaInput('');
    }
  }

  function removeAgendaItem(i) {
    onAgendaChange(agendaItems.filter((_, idx) => idx !== i));
  }

  const hasContent = brief?.last_call || agendaItems.length > 0;

  return (
    <div className="border-b border-[#f0f0f0]">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-1.5 px-3 py-2 text-left bg-transparent border-none cursor-pointer hover:bg-[#fafafa] transition-colors font-inherit"
      >
        {open
          ? <ChevronDown  size={11} className="text-[#bbb] flex-shrink-0" />
          : <ChevronRight size={11} className="text-[#bbb] flex-shrink-0" />}
        <span className="text-[11px] font-semibold text-[#aaa] uppercase tracking-wider">Pre-call brief</span>
        {!open && hasContent && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[#4a6cf7] flex-shrink-0" />}
      </button>

      {open && (
        <div className="px-3 pb-3 flex flex-col gap-2">
          {brief?.last_call && (
            <div className="text-[12px] text-[#666]">
              <span className="font-medium">Last call:</span>{' '}
              {formatDate(brief.last_call.date)}
              {brief.action_items?.length > 0 && (
                <span className="text-[#aaa]">
                  {' '}· {brief.action_items.length} open item{brief.action_items.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>
          )}

          {brief?.action_items?.length > 0 && (
            <div className="flex flex-col gap-0.5">
              {brief.action_items.map((item, i) => (
                <div key={i} className="text-[12px] text-[#888] flex items-start gap-1.5">
                  <span className="text-[#4a6cf7] font-bold text-[10px] mt-[2px]">A</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-col gap-0.5 mt-0.5">
            <div className="text-[11px] font-semibold text-[#aaa] uppercase tracking-wider mb-0.5">Agenda</div>
            {agendaItems.map((item, i) => (
              <div key={i} className="flex items-center gap-1.5 group/agenda">
                <span className="text-[#bbb] text-[10px]">·</span>
                <span className="text-[12px] text-[#555] flex-1">{item}</span>
                <button
                  onClick={() => removeAgendaItem(i)}
                  className="opacity-0 group-hover/agenda:opacity-100 text-[#ccc] hover:text-[#e55] bg-transparent border-none cursor-pointer p-0 transition-all"
                >
                  <X size={10} />
                </button>
              </div>
            ))}
            <input
              type="text"
              value={agendaInput}
              onChange={e => setAgendaInput(e.target.value)}
              onKeyDown={addAgendaItem}
              placeholder="+ Add agenda item"
              className="text-[12px] text-[#555] border-none bg-transparent outline-none placeholder-[#ccc] font-inherit py-0.5"
            />
          </div>

          {!brief?.last_call && agendaItems.length === 0 && (
            <div className="text-[12px] text-[#bbb]">No previous calls for this client.</div>
          )}
        </div>
      )}
    </div>
  );
}
