import { useNavigate } from "react-router-dom";
import { HealthBadge } from "./HealthBadge";
import { PowerBadge } from "./PowerBadge";

const borderColor = (health) => ({
  OK: "border-green-400",
  Warning: "border-yellow-400",
  Critical: "border-red-500",
}[health] ?? "border-gray-300");

export function FleetGrid({ hosts }) {
  const navigate = useNavigate();
  if (!hosts.length) {
    return <p className="text-gray-500 text-sm mt-4">No hosts configured. Add one via the admin or API.</p>;
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {hosts.map((h) => {
        const snap = h.latest_snapshot;
        const health = snap?.health;
        return (
          <div
            key={h.id}
            onClick={() => navigate(`/hosts/${h.id}`)}
            className={`cursor-pointer border-l-4 ${borderColor(health)} bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">{h.display_name || h.host}</p>
                <p className="text-xs text-gray-400 truncate">{snap?.hostname || h.host}</p>
              </div>
              <HealthBadge health={health} />
            </div>
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <PowerBadge state={snap?.power_state} />
              <span className="text-xs text-gray-500 truncate">{snap?.model || "—"}</span>
            </div>
            <div className="mt-2 text-xs text-gray-400">
              {snap
                ? `Polled ${new Date(snap.polled_at).toLocaleTimeString()}`
                : h.last_error
                ? <span className="text-red-500 truncate block">{h.last_error}</span>
                : "Never polled"}
            </div>
          </div>
        );
      })}
    </div>
  );
}
