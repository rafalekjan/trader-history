import { useState, useEffect, useCallback } from "react";
import { api, type ImportedTrade, type TradeSummary, type OpenPosition } from "../api/client";

const SIDES = ["All", "Long", "Short"] as const;
const TYPES = ["All", "Stock", "Option", "Future"] as const;
const PAGE_SIZE = 100;

export default function TradesList() {
  const [trades, setTrades] = useState<ImportedTrade[]>([]);
  const [summary, setSummary] = useState<TradeSummary | null>(null);
  const [openPositions, setOpenPositions] = useState<OpenPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sideFilter, setSideFilter] = useState<string>("All");
  const [typeFilter, setTypeFilter] = useState<string>("All");
  const [sortBy, setSortBy] = useState("date");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(0);

  const [editSymbol, setEditSymbol] = useState<string | null>(null);
  const [closeDate, setCloseDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [closePrice, setClosePrice] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [priceRefreshing, setPriceRefreshing] = useState(false);
  const [lastPriceUpdate, setLastPriceUpdate] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedSearch(search); setPage(0); }, 250);
    return () => clearTimeout(t);
  }, [search]);

  const loadTrades = useCallback(() => {
    setLoading(true);
    api.getImportedTrades({
      limit: PAGE_SIZE, offset: page * PAGE_SIZE,
      search: debouncedSearch || undefined,
      side: sideFilter === "All" ? undefined : sideFilter.toLowerCase(),
      tradeType: typeFilter === "All" ? undefined : typeFilter,
      sortBy, sortDir,
    }).then(setTrades).catch(console.error).finally(() => setLoading(false));
  }, [debouncedSearch, sideFilter, typeFilter, sortBy, sortDir, page]);

  const reload = () => {
    api.getTradeSummary().then(setSummary).catch(console.error);
    api.getOpenPositions().then(setOpenPositions).catch(console.error);
    loadTrades();
  };

  useEffect(() => { loadTrades(); }, [loadTrades]);
  useEffect(() => {
    api.getTradeSummary().then(setSummary);
    api.getOpenPositions().then(setOpenPositions);
    api.getPrices().then(r => setLastPriceUpdate(r.last_updated));
  }, []);

  const toggleSort = (col: string) => {
    if (sortBy === col) setSortDir(d => d === "desc" ? "asc" : "desc");
    else { setSortBy(col); setSortDir("desc"); }
    setPage(0);
  };
  const sortIcon = (col: string) => sortBy !== col ? " ⇅" : sortDir === "desc" ? " ↓" : " ↑";

  const handleClose = async (pos: OpenPosition) => {
    if (!closePrice) return;
    setActionLoading(true);
    try {
      await api.closePosition({
        symbol: pos.symbol, asset_category: pos.asset_category,
        close_price: parseFloat(closePrice), close_date: closeDate, quantity: pos.quantity,
      });
      setEditSymbol(null); setClosePrice(""); reload();
    } catch (e) { console.error(e); }
    finally { setActionLoading(false); }
  };

  const handleRefreshPrices = async () => {
    setPriceRefreshing(true);
    try {
      const r = await api.refreshPrices();
      setLastPriceUpdate(r.last_updated);
      api.getOpenPositions().then(setOpenPositions);
    } catch (e) { console.error(e); }
    finally { setPriceRefreshing(false); }
  };

  const handleDelete = async (symbol: string) => {
    if (!confirm(`Delete all trades for ${symbol}?`)) return;
    setActionLoading(true);
    try { await api.deleteBySymbol(symbol); setEditSymbol(null); reload(); }
    catch (e) { console.error(e); }
    finally { setActionLoading(false); }
  };

  return (
    <div>
      {summary && (
        <div className="card">
          <div className="stats-bar">
            <div className="stat"><span className="stat-label">Net Realized P&L</span><span className={`stat-value ${summary.net_realized_pnl >= 0 ? "text-green" : "text-red"}`}>${summary.net_realized_pnl.toFixed(2)}</span></div>
            <div className="stat"><span className="stat-label">Open Trades</span><span className="stat-value">{summary.open_trades}</span></div>
            <div className="stat"><span className="stat-label">Logged Trades</span><span className="stat-value">{summary.logged_trades}</span></div>
            <div className="stat"><span className="stat-label">Win Rate</span><span className="stat-value">{summary.win_rate}%</span></div>
          </div>
        </div>
      )}

      {openPositions.length > 0 && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h2 style={{ margin: 0 }}>Open Positions</h2>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              {lastPriceUpdate && (
                <span className="price-updated">
                  Live prices &middot; {new Date(lastPriceUpdate).toLocaleTimeString()}
                </span>
              )}
              <button className="btn btn-secondary" onClick={handleRefreshPrices} disabled={priceRefreshing} style={{ marginLeft: 0 }}>
                {priceRefreshing ? "Refreshing..." : "Refresh Prices"}
              </button>
            </div>
          </div>
          <div className="table-wrapper">
            <table className="data-table">
              <thead><tr><th>Symbol</th><th>Type</th><th>Qty</th><th>Avg Price</th><th>Cost Basis</th><th>Current Price</th><th>Unrealized P&L</th><th></th></tr></thead>
              <tbody>
                {openPositions.map((p) => (
                  <>
                    <tr key={p.symbol} className={editSymbol === p.symbol ? "row-active" : ""} style={{ cursor: "pointer" }}
                        onClick={() => { setEditSymbol(editSymbol === p.symbol ? null : p.symbol); setClosePrice(""); }}>
                      <td style={{ fontWeight: 600 }}>{p.symbol}</td>
                      <td>{p.asset_category === "Stocks" ? "Stock" : "Option"}</td>
                      <td className={p.quantity > 0 ? "text-green" : "text-red"}>{p.quantity}</td>
                      <td>${p.avg_price.toFixed(2)}</td>
                      <td>${p.market_value.toFixed(2)}</td>
                      <td>{p.current_price != null ? `$${p.current_price.toFixed(2)}` : "—"}</td>
                      <td className={p.unrealized_pnl != null ? (p.unrealized_pnl >= 0 ? "text-green" : "text-red") : ""}>{p.unrealized_pnl != null ? `$${p.unrealized_pnl.toFixed(2)}` : "—"}</td>
                      <td style={{ color: "#8b949e", fontSize: 12 }}>{editSymbol === p.symbol ? "▲" : "▼"}</td>
                    </tr>
                    {editSymbol === p.symbol && (
                      <tr key={`${p.symbol}-edit`}>
                        <td colSpan={8} style={{ padding: 0 }}>
                          <div className="edit-panel">
                            <div className="edit-section">
                              <h3>Close Position</h3>
                              <div className="edit-row">
                                <div className="edit-field">
                                  <label>Date</label>
                                  <input type="date" value={closeDate} onChange={e => setCloseDate(e.target.value)} />
                                </div>
                                <div className="edit-field">
                                  <label>Close Price</label>
                                  <input type="number" step="0.01" placeholder="Price..." value={closePrice} onChange={e => setClosePrice(e.target.value)} />
                                </div>
                                <button className="btn btn-primary" disabled={!closePrice || actionLoading} onClick={() => handleClose(p)}>
                                  {actionLoading ? "..." : "Close"}
                                </button>
                              </div>
                            </div>
                            <div className="edit-section">
                              <button className="btn btn-danger" disabled={actionLoading} onClick={() => handleDelete(p.symbol)}>
                                Delete Position
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card">
        <h2>All Trades</h2>
        <div className="trades-toolbar">
          <div className="search-box">
            <input type="text" placeholder="Search symbol..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <div className="filter-group">
            <span className="filter-label">Side</span>
            {SIDES.map(s => (
              <button key={s} className={`btn ${sideFilter === s ? "btn-primary" : "btn-secondary"}`}
                onClick={() => { setSideFilter(s); setPage(0); }}>{s}</button>
            ))}
          </div>
          <div className="filter-group">
            <span className="filter-label">Type</span>
            {TYPES.map(t => (
              <button key={t} className={`btn ${typeFilter === t ? "btn-primary" : "btn-secondary"}`}
                onClick={() => { setTypeFilter(t); setPage(0); }}>{t}</button>
            ))}
          </div>
        </div>

        {loading ? <p className="muted">Loading...</p> : trades.length === 0 ? <p className="muted">No trades found.</p> : (
          <>
            <div className="table-wrapper">
              <table className="data-table">
                <thead><tr>
                  <th className="sortable" onClick={() => toggleSort("date")}>Date{sortIcon("date")}</th>
                  <th>Symbol</th><th>Type</th><th>Side</th><th>Qty</th><th>Price</th>
                  <th>Proceeds</th><th>Commission</th>
                  <th className="sortable" onClick={() => toggleSort("pnl")}>Realized P&L{sortIcon("pnl")}</th>
                </tr></thead>
                <tbody>
                  {trades.map(t => (
                    <tr key={t.id}>
                      <td className="nowrap">{new Date(t.date_time).toLocaleString()}</td>
                      <td className="nowrap" style={{ fontWeight: 600 }}>{t.symbol}</td>
                      <td>{t.asset_category === "Stocks" ? "Stock" : "Option"}</td>
                      <td className={t.quantity > 0 ? "text-green" : "text-red"}>{t.quantity > 0 ? "BUY" : "SELL"}</td>
                      <td>{Math.abs(t.quantity)}</td>
                      <td>${t.trade_price.toFixed(2)}</td>
                      <td>${t.proceeds.toFixed(2)}</td>
                      <td className="text-red">${t.commission.toFixed(2)}</td>
                      <td className={t.realized_pnl >= 0 ? "text-green" : "text-red"}>{t.realized_pnl !== 0 ? `$${t.realized_pnl.toFixed(2)}` : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "center" }}>
              <button className="btn btn-secondary" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>Previous</button>
              <span className="muted" style={{ padding: "10px 16px" }}>Page {page + 1}</span>
              <button className="btn btn-secondary" onClick={() => setPage(p => p + 1)} disabled={trades.length < PAGE_SIZE}>Next</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
