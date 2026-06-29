import { useState, useEffect, useMemo } from "react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine,
} from "recharts";
import { api, type CumulativePnLPoint, type FullStats, type DepositsResponse } from "../api/client";

const RANGES = [
  { key: "MTD", label: "MTD" },
  { key: "YTD", label: "YTD" },
  { key: "1M", label: "1M" },
  { key: "3M", label: "3M" },
  { key: "6M", label: "6M" },
  { key: "1Y", label: "1Y" },
  { key: "ALL", label: "ALL" },
];

function getStartDate(range: string): string | null {
  const now = new Date();
  switch (range) {
    case "MTD": return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
    case "YTD": return `${now.getFullYear()}-01-01`;
    case "1M": { const d = new Date(now); d.setMonth(d.getMonth() - 1); return d.toISOString().slice(0, 10); }
    case "3M": { const d = new Date(now); d.setMonth(d.getMonth() - 3); return d.toISOString().slice(0, 10); }
    case "6M": { const d = new Date(now); d.setMonth(d.getMonth() - 6); return d.toISOString().slice(0, 10); }
    case "1Y": { const d = new Date(now); d.setFullYear(d.getFullYear() - 1); return d.toISOString().slice(0, 10); }
    default: return null;
  }
}

function round(n: number) { return Math.round(n * 100) / 100; }

export default function Analysis() {
  const [allData, setAllData] = useState<CumulativePnLPoint[]>([]);
  const [stats, setStats] = useState<FullStats | null>(null);
  const [deposits, setDeposits] = useState<DepositsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState("ALL");

  useEffect(() => {
    Promise.all([api.getCumulativePnL(), api.getFullStats(), api.getDeposits()])
      .then(([c, s, d]) => { setAllData(c); setStats(s); setDeposits(d); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const start = getStartDate(range);
    api.getFullStats(start ?? undefined).then(setStats).catch(console.error);
  }, [range]);

  const chartData = useMemo(() => {
    const start = getStartDate(range);
    if (!start) return allData;
    const filtered = allData.filter(d => d.date >= start);
    if (filtered.length === 0) return filtered;
    const base = filtered[0].cumulative_pnl - filtered[0].daily_pnl;
    return filtered.map(d => ({ ...d, cumulative_pnl: round(d.cumulative_pnl - base) }));
  }, [allData, range]);

  const current = chartData.length > 0 ? chartData[chartData.length - 1].cumulative_pnl : 0;

  if (loading) return <div className="card"><p>Loading...</p></div>;

  return (
    <div>
      {stats && (
        <div className="card">
          <div className="stats-bar">
            <div className="stat"><span className="stat-label">Net Realized P&L</span><span className={`stat-value ${stats.net_realized_pnl >= 0 ? "text-green" : "text-red"}`}>${stats.net_realized_pnl.toFixed(2)}</span></div>
            <div className="stat"><span className="stat-label">Win Rate</span><span className="stat-value">{stats.win_rate}%</span></div>
            <div className="stat"><span className="stat-label">Closed Trades</span><span className="stat-value">{stats.closed_trades}</span></div>
            <div className="stat"><span className="stat-label">Profit Factor</span><span className="stat-value">{stats.profit_factor}</span></div>
          </div>
        </div>
      )}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>Cumulative P&L</h2>
          <div className="range-bar">
            {RANGES.map(r => (
              <button key={r.key} className={`range-btn ${range === r.key ? "range-active" : ""}`} onClick={() => setRange(r.key)}>{r.label}</button>
            ))}
          </div>
        </div>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={current >= 0 ? "#3fb950" : "#f85149"} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={current >= 0 ? "#3fb950" : "#f85149"} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8b949e" }} tickFormatter={(v: string) => v.slice(5)} stroke="#30363d" />
              <YAxis tick={{ fontSize: 11, fill: "#8b949e" }} tickFormatter={(v: number) => `$${v}`} stroke="#30363d" />
              <Tooltip contentStyle={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 6, color: "#e2e8f0" }}
                formatter={(value: number, name: string) => [`$${value.toFixed(2)}`, name === "cumulative_pnl" ? "Cumulative P&L" : "Daily P&L"]}
                labelFormatter={(l: string) => `Date: ${l}`} />
              <ReferenceLine y={0} stroke="#484f58" strokeDasharray="3 3" />
              <Area type="monotone" dataKey="cumulative_pnl" stroke={current >= 0 ? "#3fb950" : "#f85149"} fill="url(#colorPnl)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        ) : <p className="muted">No data for selected range.</p>}
      </div>

      {stats && (
        <div className="card">
          <h2>Trade Statistics</h2>
          <div className="stats-grid">
            <div className="stat-card"><span className="stat-label">Average Win</span><span className="stat-value text-green">${stats.avg_win.toFixed(2)}</span></div>
            <div className="stat-card"><span className="stat-label">Average Loss</span><span className="stat-value text-red">${stats.avg_loss.toFixed(2)}</span></div>
            {stats.best_trade && <div className="stat-card"><span className="stat-label">Best Trade</span><span className="stat-value text-green">${stats.best_trade.pnl.toFixed(2)}</span><span className="stat-sub">{stats.best_trade.symbol}</span></div>}
            {stats.worst_trade && <div className="stat-card"><span className="stat-label">Worst Trade</span><span className="stat-value text-red">${stats.worst_trade.pnl.toFixed(2)}</span><span className="stat-sub">{stats.worst_trade.symbol}</span></div>}
          </div>
        </div>
      )}

      {deposits && deposits.deposits.length > 0 && (
        <div className="card">
          <h2>Deposits & Transfers</h2>
          <div className="stats-bar" style={{ marginBottom: 16 }}>
            {Object.entries(deposits.total_native).map(([cur, amt]) => (
              <div className="stat" key={cur}><span className="stat-label">Total {cur}</span><span className="stat-value">{cur === "USD" ? "$" : ""}{amt.toFixed(2)} {cur !== "USD" ? cur : ""}</span></div>
            ))}
            <div className="stat"><span className="stat-label">Total (USD)</span><span className="stat-value">${deposits.total_usd.toFixed(2)}</span></div>
          </div>
          <div className="table-wrapper">
            <table className="data-table">
              <thead><tr><th>Date</th><th>Description</th><th>Currency</th><th>Amount</th></tr></thead>
              <tbody>
                {deposits.deposits.map((d, i) => (
                  <tr key={i}><td className="nowrap">{d.settle_date}</td><td>{d.description}</td><td>{d.currency}</td><td>{d.amount.toFixed(2)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
