import { NavLink, Route, Routes } from "react-router-dom";
import AgentChat from "./pages/AgentChat";
import GraphExplorer from "./pages/GraphExplorer";
import EntityDashboard from "./pages/EntityDashboard";
import GovernanceDashboard from "./pages/GovernanceDashboard";
import ConnectorMarketplace from "./pages/ConnectorMarketplace";
import PipelineBuilder from "./pages/PipelineBuilder";
import AgentBuilder from "./pages/AgentBuilder";
import QualityStudio from "./pages/QualityStudio";
import { mountedApps, type MountedApp } from "./apps";

const platformApp: MountedApp = {
  id: "platform",
  title: "Engine",
  nav: {
    title: "Engine",
    items: [
      { to: "/chat", label: "Agent Chat" },
      { to: "/graph", label: "Graph" },
      { to: "/entities", label: "Entities" },
      { to: "/connectors", label: "Connectors" },
      { to: "/pipelines", label: "Pipelines" },
      { to: "/agents", label: "Agent Builder" },
      { to: "/quality", label: "Quality Studio" },
      { to: "/governance", label: "Governance" },
    ],
  },
  routes: [
    { path: "/chat", element: <AgentChat /> },
    { path: "/graph", element: <GraphExplorer /> },
    { path: "/entities", element: <EntityDashboard /> },
    { path: "/connectors", element: <ConnectorMarketplace /> },
    { path: "/pipelines", element: <PipelineBuilder /> },
    { path: "/agents", element: <AgentBuilder /> },
    { path: "/quality", element: <QualityStudio /> },
    { path: "/governance", element: <GovernanceDashboard /> },
  ],
};

const allApps: MountedApp[] = [...mountedApps, platformApp];

export default function App() {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <nav className="w-56 shrink-0 border-r border-gray-200 bg-white flex flex-col">
        <div className="px-4 py-5 font-bold text-lg tracking-tight">
          <span className="text-brand-700">Context</span>
          <span className="text-gray-400">Forge</span>
        </div>
        <div className="flex-1 overflow-y-auto px-2 space-y-4">
          {allApps.map((app) => (
            <div key={app.id}>
              <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-gray-300">
                {app.nav.title}
              </p>
              <ul className="space-y-0.5">
                {app.nav.items.map(({ to, label }) => (
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
          {allApps.flatMap((app) =>
            app.routes.map((r) => (
              <Route key={`${app.id}:${r.path}`} path={r.path} element={r.element} />
            )),
          )}
        </Routes>
      </main>
    </div>
  );
}
