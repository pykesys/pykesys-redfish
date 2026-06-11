export function PowerBadge({ state }) {
  const styles = {
    On: "bg-green-100 text-green-800",
    Off: "bg-gray-100 text-gray-600",
    PoweringOn: "bg-blue-100 text-blue-700",
    PoweringOff: "bg-orange-100 text-orange-700",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${styles[state] ?? "bg-gray-100 text-gray-500"}`}>
      {state ?? "—"}
    </span>
  );
}
