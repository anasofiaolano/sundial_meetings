import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { formatDate } from '../api/index';

function initials(name) {
  if (!name) return '?';
  return name.split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
}

// Pastel avatar colors based on first char
const AVATAR_COLORS = [
  { bg: '#dbeafe', color: '#1d4ed8' },
  { bg: '#dcfce7', color: '#15803d' },
  { bg: '#ede9fe', color: '#6d28d9' },
  { bg: '#fce7f3', color: '#be185d' },
  { bg: '#ffedd5', color: '#c2410c' },
  { bg: '#fef9c3', color: '#a16207' },
];

function avatarColor(name) {
  const idx = (name?.charCodeAt(0) || 0) % AVATAR_COLORS.length;
  return AVATAR_COLORS[idx];
}

export default function ClientsView({ clients }) {
  const navigate = useNavigate();

  return (
    <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
      <div className="flex-1 overflow-y-auto px-8 py-8">

        <div className="mb-8">
          <div className="text-[24px] font-bold text-[#1a1a1a] tracking-[-0.03em]">Clients</div>
          <div className="text-[13px] text-[#aaa] mt-1">Your client notes and call records.</div>
        </div>

        {clients.length === 0 ? (
          <div className="text-[13px] text-[#bbb]">No clients yet.</div>
        ) : (
          <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
            {clients.map(client => {
              const av = avatarColor(client.name);
              return (
                <button
                  key={client.id}
                  onClick={() => navigate(`/client/${client.id}`)}
                  className="group text-left bg-white rounded-[12px] px-5 py-5 cursor-pointer border-none transition-all hover:-translate-y-[2px] hover:shadow-[0_4px_16px_rgba(0,0,0,0.10)]"
                  style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.05)' }}
                >
                  {/* Top row: avatar + arrow */}
                  <div className="flex items-start justify-between mb-3">
                    <div
                      className="w-10 h-10 rounded-[10px] flex items-center justify-center text-[14px] font-bold tracking-[-0.01em] flex-shrink-0"
                      style={{ background: av.bg, color: av.color }}
                    >
                      {initials(client.name)}
                    </div>
                    <ArrowRight
                      size={16}
                      className="text-[#ddd] group-hover:text-[#999] transition-colors mt-1 flex-shrink-0"
                    />
                  </div>

                  {/* Name */}
                  <div className="text-[16px] font-bold text-[#1a1a1a] tracking-[-0.02em] leading-tight">
                    {client.name}
                  </div>

                  {/* Last activity */}
                  {client.last_call_at ? (
                    <div className="text-[11.5px] text-[#aaa] mt-2">
                      Last call · {formatDate(client.last_call_at)}
                    </div>
                  ) : (
                    <div className="text-[11.5px] text-[#ccc] mt-2">No calls yet</div>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
