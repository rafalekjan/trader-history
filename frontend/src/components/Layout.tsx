import { NavLink, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="app-layout">
      <nav className="sidebar">
        <h1>Trader History</h1>
        <NavLink to="/import" className={({ isActive }) => (isActive ? "active" : "")}>
          Import CSV
        </NavLink>
        <NavLink to="/trades" className={({ isActive }) => (isActive ? "active" : "")}>
          Trades
        </NavLink>
        <NavLink to="/calendar" className={({ isActive }) => (isActive ? "active" : "")}>
          P&L Calendar
        </NavLink>
        <NavLink to="/analysis" className={({ isActive }) => (isActive ? "active" : "")}>
          Analysis
        </NavLink>
      </nav>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
