import { useEffect, useState } from "react";
import { getFleet, pollHost } from "../api";
import { FleetGrid } from "../components/FleetGrid";

export default function Dashboard() {
  const [hosts, setHosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const load = async () => {
    try {
      const data = await getFleet();
      setHosts(data);
      setLastRefresh(new Date());
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, []);

  const ok = hosts.filter((h) => h.latest_snapshot?.health === "OK").length;
  const warn = hosts.filter((h) => h.latest_snapshot?.health === "Warning").length;
  const crit = hosts.filter((h) => h.latest_snapshot?.health === "Critical").length;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Fleet Dashboard</h1>
        <div className="flex items-center gap-3 text-sm text-gray-500">
          {lastRefresh && <span>Refreshed {lastRefresh.toLocaleTimeString()}</span>}
          <button onClick={load} className="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-gray-700">Refresh</button>
        </div>
      </div>

      {/* Summary strip */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: "Total", value: hosts.length, color: "text-gray-900" },
          { label: "Healthy", value: ok, color: "text-green-600" },
          { label: "Warning", value: warn, color: "text-yellow-600" },
          { label: "Critical", value: crit, color: "text-red-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-lg shadow-sm p-4 text-center">
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
            <p className="text-xs text-gray-500 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {loading && <p className="text-gray-400 text-sm">Loading…</p>}
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {!loading && <FleetGrid hosts={hosts} />}
    </div>
  );
}
