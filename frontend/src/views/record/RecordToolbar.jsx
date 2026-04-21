import { useState } from 'react';
import { Archive } from 'lucide-react';
import { formatDate } from '../../api/index';

export default function RecordToolbar({ call, transcriptOpen, onToggleTranscript, onArchive }) {
  const briefing = call.briefing || {};
  const [attendees, setAttendees] = useState(briefing.attendees || '');

  const rawName = call.transcript_name || call.id || 'Untitled Call';
  const title = rawName.replace(/^\d{6,8}[_\s]+/, '').replace(/_/g, ' ').trim() || rawName;
  const date = formatDate(call.created_at);

  return (
    <div className="flex items-start justify-between px-6 py-4 flex-shrink-0 border-b border-[#f0f0f0] bg-white">
      <div>
        <div className="text-[18px] font-bold text-[#1a1a1a] tracking-[-0.02em] leading-tight">
          {title}
        </div>
        {date && (
          <div className="text-[12px] text-[#999] mt-0.5">{date}</div>
        )}
        {attendees && (
          <div className="text-[12px] text-[#999] mt-0.5 flex items-baseline gap-1">
            <span className="flex-shrink-0">Attendees:</span>
            <span
              contentEditable
              suppressContentEditableWarning
              onBlur={e => setAttendees(e.currentTarget.textContent)}
              className="outline-none cursor-text rounded px-1 -mx-1
                hover:bg-black/[0.04] hover:text-[#666]
                focus:bg-[#f5f5f5] focus:text-[#333]
                transition-colors"
            >
              {attendees}
            </span>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 flex-shrink-0 mt-0.5">
        {onArchive && (
          <button
            onClick={onArchive}
            className="flex items-center gap-1.5 text-[12.5px] font-medium px-3 py-[6px] rounded-lg border border-[#e0e0e0] bg-white text-[#555] hover:border-[#bbb] cursor-pointer transition-colors font-inherit"
          >
            <Archive size={12} />
            Archive
          </button>
        )}
<button
          onClick={onToggleTranscript}
          className={`text-[13px] font-medium px-3 py-[6px] rounded-lg border cursor-pointer transition-colors font-inherit
            ${transcriptOpen
              ? 'bg-[#1a1a1a] text-white border-[#1a1a1a]'
              : 'bg-white text-[#555] border-[#e0e0e0] hover:border-[#bbb]'}`}
        >
          {transcriptOpen ? 'Hide Transcript' : 'View Transcript'}
        </button>
      </div>
    </div>
  );
}
