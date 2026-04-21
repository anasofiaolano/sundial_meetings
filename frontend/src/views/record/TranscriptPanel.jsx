import { X } from 'lucide-react';

export default function TranscriptPanel({ call, onClose }) {
  const text = call?.transcript_text;
  const rawName = call?.transcript_name || call?.id || 'Call';
  const title = rawName.replace(/^\d{6,8}[_\s]+/, '').replace(/_/g, ' ').trim() || rawName;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#f0f0f0] flex-shrink-0">
        <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#bbb]">Transcript</span>
        {onClose && (
          <button
            onClick={onClose}
            className="text-[#ccc] hover:text-[#666] border-none bg-transparent cursor-pointer p-1 rounded-md hover:bg-[#f5f5f5] transition-colors"
          >
            <X size={13} />
          </button>
        )}
      </div>
      {/* Content */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {text ? (
          <div className="transcript-prose whitespace-pre-wrap">{text}</div>
        ) : (
          <p className="text-[13px] text-[#ccc]">Transcript not available.</p>
        )}
      </div>
    </div>
  );
}
