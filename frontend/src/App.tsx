import { NavLink, Route, Routes } from "react-router-dom";
import AgentChat from "./pages/AgentChat";
import GraphExplorer from "./pages/GraphExplorer";
import EntityDashboard from "./pages/EntityDashboard";
import GovernanceDashboard from "./pages/GovernanceDashboard";
import CareerDashboard from "./pages/CareerDashboard";
import TraineeList from "./pages/TraineeList";
import ConnectorMarketplace from "./pages/ConnectorMarketplace";
import PipelineBuilder from "./pages/PipelineBuilder";

const navSections = [
  {
    title: "CareerForge",
    items: [
      { to: "/", label: "Dashboard" },
      { to: "/trainees", label: "Trainees" },
    ],
  },
  {
    title: "Engine",
    items: [
      { to: "/chat", label: "Agent Chat" },
      { to: "/graph", label: "Graph" },
      { to: "/entities", label: "Entities" },
      { to: "/connectors", label: "Connectors" },
      { to: "/pipelines", label: "Pipelines" },
      { to: "/governance", label: "Governance" },
    ],
  },
];

export default function App() {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <nav className="w-56 shrink-0 border-r border-gray-200 bg-white flex flex-col">
        <div className="px-4 py-5 font-bold text-lg tracking-tight">
          <span className="text-brand-700">Career</span>
          <span className="text-gray-400">Forge</span>
        </div>
        <div className="flex-1 overflow-y-auto px-2 space-y-4">
          {navSections.map((section) => (
            <div key={section.title}>
              <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-gray-300">
                {section.title}
              </p>
              <ul className="space-y-0.5">
                {section.items.map(({ to, label }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      end={to === "/"}
                      className={({ isActive }) =>
                        `block rounded-md px-3 py-2 text-sm font-medium transition ${
                          isActive
                            ? "bg-brand-50 text-brand-700"
                            : "text-gray-600 hover:bg-gray-100"
                        }`
                      }
                    >
                      {label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="border-t border-gray-200 px-4 py-3 text-xs text-gray-400">
          v0.1.0 &middot; Sprint 1
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<CareerDashboard />} />
          <Route path="/trainees" element={<TraineeList />} />
          <Route path="/chat" element={<AgentChat />} />
          <Route path="/graph" element={<GraphExplorer />} />
          <Route path="/entities" element={<EntityDashboard />} />
          <Route path="/connectors" element={<ConnectorMarketplace />} />
          <Route path="/pipelines" element={<PipelineBuilder />} />
          <Route path="/governance" element={<GovernanceDashboard />} />
        </Routes>
      </main>
    </div>
  );
}
