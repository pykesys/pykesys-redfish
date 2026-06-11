export function HealthBadge({ health }) {
  const styles = {
    OK: "bg-green-100 text-green-800",
    Warning: "bg-yellow-100 text-yellow-800",
    Critical: "bg-red-100 text-red-800",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${styles[health] ?? "bg-gray-100 text-gray-600"}`}>
      {health ?? "Unknown"}
    </span>
  );
}
