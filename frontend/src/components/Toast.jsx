import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { CheckCircle, XCircle, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

let _toastId = 0;

const ICONS = {
  success: <CheckCircle size={15} className="text-[#16a34a] flex-shrink-0" />,
  error:   <XCircle    size={15} className="text-[#dc2626] flex-shrink-0" />,
  info:    <Info       size={15} className="text-[#4a6cf7] flex-shrink-0" />,
};

function ToastItem({ toast, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(toast.id), toast.duration ?? 4000);
    return () => clearTimeout(t);
  }, [toast.id, toast.duration, onDismiss]);

  return (
    <div
      className="flex items-center gap-2.5 px-3.5 py-2.5 bg-white rounded-[10px] text-[13px] text-[#1a1a1a] font-medium max-w-[360px] animate-slide-up"
      style={{ boxShadow: '0 4px 20px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.06)' }}
    >
      {ICONS[toast.type] ?? ICONS.info}
      <span className="flex-1 leading-snug">{toast.message}</span>

      {toast.action && (
        <>
          <div className="w-px h-4 bg-[#e8e8e8] flex-shrink-0" />
          <button
            onClick={() => { toast.action.onClick(); onDismiss(toast.id); }}
            className="flex-shrink-0 text-[#4a6cf7] hover:text-[#2a4cd7] border-none bg-transparent cursor-pointer p-0 leading-none transition-colors font-medium font-inherit text-[13px] whitespace-nowrap"
          >
            {toast.action.label}
          </button>
        </>
      )}

      <button
        onClick={() => onDismiss(toast.id)}
        className="flex-shrink-0 text-[#ccc] hover:text-[#888] border-none bg-transparent cursor-pointer p-0 leading-none transition-colors ml-0.5"
      >
        <X size={13} />
      </button>
    </div>
  );
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const toastsRef = useRef(toasts);
  toastsRef.current = toasts;

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Esc dismisses the newest toast
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key !== 'Escape') return;
      const current = toastsRef.current;
      if (current.length > 0) {
        dismiss(current[current.length - 1].id);
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [dismiss]);

  // addToast(message, type?, options?)
  // options: { duration?, action: { label, onClick } }
  // Backward-compat: 3rd arg can be a plain number (duration)
  const addToast = useCallback((message, type = 'info', optionsOrDuration, action) => {
    const id = ++_toastId;
    let duration, resolvedAction;
    if (typeof optionsOrDuration === 'number') {
      duration = optionsOrDuration;
      resolvedAction = action;
    } else if (optionsOrDuration && typeof optionsOrDuration === 'object') {
      duration = optionsOrDuration.duration;
      resolvedAction = optionsOrDuration.action;
    }
    setToasts(prev => [...prev, { id, message, type, duration, action: resolvedAction }]);
    return id;
  }, []);

  const dismissToast = useCallback((id) => dismiss(id), [dismiss]);

  return (
    <ToastContext.Provider value={{ addToast, dismiss: dismissToast }}>
      {children}
      <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-2 items-center pointer-events-none">
        {toasts.map(t => (
          <div key={t.id} className="pointer-events-auto">
            <ToastItem toast={t} onDismiss={dismiss} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  // Legacy callers expect addToast to be the function directly
  // New callers can destructure { addToast, dismiss }
  if (!ctx) {
    const noop = () => {};
    noop.addToast = noop;
    noop.dismiss  = noop;
    return noop;
  }
  // Return addToast as the callable, with dismiss attached
  const fn = ctx.addToast;
  fn.dismiss = ctx.dismiss;
  return fn;
}
