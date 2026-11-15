import Session from "./Session";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import {
  AudioWaveform,
  LayoutDashboard,
  RadioTower,
  ShieldCheck,
  ArrowLeftRight,
  Server,
} from "lucide-react";
import SentinelOpsDashboard, {CommandBar} from "./SentinelOpsDashboard";
import "./command.css";
import { Incidents, Detail } from "./pages/Incidents";
import Approvals from "./pages/Approvals";
import Payflow from "./pages/Payflow";
import "./style.css";

const links = [
  { path: "/", name: "Overview", Icon: LayoutDashboard },
  { path: "/incidents", name: "Incidents", Icon: RadioTower },
  { path: "/approvals", name: "Approvals", Icon: ShieldCheck },
  { path: "/payflow", name: "PayFlow lab", Icon: ArrowLeftRight },
];
function App() {
  return (
    <div className="shell">
      <aside>
        <Link to="/" className="brand">
          <AudioWaveform />
          SentinelOps
        </Link>
        <nav aria-label="Workspace">
          {links.map(({ path, name, Icon }) => (
            <NavLink key={path} end={path === "/"} to={path}>
              <Icon size={18} />
              {name}
            </NavLink>
          ))}
        </nav>
        <div className="local" title="Local simulation">
          <Server size={17} />
          Local simulation
        </div>
      </aside>
      <main><CommandBar/>
        <div className="content">
          <Routes>
            <Route path="/" element={<SentinelOpsDashboard />} />
            <Route path="/incidents" element={<Incidents />} />
            <Route path="/incidents/:id" element={<Detail />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/payflow" element={<Payflow />} />
            <Route
              path="*"
              element={
                <Link to="/">Page unavailable. Return to overview.</Link>
              }
            />
          </Routes>
        </div>
        <footer>
          Local simulation. The audit trail records operator decisions and verified fault clearance.
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <Session>
      <App />
    </Session>
  </BrowserRouter>,
);
