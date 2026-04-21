import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CheckCircle, AlertCircle, Loader, Trash2 } from 'lucide-react';
import Breadcrumb from '../components/Breadcrumb';

const API = 'http://localhost:3004';

// ── Provider logos ────────────────────────────────────────────────────────────

function GoogleLogo() {
  return (
    <svg viewBox="0 0 24 24" className="w-5 h-5">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

function OutlookLogo() {
  return (
    <svg viewBox="0 0 24 24" className="w-5 h-5">
      <rect x="1" y="5" width="14" height="14" rx="2" fill="#0078D4"/>
      <rect x="8" y="1" width="15" height="15" rx="2" fill="#28A8E8"/>
      <rect x="8" y="8" width="15" height="8" rx="0" fill="#0078D4"/>
      <rect x="8" y="8" width="15" height="1" fill="#50D9FF" opacity="0.4"/>
      <text x="10.5" y="20" fontSize="7" fontWeight="bold" fill="white" fontFamily="sans-serif">M</text>
    </svg>
  );
}

function ElevateLogo() {
  return (
    <div className="w-5 h-5 rounded-full bg-[#f59e0b] flex items-center justify-center">
      <span className="text-[9px] font-bold text-white">E</span>
    </div>
  );
}

// ── Provider config ───────────────────────────────────────────────────────────

const PROVIDERS = [
  {
    key:         'google',
    label:       'Gmail',
    logo:        <GoogleLogo />,
    description: 'Pull email threads into client records automatically.',
    available:   true,
  },
  {
    key:         'microsoft',
    label:       'Outlook',
    logo:        <OutlookLogo />,
    description: 'Connect your Outlook or Microsoft 365 account.',
    available:   false, // coming soon
  },
  {
    key:         'elevate',
    label:       'Elevate',
    logo:        <ElevateLogo />,
    description: 'Phone calls and SMS via Elevate.',
    available:   false, // coming soon
  },
];

// ── Sub-components ────────────────────────────────────────────────────────────

function HealthDot({ status }) {
  if (status === 'active') {
    return <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a] flex-shrink-0" />;
  }
  return <span className="w-1.5 h-1.5 rounded-full bg-[#dc2626] flex-shrink-0" />;
}

function ConnectedRow({ provider, account, onDisconnect, disconnecting }) {
  const isBusy = disconnecting === account.id;
  return (
    <div className="flex items-center gap-4 px-5 py-4">
      {/* Logo */}
      <div className="w-9 h-9 rounded-lg bg-[#f5f5f5] flex items-center justify-center flex-shrink-0">
        {provider.logo}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-[13px] font-semibold text-[#1a1a1a]">{provider.label}</span>
          <HealthDot status={account.status} />
          <span className={`text-[11px] font-medium ${account.status === 'active' ? 'text-[#16a34a]' : 'text-[#dc2626]'}`}>
            {account.status === 'active' ? 'Connected' : 'Reconnect needed'}
          </span>
        </div>
        <div className="text-[12px] text-[#888] truncate">{account.email_address}</div>
        <div className="text-[11px] text-[#bbb] mt-0.5">
          Connected {new Date(account.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
        </div>
      </div>

      {/* Disconnect */}
      <button
        onClick={() => onDisconnect(account)}
        disabled={isBusy}
        className="flex items-center gap-1.5 text-[12px] font-medium text-[#999] hover:text-[#dc2626] border border-[#e8e8e8] hover:border-[#fca5a5] px-3 py-1.5 rounded-lg cursor-pointer bg-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed font-inherit flex-shrink-0"
      >
        {isBusy ? <Loader size={11} className="animate-spin" /> : <Trash2 size={11} />}
        Disconnect
      </button>
    </div>
  );
}

function UnconnectedRow({ provider, onConnect }) {
  return (
    <div className="flex items-center gap-4 px-5 py-4">
      {/* Logo */}
      <div className="w-9 h-9 rounded-lg bg-[#f5f5f5] flex items-center justify-center flex-shrink-0 opacity-60">
        {provider.logo}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-semibold text-[#1a1a1a] mb-0.5">{provider.label}</div>
        <div className="text-[12px] text-[#bbb]">{provider.description}</div>
      </div>

      {/* CTA */}
      {provider.available ? (
        <button
          onClick={() => onConnect(provider.key)}
          className="text-[12px] font-semibold text-white bg-[#1a1a1a] hover:bg-[#333] px-3.5 py-1.5 rounded-lg cursor-pointer border-none transition-colors font-inherit flex-shrink-0"
        >
          Connect →
        </button>
      ) : (
        <span className="text-[11px] font-medium text-[#ccc] bg-[#f5f5f5] px-2.5 py-1 rounded-full flex-shrink-0">
          Coming soon
        </span>
      )}
    </div>
  );
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function Toast({ toast }) {
  if (!toast) return null;
  return (
    <div
      className={`fixed bottom-5 left-1/2 -translate-x-1/2 flex items-center gap-2 px-4 py-2.5 rounded-xl text-[13px] font-medium shadow-lg animate-slide-up z-50 whitespace-nowrap
        ${toast.type === 'success' ? 'bg-[#1a1a1a] text-white' : 'bg-[#dc2626] text-white'}`}
    >
      {toast.type === 'success'
        ? <CheckCircle size={14} />
        : <AlertCircle size={14} />
      }
      {toast.message}
    </div>
  );
}

// ── SettingsView ──────────────────────────────────────────────────────────────

export default function SettingsView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [accounts, setAccounts]         = useState([]);
  const [loading, setLoading]           = useState(true);
  const [toast, setToast]               = useState(null);
  const [disconnecting, setDisconnecting] = useState(null);

  function showToast(message, type = 'success') {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  }

  async function loadAccounts() {
    try {
      const res  = await fetch(`${API}/api/email/accounts`);
      const data = await res.json();
      setAccounts(data);
    } catch {
      // non-critical
    } finally {
      setLoading(false);
    }
  }

  // Handle redirect back from OAuth
  useEffect(() => {
    const connected = searchParams.get('email_connected');
    const error     = searchParams.get('email_error');

    if (connected) {
      const label = connected === 'google' ? 'Gmail' : 'Outlook';
      showToast(`${label} connected successfully.`, 'success');
      setSearchParams({});
      loadAccounts();
    } else if (error) {
      const messages = {
        invalid_state:   'Connection failed — please try again.',
        scope_denied:    'Gmail access was not granted. Please allow email access when prompted.',
        exchange_failed: 'Connection failed — could not complete authorization.',
        access_denied:   'Connection cancelled.',
      };
      showToast(messages[error] || `Error: ${error}`, 'error');
      setSearchParams({});
    }
  }, []);

  useEffect(() => { loadAccounts(); }, []);

  async function disconnect(account) {
    setDisconnecting(account.id);
    try {
      await fetch(`${API}/api/email/accounts/${account.id}`, { method: 'DELETE' });
      setAccounts(prev => prev.filter(a => a.id !== account.id));
      const label = account.provider === 'google' ? 'Gmail' : 'Outlook';
      showToast(`${label} disconnected.`, 'success');
    } catch {
      showToast('Failed to disconnect — please try again.', 'error');
    } finally {
      setDisconnecting(null);
    }
  }

  function connect(providerKey) {
    window.location.href = `${API}/api/email/connect/${providerKey}`;
  }

  function accountFor(providerKey) {
    return accounts.find(a => a.provider === providerKey) || null;
  }

  return (
    <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">

      {/* Header */}
      <div className="flex-shrink-0 px-6 pt-4 pb-3 flex flex-col gap-2">
        <Breadcrumb items={[{ label: 'Home', to: '/' }, { label: 'Settings' }]} />
        <div className="text-[22px] font-bold text-[#1a1a1a] tracking-[-0.02em]">Settings</div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">
        <div className="max-w-[600px] flex flex-col gap-8 pt-2">

          {/* Connected accounts */}
          <section>
            <div className="text-[10px] font-semibold text-[#bbb] uppercase tracking-[0.06em] mb-3">
              Connected accounts
            </div>

            <div
              className="rounded-[10px] overflow-hidden bg-white divide-y divide-[#f0f0f0]"
              style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.05)' }}
            >
              {loading ? (
                <div className="flex items-center justify-center py-10 gap-2 text-[#bbb] text-[13px]">
                  <Loader size={13} className="animate-spin" />
                  Loading…
                </div>
              ) : (
                PROVIDERS.map(provider => {
                  const account = accountFor(provider.key);
                  return account ? (
                    <ConnectedRow
                      key={provider.key}
                      provider={provider}
                      account={account}
                      onDisconnect={disconnect}
                      disconnecting={disconnecting}
                    />
                  ) : (
                    <UnconnectedRow
                      key={provider.key}
                      provider={provider}
                      onConnect={connect}
                    />
                  );
                })
              )}
            </div>
          </section>

          {/* Briefings — placeholder for next iteration */}
          <section>
            <div className="text-[10px] font-semibold text-[#bbb] uppercase tracking-[0.06em] mb-3">
              Briefings
            </div>
            <div
              className="rounded-[10px] bg-white px-5 py-4"
              style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.05)' }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[13px] font-semibold text-[#1a1a1a] mb-0.5">Pre-call email</div>
                  <div className="text-[12px] text-[#bbb]">Send a briefing email before scheduled calls</div>
                </div>
                <span className="text-[11px] font-medium text-[#ccc] bg-[#f5f5f5] px-2.5 py-1 rounded-full flex-shrink-0">
                  Coming soon
                </span>
              </div>
            </div>
          </section>

        </div>
      </div>

      <Toast toast={toast} />
    </div>
  );
}
