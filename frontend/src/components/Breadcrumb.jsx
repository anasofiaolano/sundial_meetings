import { useNavigate } from 'react-router-dom';

export default function Breadcrumb({ items }) {
  const navigate = useNavigate();

  return (
    <div className="flex items-center gap-1.5 text-[12px] text-[#aaa]">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span className="text-[#ccc]">›</span>}
          {item.to ? (
            <button
              onClick={() => navigate(item.to)}
              className="text-[#888] hover:text-[#1a1a1a] border-none bg-none cursor-pointer font-inherit text-[12px] p-0 hover:underline"
            >
              {item.label}
            </button>
          ) : (
            <span className="text-[#1a1a1a] font-medium">{item.label}</span>
          )}
        </span>
      ))}
    </div>
  );
}
