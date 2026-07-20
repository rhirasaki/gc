import { NavLink, Route, Routes } from "react-router-dom";
import Studio from "./pages/Studio";
import Project from "./pages/Project";
import Templates from "./pages/Templates";
import Costs from "./pages/Costs";
import NewProject from "./pages/NewProject";
import Settings from "./pages/Settings";

const nav = [
  { to: "/", label: "Studio" },
  { to: "/templates", label: "Templates" },
  { to: "/costs", label: "Costs" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  return (
    <div className="min-h-screen flex">
      {/* Spine */}
      <aside className="w-52 shrink-0 border-r border-line bg-card flex flex-col">
        <div className="p-5 border-b border-line">
          <div className="eyebrow">The Bindery</div>
          <div className="display text-2xl leading-tight mt-1">
            Photo Book<br />Studio
          </div>
        </div>
        <nav className="p-3 flex flex-col gap-1">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `px-3 py-2 text-sm ${isActive ? "bg-press-soft text-press font-semibold" : "text-ink-2 hover:text-ink"}`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto p-5 mono text-[10px] text-ink-2 leading-relaxed">
          REG ◈ CMYK
          <br />
          10 × 10 in · trim
        </div>
      </aside>

      <main className="flex-1 p-8 max-w-6xl">
        <Routes>
          <Route path="/" element={<Studio />} />
          <Route path="/new" element={<NewProject />} />
          <Route path="/projects/:id" element={<Project />} />
          <Route path="/templates" element={<Templates />} />
          <Route path="/costs" element={<Costs />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
