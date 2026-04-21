import { useRouteError } from 'react-router-dom';
import RootLayout from './layouts/RootLayout';
import ClientsPage from './pages/ClientsPage';
import RecordPage from './pages/RecordPage';
import SettingsPage from './pages/SettingsPage';

function ErrorPage() {
  const error = useRouteError();
  const message = error?.message || String(error) || 'Unknown error';
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#fafafa]">
      <div className="max-w-md w-full mx-4 bg-white rounded-2xl p-8 shadow-sm border border-[#f0f0f0] text-center">
        <div className="text-[32px] mb-3">⚠️</div>
        <div className="text-[17px] font-bold text-[#1a1a1a] mb-2">Something went wrong</div>
        <div className="text-[13px] text-[#888] leading-relaxed mb-6">
          The page ran into an unexpected error.
        </div>
        <details className="text-left mb-6">
          <summary className="text-[12px] text-[#bbb] cursor-pointer hover:text-[#888] transition-colors">
            Error details
          </summary>
          <pre className="mt-2 text-[11px] text-[#999] bg-[#f5f5f5] rounded-lg p-3 overflow-auto whitespace-pre-wrap break-all leading-relaxed">
            {message}
          </pre>
        </details>
        <button
          onClick={() => window.location.href = '/'}
          className="text-[13px] font-medium px-5 py-2.5 rounded-lg bg-[#1a1a1a] text-white border-none cursor-pointer hover:bg-[#333] transition-colors font-inherit"
        >
          Go home
        </button>
      </div>
    </div>
  );
}

export const createRouteConfig = (isMobile) => [
  {
    path: '/',
    element: <RootLayout />,
    errorElement: <ErrorPage />,
    children: [
      { index: true, element: <ClientsPage />, errorElement: <ErrorPage /> },
      { path: 'client/:clientId', element: <RecordPage />, errorElement: <ErrorPage /> },
      { path: 'settings', element: <SettingsPage />, errorElement: <ErrorPage /> },
    ],
  },
];
