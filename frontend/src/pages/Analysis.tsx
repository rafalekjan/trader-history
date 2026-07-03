import { useState, useEffect, useMemo } from "react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine,
} from "recharts";
import { api, type CumulativePnLPoint, type FullStats, type DepositsResponse } from "../api/client";
import { fmtMoney, pnlClass } from "../utils/format";
import StatsBar from "../components/StatsBar";

const RANGES = ["MTD", "YTD", "1M", "3M", "6M", "1Y", "ALL"] as const;
type Range = (typeof RANGES)[number];

function getStartDate(range: Range): string | null {
  const now = new Date();
  switch (range) {
    case "MTD": return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
    case "YTD": return `${now.getFullYear()}-01-01`;
    case "ALL": return null;
    default: {
      const d = new Date(now);
      if (range === "1Y") d.setFullYear(d.getFullYear() - 1);
      else d.setMonth(d.getMonth() - parseInt(range, 10));
      return d.toISOString().slice(0, 10);
    }
  }
}

const round2 = (n: number) => Math.round(n * 100) / 100;

export default function Analysis() {
  const [allData, setAllData] = useState<CumulativePnLPoint[]>([]);
  const [stats, setStats] = useState<FullStats | null>(null);
  const [deposits, setDeposits] = useState<DepositsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<Range>("ALL");

  useEffect(() => {
    Promise.all([api.getCumulativePnL(), api.getDeposits()])
      .then(([c, d]) => { setAllData(c); setDeposits(d); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // Stats follow the selected chart range.
  useEffect(() => {
    api.getFullStats(getStartDate(range) ?? undefined).then(setStats).catch(console.error);
  }, [range]);

  const chartData = useMemo(() => {
    const start = getStartDate(range);
    if (!start) return allData;
    const filtered = allData.filter((d) => d.date >= start);
    if (filtered.length === 0) return filtered;
    // Re-baseline so the curve starts at 0 for the selected window.
    const base = filtered[0].cumulative_pnl - filtered[0].daily_pnl;
    return filtered.map((d) => ({ ...d, cumulative_pnl: round2(d.cumulative_pnl - base) }));
  }, [allData, range]);

  const current = chartData.length > 0 ? chartData[chartData.length - 1].cumulative_pnl : 0;
  const chartColor = current >= 0 ? "#3fb950" : "#f85149";

  if (loading) return <div className="card"><p className="muted">Loading...</p></div>;

  return (
    <div>
      {stats && (
        <div className="card">
          <StatsBar items={[
            { label: "Net Realized P&L", value: fmtMoney(stats.net_realized_pnl), className: pnlClass(stats.net_realized_pnl) },
            { label: "Win Rate", value: `${stats.win_rate}%` },
            { label: "Closed Trades", value: stats.closed_trades },
            { label: "Profit Factor", value: stats.profit_factor },
          ]} />
        </div>
      )}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>Cumulative P&L</h2>
          <div className="range-bar">
            {RANGES.map((r) => (
              <button key={r} className={`range-btn ${range === r ? "range-active" : ""}`} onClick={() => setRange(r)}>
                {r}
              </button>
            ))}
          </div>
        </div>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColor} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8b949e" }} tickFormatter={(v: string) => v.slice(5)} stroke="#30363d" />
              <YAxis tick={{ fontSize: 11, fill: "#8b949e" }} tickFormatter={(v: number) => `$${v}`} stroke="#30363d" />
              <Tooltip
                contentStyle={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 6, color: "#e2e8f0" }}
                formatter={(value: number, name: string) => [fmtMoney(value), name === "cumulative_pnl" ? "Cumulative P&L" : "Daily P&L"]}
                labelFormatter={(l: string) => `Date: ${l}`}
              />
              <ReferenceLine y={0} stroke="#484f58" strokeDasharray="3 3" />
              <Area type="monotone" dataKey="cumulative_pnl" stroke={chartColor} fill="url(#colorPnl)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="muted">No data for selected range.</p>
        )}
      </div>

      {stats && (
        <div className="card">
          <h2>Trade Statistics</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <span className="stat-label">Average Win</span>
              <span className="stat-value text-green">{fmtMoney(stats.avg_win)}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Average Loss</span>
              <span className="stat-value text-red">{fmtMoney(stats.avg_loss)}</span>
            </div>
            {stats.best_trade && (
              <div className="stat-card">
                <span className="stat-label">Best Trade</span>
                <span className="stat-value text-green">{fmtMoney(stats.best_trade.pnl)}</span>
                <span className="stat-sub">{stats.best_trade.symbol}</span>
              </div>
            )}
            {stats.worst_trade && (
              <div className="stat-card">
                <span className="stat-label">Worst Trade</span>
                <span className="stat-value text-red">{fmtMoney(stats.worst_trade.pnl)}</span>
                <span className="stat-sub">{stats.worst_trade.symbol}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {deposits && deposits.deposits.length > 0 && (
        <div className="card">
          <h2>Deposits & Transfers</h2>
          <StatsBar
            style={{ marginBottom: 16 }}
            items={[
              ...Object.entries(deposits.total_native).map(([cur, amt]) => ({
                label: `Total ${cur}`,
                value: cur === "USD" ? fmtMoney(amt) : `${amt.toFixed(2)} ${cur}`,
              })),
              { label: "Total (USD)", value: fmtMoney(deposits.total_usd) },
            ]}
          />
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr><th>Date</th><th>Description</th><th>Currency</th><th>Amount</th></tr>
              </thead>
              <tbody>
                {deposits.deposits.map((d, i) => (
                  <tr key={i}>
                    <td className="nowrap">{d.settle_date}</td>
                    <td>{d.description}</td>
                    <td>{d.currency}</td>
                    <td>{d.amount.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
