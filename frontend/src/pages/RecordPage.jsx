import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import LeftNav from '../components/sidebar/LeftNav';
import RecordView from '../views/RecordView';
import { fetchClients, fetchCalls } from '../api/index';

export default function RecordPage() {
  const { clientId } = useParams();
  const [client, setClient] = useState(null);
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    setError(null);

    Promise.all([fetchClients(), fetchCalls(clientId)])
      .then(([clients, calls]) => {
        const found = clients.find(c => c.id === clientId);
        if (!found) throw new Error(`Client "${clientId}" not found`);
        setClient(found);
        setCalls(calls);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [clientId]);

  return (
    <>
      <LeftNav active="home" />
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[#aaa] text-[13px]">Loading…</div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center text-[#e55] text-[13px]">{error}</div>
      ) : (
        <RecordView client={client} calls={calls} />
      )}
    </>
  );
}
