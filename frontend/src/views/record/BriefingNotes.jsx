import NotesEditor from './NotesEditor';

const SECTION_CONFIG = {
  summary:        { label: 'Summary',    dot: '#4a6cf7' },
  key_items:      { label: 'Key Items',  dot: '#f59e0b' },
  action_items:   { label: 'Next Steps', dot: '#22c55e' },
  attendee_notes: { label: 'Attendees',  dot: '#a78bfa' },
};

export default function BriefingNotes({ briefing }) {
  if (!briefing) return null;

  const sections = ['summary', 'key_items', 'action_items', 'attendee_notes']
    .map(key => ({ key, content: briefing[key], ...SECTION_CONFIG[key] }))
    .filter(s => s.content);

  if (sections.length === 0) return null;

  return (
    <div className="flex flex-col gap-5">
      {sections.map(section => (
        <div
          key={section.key}
          className="rounded-[10px] overflow-hidden"
          style={{ boxShadow: '0 0 0 1px rgba(0,0,0,0.06)' }}
        >
          {/* Section header */}
          <div
            className="flex items-center gap-2.5 px-4 py-2.5 border-b"
            style={{ background: '#fafafa', borderColor: 'rgba(0,0,0,0.06)' }}
          >
            <div
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ background: section.dot }}
            />
            <span className="text-[12px] font-semibold text-[#555] tracking-[-0.01em]">
              {section.label}
            </span>
          </div>

          {/* Content */}
          <div className="px-4 py-4 bg-white">
            <NotesEditor markdown={section.content} />
          </div>
        </div>
      ))}
    </div>
  );
}
