import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getHost, getSensors, getLogs, powerAction, bootAction, pollHost } from "../api";
import { HealthBadge } from "../components/HealthBadge";
import { PowerBadge } from "../components/PowerBadge";
import { SensorTable } from "../components/SensorTable";
import { LogTable } from "../components/LogTable";

const TABS = ["Overview", "Sensors", "Logs", "Actions"];

export default function HostDetail() {
  const { id } = useParams();
  const [host, setHost] = useState(null);
  const [sensors, setSensors] = useState([]);
  const [logs, setLogs] = useState([]);
  const [tab, setTab] = useState("Overview");
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState(null);

  useEffect(() => {
    Promise.all([
      getHost(id),
      getSensors(id).then((d) => setSensors(d.results ?? [])),
      getLogs(id).then((d) => setLogs(d.results ?? [])),
    ])
      .then(([h]) => setHost(h))
      .finally(() => setLoading(false));
  }, [id]);

  const sendAction = async (fn, label) => {
    setActionMsg(`Sending ${label}…`);
    try {
      await fn();
      setActionMsg(`${label} sent.`);
    } catch (e) {
      setActionMsg(`Error: ${e.message}`);
    }
    setTimeout(() => setActionMsg(null), 4000);
  };

  if (loading) return <p className="text-gray-400 text-sm">Loading…</p>;
  if (!host) return <p className="text-red-500">Host not found.</p>;

  const snap = host.latest_snapshot;

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="text-xl font-bold text-gray-900">{host.display_name || host.host}</h1>
        {snap && <HealthBadge health={snap.health} />}
        {snap && <PowerBadge state={snap.power_state} />}
      </div>

      {/* Tabs */}
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
            </button>
          ))}
        </nav>
      </div>

      {tab === "Overview" && snap && (
        <dl className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[
            ["Hostname", snap.hostname],
            ["Model", snap.model],
            ["Manufacturer", snap.manufacturer],
            ["Serial", snap.serial_number],
            ["BIOS", snap.bios_version],
            ["RAM (GiB)", snap.total_memory_gib],
            ["CPUs", snap.processor_count],
            ["CPU Model", snap.processor_model],
          ].map(([label, val]) => (
            <div key={label} className="bg-white rounded-lg shadow-sm p-3">
              <dt className="text-xs text-gray-500">{label}</dt>
              <dd className="text-sm font-medium text-gray-900 mt-1">{val ?? "—"}</dd>
            </div>
          ))}
        </dl>
      )}

      {tab === "Sensors" && <SensorTable sensors={sensors} />}
      {tab === "Logs" && <LogTable logs={logs} />}

      {tab === "Actions" && (
        <div className="space-y-6 max-w-md">
          {actionMsg && (
            <div className="rounded bg-blue-50 border border-blue-200 px-4 py-2 text-sm text-blue-700">{actionMsg}</div>
          )}

          <section>
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Power</h2>
            <div className="flex flex-wrap gap-2">
              {[
                ["Power On", "On"],
                ["Graceful Shutdown", "GracefulShutdown"],
                ["Graceful Restart", "GracefulRestart"],
                ["Force Restart", "ForceRestart"],
                ["Force Off", "ForceOff"],
              ].map(([label, rt]) => (
                <button
                  key={rt}
                  onClick={() => sendAction(() => powerAction(id, rt), label)}
                  className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded border border-gray-200"
                >
                  {label}
                </button>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Boot Override (One-Time)</h2>
            <div className="flex flex-wrap gap-2">
              {["Pxe", "Usb", "Hdd", "Cd", "BiosSetup", "UefiShell"].map((target) => (
                <button
                  key={target}
                  onClick={() => sendAction(() => bootAction(id, target), `Boot → ${target}`)}
                  className="px-3 py-1.5 text-sm bg-blue-50 hover:bg-blue-100 rounded border border-blue-200"
                >
                  {target}
                </button>
              ))}
              <button
                onClick={() => sendAction(() => bootAction(id, "None", "Disabled"), "Clear Override")}
                className="px-3 py-1.5 text-sm bg-gray-50 hover:bg-gray-100 rounded border border-gray-200"
              >
                Clear Override
              </button>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Polling</h2>
            <button
              onClick={() => sendAction(() => pollHost(id), "Poll Now")}
              className="px-4 py-2 text-sm bg-indigo-50 hover:bg-indigo-100 rounded border border-indigo-200 text-indigo-700"
            >
              Poll Now
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
