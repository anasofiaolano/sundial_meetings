import { Sparkles } from 'lucide-react';

export default function ChatRail({ onOpen }) {
  return (
    <div
      className="w-10 flex-shrink-0 flex flex-col items-center py-4 gap-3 group cursor-pointer"
      style={{
        background: '#fff',
        borderRadius: '10px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.05)',
      }}
      onClick={onOpen}
      title="Open AI copilot"
    >
      {/* Icon */}
      <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-[#f0f0f0] group-hover:bg-[#eef1ff] transition-colors flex-shrink-0">
        <Sparkles size={14} className="text-[#ccc] group-hover:text-[#4a6cf7] transition-colors" />
      </div>

      {/* Vertical label */}
      <span
        className="text-[10px] font-semibold text-[#ccc] group-hover:text-[#888] transition-colors tracking-[0.06em] uppercase select-none"
        style={{ writingMode: 'vertical-rl', textOrientation: 'mixed', transform: 'rotate(180deg)' }}
      >
        AI Chat
      </span>
    </div>
  );
}
