import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import CommandPalette from '../components/CommandPalette';

export default function RootLayout() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    function onKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setPaletteOpen(o => !o);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#f5f4f0]">
      <Outlet context={{ openPalette: () => setPaletteOpen(true) }} />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
