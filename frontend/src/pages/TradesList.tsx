import { useState, useEffect, useCallback } from "react";
import { api, type ImportedTrade, type TradeSummary } from "../api/client";
import { fmtMoney, pnlClass } from "../utils/format";
import { useDebounce } from "../hooks/useDebounce";
import StatsBar from "../components/StatsBar";
import OpenPositions from "../components/OpenPositions";

const SIDES = ["All", "Long", "Short"] as const;
const TYPES = ["All", "Stock", "Option", "Future"] as const;
const PAGE_SIZE = 100;

export default function TradesList() {
  const [trades, setTrades] = useState<ImportedTrade[]>([]);
  const [summary, setSummary] = useState<TradeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sideFilter, setSideFilter] = useState<string>("All");
  const [typeFilter, setTypeFilter] = useState<string>("All");
  const [sortBy, setSortBy] = useState("date");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(0);

  const debouncedSearch = useDebounce(search);

  useEffect(() => setPage(0), [debouncedSearch, sideFilter, typeFilter]);

  const loadTrades = useCallback(() => {
    setLoading(true);
    api.getImportedTrades({
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      search: debouncedSearch || undefined,
      side: sideFilter === "All" ? undefined : sideFilter.toLowerCase(),
      tradeType: typeFilter === "All" ? undefined : typeFilter,
      sortBy,
      sortDir,
    }).then(setTrades).catch(console.error).finally(() => setLoading(false));
  }, [debouncedSearch, sideFilter, typeFilter, sortBy, sortDir, page]);

  const loadSummary = useCallback(() => {
    api.getTradeSummary().then(setSummary).catch(console.error);
  }, []);

  useEffect(() => { loadTrades(); }, [loadTrades]);
  useEffect(() => { loadSummary(); }, [loadSummary]);

  const handlePositionsChanged = () => {
    loadSummary();
    loadTrades();
  };

  const toggleSort = (col: string) => {
    if (sortBy === col) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortBy(col); setSortDir("desc"); }
    setPage(0);
  };
  const sortIcon = (col: string) => (sortBy !== col ? " ⇅" : sortDir === "desc" ? " ↓" : " ↑");

  return (
    <div>
      {summary && (
        <div className="card">
          <StatsBar items={[
            { label: "Net Realized P&L", value: fmtMoney(summary.net_realized_pnl), className: pnlClass(summary.net_realized_pnl) },
            { label: "Open Trades", value: summary.open_trades },
            { label: "Logged Trades", value: summary.logged_trades },
            { label: "Win Rate", value: `${summary.win_rate}%` },
          ]} />
        </div>
      )}

      <OpenPositions onChanged={handlePositionsChanged} />

      <div className="card">
        <h2>All Trades</h2>
        <div className="trades-toolbar">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search symbol..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="filter-group">
            <span className="filter-label">Side</span>
            {SIDES.map((s) => (
              <button
                key={s}
                className={`btn ${sideFilter === s ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setSideFilter(s)}
              >
                {s}
              </button>
            ))}
          </div>
          <div className="filter-group">
            <span className="filter-label">Type</span>
            {TYPES.map((t) => (
              <button
                key={t}
                className={`btn ${typeFilter === t ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setTypeFilter(t)}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <p className="muted">Loading...</p>
        ) : trades.length === 0 ? (
          <p className="muted">No trades found.</p>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="sortable" onClick={() => toggleSort("date")}>Date{sortIcon("date")}</th>
                    <th>Symbol</th><th>Type</th><th>Side</th><th>Qty</th><th>Price</th>
                    <th>Proceeds</th><th>Commission</th>
                    <th className="sortable" onClick={() => toggleSort("pnl")}>Realized P&L{sortIcon("pnl")}</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((t) => (
                    <tr key={t.id}>
                      <td className="nowrap">{new Date(t.date_time).toLocaleString()}</td>
                      <td className="nowrap" style={{ fontWeight: 600 }}>{t.symbol}</td>
                      <td>{t.asset_category === "Stocks" ? "Stock" : "Option"}</td>
                      <td className={pnlClass(t.quantity)}>{t.quantity > 0 ? "BUY" : "SELL"}</td>
                      <td>{Math.abs(t.quantity)}</td>
                      <td>{fmtMoney(t.trade_price)}</td>
                      <td>{fmtMoney(t.proceeds)}</td>
                      <td className="text-red">{fmtMoney(t.commission)}</td>
                      <td className={pnlClass(t.realized_pnl)}>
                        {t.realized_pnl !== 0 ? fmtMoney(t.realized_pnl) : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "center" }}>
              <button className="btn btn-secondary" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
                Previous
              </button>
              <span className="muted" style={{ padding: "10px 16px" }}>Page {page + 1}</span>
              <button className="btn btn-secondary" onClick={() => setPage((p) => p + 1)} disabled={trades.length < PAGE_SIZE}>
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
