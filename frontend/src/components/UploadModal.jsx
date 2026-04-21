import { useState, useEffect } from 'react';
import { Check, X, FileText, Cpu, Sparkles } from 'lucide-react';
import { fetchClients, uploadTranscript, fetchClientSessions } from '../api/index';

// ── Step indicator ────────────────────────────────────────────────────────────

const STEPS = [
  { key: 'upload',  icon: FileText, label: 'Uploading transcript' },
  { key: 'queue',   icon: Cpu,      label: 'Queued for processing' },
  { key: 'done',    icon: Sparkles, label: 'Ready' },
];

function StepRow({ icon: Icon, label, state }) {
  // state: 'pending' | 'active' | 'done'
  return (
    <div className="flex items-center gap-3">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 transition-colors
        ${state === 'done'   ? 'bg-[#dcfce7]' :
          state === 'active' ? 'bg-[#fef9c3]' :
          'bg-[#f5f5f5]'}`}
      >
        {state === 'done'
          ? <Check size={14} className="text-[#16a34a]" strokeWidth={2.5} />
          : <Icon size={14} className={state === 'active' ? 'text-[#ca8a04]' : 'text-[#ccc]'} />
        }
      </div>
      <span className={`text-[13px] transition-colors
        ${state === 'done'   ? 'text-[#16a34a] font-medium' :
          state === 'active' ? 'text-[#854d0e] font-medium' :
          'text-[#bbb]'}`}
      >
        {label}
      </span>
      {state === 'active' && (
        <div className="ml-auto flex gap-0.5">
          {[0,1,2].map(i => (
            <div key={i} className="w-1 h-1 rounded-full bg-[#f59e0b] animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
        </div>
      )}
    </div>
  );
}

function stepState(stepKey, currentStep) {
  const order = ['upload', 'queue', 'done'];
  const si = order.indexOf(stepKey);
  const ci = order.indexOf(currentStep);
  if (si < ci) return 'done';
  if (si === ci) return 'active';
  return 'pending';
}

// ── Indeterminate progress bar ────────────────────────────────────────────────

function ProgressBar({ active }) {
  return (
    <div className="h-[3px] bg-[#f0f0f0] rounded-full overflow-hidden">
      {active && (
        <div
          className="h-full w-1/3 rounded-full bg-[#4a6cf7] animate-progress"
          style={{ animationDuration: '1.6s' }}
        />
      )}
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────

export default function UploadModal({ defaultClientId, onClose, onSuccess }) {
  const [name, setName] = useState('');
  const [content, setContent] = useState('');
  const [clientId, setClientId] = useState(defaultClientId || '');
  const [callDate, setCallDate] = useState('');  // datetime-local string, optional
  const [clients, setClients] = useState([]);
  const [recentSession, setRecentSession] = useState(null);   // unlinked ended session for this client
  const [linkSession, setLinkSession] = useState(true);       // pre-checked
  const [sessionSkipped, setSessionSkipped] = useState(false);
  const [error, setError] = useState(null);

  // 'form' | 'upload' | 'queue' | 'done'
  const [step, setStep] = useState('form');

  useEffect(() => { fetchClients().then(setClients).catch(() => {}); }, []);

  // When clientId is set, look for a recent unlinked ended session
  useEffect(() => {
    if (!clientId || clientId === '__new__') { setRecentSession(null); return; }
    fetchClientSessions(clientId)
      .then(sessions => {
        const unlinked = sessions
          .filter(s => s.status === 'ended' && !s.job_id)
          .sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
        setRecentSession(unlinked[0] || null);
        setLinkSession(true);
        setSessionSkipped(false);
      })
      .catch(() => setRecentSession(null));
  }, [clientId]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim())    { setError('Call name is required.'); return; }
    if (!content.trim()) { setError('Transcript is required.'); return; }
    if (!clientId)       { setError('Please select a client.'); return; }

    setError(null);
    setStep('upload');

    // Convert datetime-local value to ISO string if provided
    const callDateIso = callDate ? new Date(callDate).toISOString() : null;
    const sessionId = (recentSession && linkSession && !sessionSkipped) ? recentSession.id : null;

    try {
      await uploadTranscript({ name: name.trim(), content: content.trim(), clientId, callDate: callDateIso, sessionId });
      setStep('queue');
      await new Promise(r => setTimeout(r, 600));
      setStep('done');
      onSuccess?.();
    } catch (err) {
      setStep('form');
      setError(err.message);
    }
  }

  const isSubmitting = step === 'upload' || step === 'queue';
  const isDone = step === 'done';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(2px)' }}
      onClick={e => { if (e.target === e.currentTarget && !isSubmitting) onClose(); }}
    >
      <div
        className="bg-white rounded-[14px] flex flex-col overflow-hidden"
        style={{ width: '500px', maxHeight: '90vh', boxShadow: '0 16px 60px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.06)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#f0f0f0] flex-shrink-0">
          <div className="text-[15px] font-bold text-[#1a1a1a] tracking-[-0.01em]">Add Transcript</div>
          {!isSubmitting && (
            <button onClick={onClose} className="text-[#ccc] hover:text-[#555] border-none bg-transparent cursor-pointer leading-none transition-colors p-1 rounded-md hover:bg-[#f5f5f5]">
              <X size={15} />
            </button>
          )}
        </div>

        {/* Progress bar — visible during upload */}
        <ProgressBar active={isSubmitting} />

        {/* Body */}
        {isDone ? (
          // ── Done state ────────────────────────────────────────────────────
          <div className="flex flex-col items-center justify-center gap-5 px-8 py-10">
            <div className="w-14 h-14 rounded-full bg-[#dcfce7] flex items-center justify-center">
              <Check size={26} className="text-[#16a34a]" strokeWidth={2.5} />
            </div>
            <div className="text-center">
              <div className="text-[16px] font-bold text-[#1a1a1a] mb-1.5">Transcript uploaded</div>
              <div className="text-[13px] text-[#aaa] leading-relaxed">
                It'll appear in the sidebar now while it processes.<br />
                Briefing is usually ready in ~60 seconds.
              </div>
            </div>
            <div className="flex gap-2 mt-1">
              <button
                onClick={onClose}
                className="text-[13px] font-medium px-5 py-2.5 rounded-lg border border-[#e0e0e0] bg-white text-[#555] hover:border-[#bbb] cursor-pointer transition-colors font-inherit"
              >
                Close
              </button>
              <button
                onClick={() => window.location.reload()}
                className="text-[13px] font-medium px-5 py-2.5 rounded-lg bg-[#1a1a1a] text-white cursor-pointer border-none transition-colors font-inherit hover:bg-[#333]"
              >
                Refresh now
              </button>
            </div>
          </div>
        ) : isSubmitting ? (
          // ── Progress state ────────────────────────────────────────────────
          <div className="flex flex-col gap-4 px-8 py-8">
            <div className="text-[13px] font-medium text-[#888] mb-1">Processing your transcript…</div>
            <div className="flex flex-col gap-4">
              {STEPS.map(s => (
                <StepRow key={s.key} icon={s.icon} label={s.label} state={stepState(s.key, step)} />
              ))}
            </div>
          </div>
        ) : (
          // ── Form state ────────────────────────────────────────────────────
          <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-y-auto">
            <div className="px-6 py-5 flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-[#444]">Call name</label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="e.g. Golden Eagle — Q2 Review"
                  className="text-[13px] border border-[#e0e0e0] rounded-lg px-3 py-2.5 outline-none focus:border-[#a0a0a0] placeholder-[#ccc] font-inherit transition-colors"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-[#444]">Client</label>
                <select
                  value={clientId}
                  onChange={e => { if (e.target.value !== '__new__') setClientId(e.target.value); }}
                  className="text-[13px] border border-[#e0e0e0] rounded-lg px-3 py-2.5 outline-none focus:border-[#a0a0a0] bg-white font-inherit cursor-pointer transition-colors"
                >
                  <option value="">Select a client…</option>
                  {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  <option value="__new__" disabled>New client… (coming soon)</option>
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-[#444]">
                  Call date & time
                  <span className="text-[11px] font-normal text-[#aaa] ml-1.5">optional — defaults to now</span>
                </label>
                <input
                  type="datetime-local"
                  value={callDate}
                  onChange={e => setCallDate(e.target.value)}
                  className="text-[13px] border border-[#e0e0e0] rounded-lg px-3 py-2.5 outline-none focus:border-[#a0a0a0] font-inherit transition-colors text-[#333]"
                />
              </div>

              {recentSession && !sessionSkipped && (
                <div className="flex items-start gap-3 bg-[#fffbeb] border border-[#fde68a] rounded-lg px-3 py-2.5">
                  <input
                    type="checkbox"
                    id="link-session"
                    checked={linkSession}
                    onChange={e => setLinkSession(e.target.checked)}
                    className="mt-0.5 flex-shrink-0 cursor-pointer"
                  />
                  <div className="flex-1 min-w-0">
                    <label htmlFor="link-session" className="text-[12.5px] font-medium text-[#92400e] cursor-pointer">
                      Include your call notes
                    </label>
                    <div className="text-[11.5px] text-[#b45309] mt-0.5">
                      Notes from today's session will be used by the AI when generating the briefing.
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSessionSkipped(true)}
                    className="text-[11px] text-[#d97706] hover:text-[#92400e] bg-transparent border-none cursor-pointer font-inherit flex-shrink-0 underline"
                  >
                    Skip for now
                  </button>
                </div>
              )}

              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-[#444]">Paste transcript</label>
                <textarea
                  value={content}
                  onChange={e => setContent(e.target.value)}
                  placeholder="Paste the full transcript text here…"
                  rows={8}
                  className="text-[13px] border border-[#e0e0e0] rounded-lg px-3 py-2.5 outline-none focus:border-[#a0a0a0] placeholder-[#ccc] resize-y font-inherit leading-[1.65] transition-colors"
                />
              </div>

              {error && (
                <div className="text-[12px] text-[#dc2626] bg-[#fef2f2] border border-[#fecaca] rounded-lg px-3 py-2.5">
                  {error}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-[#f0f0f0] flex-shrink-0">
              <button type="button" onClick={onClose}
                className="text-[13px] font-medium px-4 py-2 rounded-lg border border-[#e0e0e0] bg-white text-[#555] hover:border-[#bbb] cursor-pointer transition-colors font-inherit">
                Cancel
              </button>
              <button type="submit"
                className="text-[13px] font-medium px-4 py-2 rounded-lg bg-[#1a1a1a] text-white cursor-pointer border-none transition-colors font-inherit hover:bg-[#333]">
                Upload
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
