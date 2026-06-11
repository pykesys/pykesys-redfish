export function SensorTable({ sensors }) {
  const statusColor = (s) => ({ OK: "text-green-600", Warning: "text-yellow-600", Critical: "text-red-600" }[s] ?? "text-gray-500");
  if (!sensors.length) return <p className="text-sm text-gray-500">No sensor data available.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            {["Sensor", "Reading", "Unit", "Status", "Critical Threshold"].map((h) => (
              <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {sensors.map((s) => (
            <tr key={s.id}>
              <td className="px-4 py-2 font-medium">{s.name}</td>
              <td className="px-4 py-2">{s.reading ?? "—"}</td>
              <td className="px-4 py-2 text-gray-500">{s.unit || "—"}</td>
              <td className={`px-4 py-2 font-medium ${statusColor(s.status)}`}>{s.status || "—"}</td>
              <td className="px-4 py-2 text-gray-500">{s.upper_threshold_critical ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
