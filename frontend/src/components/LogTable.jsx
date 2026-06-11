export function LogTable({ logs }) {
  const sevColor = (s) => ({ OK: "text-green-600", Warning: "text-yellow-600", Critical: "text-red-600" }[s] ?? "text-gray-500");
  if (!logs.length) return <p className="text-sm text-gray-500">No log entries.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            {["Time", "Severity", "Message"].map((h) => (
              <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {logs.map((e) => (
            <tr key={e.id}>
              <td className="px-4 py-2 text-gray-400 whitespace-nowrap">{new Date(e.occurred_at).toLocaleString()}</td>
              <td className={`px-4 py-2 font-medium ${sevColor(e.severity)}`}>{e.severity}</td>
              <td className="px-4 py-2">{e.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
