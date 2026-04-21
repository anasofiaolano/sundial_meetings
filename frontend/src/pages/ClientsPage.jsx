import { useState, useEffect } from 'react';
import LeftNav from '../components/sidebar/LeftNav';
import ClientsView from '../views/ClientsView';
import { fetchClients } from '../api/index';

export default function ClientsPage() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchClients()
      .then(setClients)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <LeftNav active="home" />
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[#aaa] text-[13px]">Loading…</div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center text-[#e55] text-[13px]">{error}</div>
      ) : (
        <ClientsView clients={clients} />
      )}
    </>
  );
}
