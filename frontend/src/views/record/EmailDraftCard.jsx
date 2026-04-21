import { useState } from 'react';
import { Copy, Check, Mail } from 'lucide-react';
import { useToast } from '../../components/Toast';

export default function EmailDraftCard({ emailDraft }) {
  const [copied, setCopied] = useState(false);
  const addToast = useToast();

  if (!emailDraft) return null;

  function handleCopy() {
    navigator.clipboard.writeText(emailDraft);
    setCopied(true);
    addToast('Email draft copied to clipboard', 'success');
    setTimeout(() => setCopied(false), 1800);
  }

  return (
    <div
      className="rounded-[10px] overflow-hidden"
      style={{ boxShadow: '0 0 0 1px rgba(0,0,0,0.06)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5 border-b"
        style={{ background: '#fafafa', borderColor: 'rgba(0,0,0,0.06)' }}
      >
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#4a6cf7] flex-shrink-0" />
          <span className="text-[12px] font-semibold text-[#555]">Follow-up email</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-[11.5px] font-medium text-[#aaa] hover:text-[#555] border-none bg-transparent cursor-pointer px-2 py-1 rounded-md hover:bg-[#f0f0f0] transition-colors font-inherit"
        >
          {copied
            ? <><Check size={12} className="text-[#16a34a]" /> Copied</>
            : <><Copy size={12} /> Copy</>
          }
        </button>
      </div>

      {/* Body */}
      <div className="px-4 py-4 bg-white">
        <div className="text-[13.5px] text-[#333] leading-[1.78] whitespace-pre-wrap font-[400]">
          {emailDraft}
        </div>
      </div>
    </div>
  );
}
