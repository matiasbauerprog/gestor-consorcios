import { NavLink } from "react-router-dom";

// tabs: array de { path, label, end? }
// end=true en NavLink hace que el activo se evalúe con match exacto (evita que
// el tab "default" /gastos quede activo también cuando estás en /gastos/habituales).
export default function Tabs({ tabs }) {
  return (
    <nav className="tabs" aria-label="Subnavegación">
      {tabs.map((tab) => (
        <NavLink
          key={tab.path}
          to={tab.path}
          end={tab.end}
          className={({ isActive }) => (isActive ? "tab activo" : "tab")}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
