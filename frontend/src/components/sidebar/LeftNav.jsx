import { useNavigate, useOutletContext } from 'react-router-dom';
import { Home, Settings, User, Search } from 'lucide-react';

const NAV_ITEMS = [
  { key: 'home',     icon: Home,     label: 'Home',     path: '/' },
  { key: 'settings', icon: Settings, label: 'Settings', path: '/settings' },
];

export default function LeftNav({ active }) {
  const navigate = useNavigate();
  let openPalette = null;
  try { ({ openPalette } = useOutletContext() ?? {}); } catch { /* outside context */ }

  return (
    <nav className="w-[196px] flex-shrink-0 bg-[#eceae3] flex flex-col px-3 py-4 border-r border-black/[0.05] h-screen overflow-hidden">

      {/* Logo */}
      <div className="text-[15px] font-bold tracking-[-0.02em] px-2 pb-4 select-none">
        Sun<span style={{ color: '#c8a97a' }}>dial</span>
      </div>

      {/* Search / Cmd+K shortcut */}
      <button
        onClick={() => openPalette?.()}
        className="flex items-center gap-2 px-2.5 py-1.5 mb-2 rounded-lg text-[12px] text-[#999] hover:text-[#555] hover:bg-black/[0.05] transition-colors border-none bg-transparent cursor-pointer font-inherit w-full text-left group"
      >
        <Search size={13} className="flex-shrink-0 text-[#bbb] group-hover:text-[#777] transition-colors" />
        <span className="flex-1">Search</span>
        <span className="text-[10px] text-[#c0c0c0] border border-[#d8d8d8] rounded px-1 py-0.5 bg-white/60 font-mono tracking-tight flex-shrink-0">
          ⌘K
        </span>
      </button>

      {/* Nav items */}
      <div className="flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ key, icon: Icon, label, path }) => (
          <button
            key={key}
            onClick={() => navigate(path)}
            className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[13px] font-medium transition-colors text-left w-full border-none cursor-pointer font-inherit
              ${active === key
                ? 'bg-white text-[#1a1a1a] shadow-sm'
                : 'text-[#777] hover:bg-black/[0.05] hover:text-[#1a1a1a] bg-transparent'
              }`}
          >
            <Icon size={14} className="flex-shrink-0" />
            {label}
          </button>
        ))}
      </div>

      {/* User at bottom */}
      <div className="mt-auto">
        <div className="h-px bg-black/[0.06] mb-2" />
        <button className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[13px] font-medium text-[#777] hover:bg-black/[0.05] hover:text-[#1a1a1a] transition-colors w-full border-none bg-transparent cursor-pointer font-inherit">
          <div className="w-5 h-5 rounded-full bg-[#d8d4cc] flex items-center justify-center flex-shrink-0">
            <span className="text-[9px] font-bold text-[#888]">JP</span>
          </div>
          Jay P.
        </button>
      </div>
    </nav>
  );
}
