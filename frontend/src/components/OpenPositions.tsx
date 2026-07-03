import { useState, useEffect, useCallback, Fragment } from "react";
import { api, type OpenPosition } from "../api/client";
import { fmtMoney, pnlClass } from "../utils/format";

const AUTO_REFRESH_MS = 5 * 60_000; // matches the backend price-refresh interval

export default function OpenPositions({ onChanged }: { onChanged?: () => void }) {
  const [positions, setPositions] = useState<OpenPosition[]>([]);
  const [editSymbol, setEditSymbol] = useState<string | null>(null);
  const [closeDate, setCloseDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [closePrice, setClosePrice] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  const load = useCallback(() => {
    api.getOpenPositions().then(setPositions).catch(console.error);
    api.getPrices().then((r) => setLastUpdate(r.last_updated)).catch(console.error);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  const toggleEdit = (symbol: string) => {
    setEditSymbol((cur) => (cur === symbol ? null : symbol));
    setClosePrice("");
  };

  const handleRefreshPrices = async () => {
    setRefreshing(true);
    try {
      const r = await api.refreshPrices();
      setLastUpdate(r.last_updated);
      api.getOpenPositions().then(setPositions);
    } catch (e) {
      console.error(e);
    } finally {
      setRefreshing(false);
    }
  };

  const handleClose = async (pos: OpenPosition) => {
    if (!closePrice) return;
    setBusy(true);
    try {
      await api.closePosition({
        symbol: pos.symbol,
        asset_category: pos.asset_category,
        close_price: parseFloat(closePrice),
        close_date: closeDate,
        quantity: pos.quantity,
      });
      setEditSymbol(null);
      setClosePrice("");
      load();
      onChanged?.();
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (symbol: string) => {
    if (!confirm(`Delete all trades for ${symbol}?`)) return;
    setBusy(true);
    try {
      await api.deleteBySymbol(symbol);
      setEditSymbol(null);
      load();
      onChanged?.();
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
    }
  };

  if (positions.length === 0) return null;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Open Positions</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {lastUpdate && (
            <span className="price-updated">
              Live prices &middot; {new Date(lastUpdate).toLocaleTimeString()}
            </span>
          )}
          <button
            className="btn btn-secondary"
            onClick={handleRefreshPrices}
            disabled={refreshing}
            style={{ marginLeft: 0 }}
          >
            {refreshing ? "Refreshing..." : "Refresh Prices"}
          </button>
        </div>
      </div>

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th><th>Type</th><th>Qty</th><th>Avg Price</th>
              <th>Cost Basis</th><th>Current Price</th><th>Unrealized P&L</th><th></th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <Fragment key={p.symbol}>
                <tr
                  className={editSymbol === p.symbol ? "row-active" : ""}
                  style={{ cursor: "pointer" }}
                  onClick={() => toggleEdit(p.symbol)}
                >
                  <td style={{ fontWeight: 600 }}>{p.symbol}</td>
                  <td>{p.asset_category === "Stocks" ? "Stock" : "Option"}</td>
                  <td className={pnlClass(p.quantity)}>{p.quantity}</td>
                  <td>{fmtMoney(p.avg_price)}</td>
                  <td>{fmtMoney(p.market_value)}</td>
                  <td>{p.current_price != null ? fmtMoney(p.current_price) : "—"}</td>
                  <td className={p.unrealized_pnl != null ? pnlClass(p.unrealized_pnl) : ""}>
                    {p.unrealized_pnl != null ? fmtMoney(p.unrealized_pnl) : "—"}
                  </td>
                  <td style={{ color: "#8b949e", fontSize: 12 }}>{editSymbol === p.symbol ? "▲" : "▼"}</td>
                </tr>
                {editSymbol === p.symbol && (
                  <tr>
                    <td colSpan={8} style={{ padding: 0 }}>
                      <div className="edit-panel">
                        <div className="edit-section">
                          <h3>Close Position</h3>
                          <div className="edit-row">
                            <div className="edit-field">
                              <label>Date</label>
                              <input type="date" value={closeDate} onChange={(e) => setCloseDate(e.target.value)} />
                            </div>
                            <div className="edit-field">
                              <label>Close Price</label>
                              <input
                                type="number" step="0.01" placeholder="Price..."
                                value={closePrice} onChange={(e) => setClosePrice(e.target.value)}
                              />
                            </div>
                            <button className="btn btn-primary" disabled={!closePrice || busy} onClick={() => handleClose(p)}>
                              {busy ? "..." : "Close"}
                            </button>
                          </div>
                        </div>
                        <div className="edit-section">
                          <button className="btn btn-danger" disabled={busy} onClick={() => handleDelete(p.symbol)}>
                            Delete Position
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
