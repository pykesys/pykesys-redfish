import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import HostDetail from "./pages/HostDetail";
import Alerts from "./pages/Alerts";

const navClass = ({ isActive }) =>
  `text-sm font-medium px-1 pb-1 border-b-2 ${isActive ? "border-white text-white" : "border-transparent text-blue-200 hover:text-white"}`;

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-blue-700 px-6 py-3 flex items-center gap-8 shadow">
          <span className="text-white font-bold text-base tracking-wide">Redfish Observability</span>
          <NavLink to="/" end className={navClass}>Dashboard</NavLink>
          <NavLink to="/alerts" className={navClass}>Alerts</NavLink>
        </nav>
        <main className="max-w-7xl mx-auto px-6 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/hosts/:id" element={<HostDetail />} />
            <Route path="/alerts" element={<Alerts />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
