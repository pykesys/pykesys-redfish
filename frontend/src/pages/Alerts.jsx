import { useEffect, useState } from "react";
import { getRules, createRule, deleteRule, getEvents, resolveEvent } from "../api";
import { HealthBadge } from "../components/HealthBadge";

const TABS = ["Rules", "Events"];

export default function Alerts() {
  const [tab, setTab] = useState("Rules");
  const [rules, setRules] = useState([]);
  const [events, setEvents] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", field: "health", operator: "eq", value: "Critical", severity: "critical", notify_slack_webhook: "" });
  const [msg, setMsg] = useState(null);

  const loadRules = () => getRules().then((d) => setRules(d.results ?? []));
  const loadEvents = () => getEvents().then((d) => setEvents(d.results ?? []));

  useEffect(() => {
    loadRules();
    loadEvents();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await createRule(form);
      await loadRules();
      setShowForm(false);
      setMsg("Rule created.");
    } catch (err) {
      setMsg(`Error: ${err.message}`);
    }
    setTimeout(() => setMsg(null), 4000);
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this rule?")) return;
    await deleteRule(id);
    await loadRules();
  };

  const handleResolve = async (id) => {
    await resolveEvent(id);
    await loadEvents();
  };

  const sevColor = (s) => ({ critical: "text-red-600", warning: "text-yellow-600" }[s] ?? "text-gray-500");

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Alerts</h1>

      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t}
              {t === "Events" && events.filter((e) => !e.resolved_at).length > 0 && (
                <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 text-xs bg-red-500 text-white rounded-full">
                  {events.filter((e) => !e.resolved_at).length}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {msg && <div className="mb-4 rounded bg-blue-50 border border-blue-200 px-4 py-2 text-sm text-blue-700">{msg}</div>}

      {tab === "Rules" && (
        <div>
          <button
            onClick={() => setShowForm(!showForm)}
            className="mb-4 px-4 py-2 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700"
          >
            {showForm ? "Cancel" : "+ New Rule"}
          </button>

          {showForm && (
            <form onSubmit={handleCreate} className="bg-white shadow-sm rounded-lg p-4 mb-4 grid grid-cols-2 gap-3 max-w-xl">
              {[
                { label: "Name", key: "name", type: "text" },
                { label: "Value", key: "value", type: "text" },
                { label: "Slack Webhook (optional)", key: "notify_slack_webhook", type: "url" },
              ].map(({ label, key, type }) => (
                <label key={key} className="flex flex-col gap-1 text-sm">
                  {label}
                  <input
                    type={type}
                    value={form[key]}
                    onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                    className="border rounded px-2 py-1 text-sm"
                    required={key === "name"}
                  />
                </label>
              ))}
              {[
                { label: "Field", key: "field", opts: ["health", "power_state"] },
                { label: "Operator", key: "operator", opts: ["eq", "neq"] },
                { label: "Severity", key: "severity", opts: ["warning", "critical"] },
              ].map(({ label, key, opts }) => (
                <label key={key} className="flex flex-col gap-1 text-sm">
                  {label}
                  <select value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className="border rounded px-2 py-1 text-sm">
                    {opts.map((o) => <option key={o}>{o}</option>)}
                  </select>
                </label>
              ))}
              <div className="col-span-2">
                <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded text-sm hover:bg-indigo-700">Create Rule</button>
              </div>
            </form>
          )}

          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["Name", "Condition", "Severity", "Enabled", ""].map((h) => (
                    <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rules.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-2 font-medium">{r.name}</td>
                    <td className="px-4 py-2 text-gray-500">{r.field} {r.operator} <strong>{r.value}</strong></td>
                    <td className={`px-4 py-2 font-medium ${sevColor(r.severity)}`}>{r.severity}</td>
                    <td className="px-4 py-2">{r.enabled ? "Yes" : "No"}</td>
                    <td className="px-4 py-2">
                      <button onClick={() => handleDelete(r.id)} className="text-xs text-red-500 hover:text-red-700">Delete</button>
                    </td>
                  </tr>
                ))}
                {!rules.length && (
                  <tr><td colSpan={5} className="px-4 py-4 text-center text-gray-400">No rules defined.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "Events" && (
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["Time", "Rule", "Host", "Severity", "Message", "Status", ""].map((h) => (
                  <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {events.map((e) => (
                <tr key={e.id} className={e.resolved_at ? "opacity-50" : ""}>
                  <td className="px-4 py-2 text-gray-400 whitespace-nowrap">{new Date(e.triggered_at).toLocaleString()}</td>
                  <td className="px-4 py-2 font-medium">{e.rule_name}</td>
                  <td className="px-4 py-2 text-gray-500">{e.host_display}</td>
                  <td className={`px-4 py-2 font-medium ${sevColor(e.rule_severity)}`}>{e.rule_severity}</td>
                  <td className="px-4 py-2 text-gray-600 max-w-xs truncate">{e.message}</td>
                  <td className="px-4 py-2">
                    {e.resolved_at ? (
                      <span className="text-green-600 text-xs">Resolved</span>
                    ) : (
                      <span className="text-red-600 text-xs font-medium">Open</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    {!e.resolved_at && (
                      <button onClick={() => handleResolve(e.id)} className="text-xs text-indigo-600 hover:text-indigo-800">Resolve</button>
                    )}
                  </td>
                </tr>
              ))}
              {!events.length && (
                <tr><td colSpan={7} className="px-4 py-4 text-center text-gray-400">No alert events.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
