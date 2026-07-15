import { useState } from "react";
import type { DayDetail, DayTradeEntry } from "../api/client";
import { fmtMoney, pnlClass } from "../utils/format";
import StatsBar from "./StatsBar";

function TradeRow({ trade: t }: { trade: DayTradeEntry }) {
  return (
    <div className="setup-item">
      <div className="setup-symbol">{t.symbol}</div>
      <div className="setup-qty">
        {t.side} {Math.abs(t.quantity)}{" "}
        {t.entry_price != null
          ? <>{fmtMoney(t.entry_price)} &rarr; {fmtMoney(t.trade_price)}</>
          : <>@ {fmtMoney(t.trade_price)}</>}
      </div>
      <div className="setup-fee">Fee {fmtMoney(t.commission)}</div>
      <div className="setup-net">Net {fmtMoney(t.net_amount)}</div>
      <div className={`setup-status setup-${t.status.toLowerCase()}`}>{t.status}</div>
      <div className={`setup-pnl ${t.realized_pnl != null ? pnlClass(t.realized_pnl) : "muted"}`}>
        {t.realized_pnl != null ? fmtMoney(t.realized_pnl) : "—"}
      </div>
    </div>
  );
}

interface Props {
  title: string;
  detail: DayDetail | null;
  loading: boolean;
  onClose: () => void;
}

export default function DayDetailCard({ title, detail, loading, onClose }: Props) {
  // Opening trades are hidden by default for readability; day-level fees and
  // P&L come from the backend and always cover them regardless of this toggle.
  const [showOpens, setShowOpens] = useState(false);

  const openCount = detail?.trades.filter((t) => t.status === "OPEN").length ?? 0;
  const visibleTrades = (detail?.trades ?? []).filter((t) => showOpens || t.status !== "OPEN");

  return (
    <div className="card day-detail-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>{title}</h2>
        <button className="btn btn-secondary" onClick={onClose}>Close</button>
      </div>
      {loading ? (
        <p className="muted">Loading...</p>
      ) : detail ? (
        <>
          <StatsBar
            style={{ marginTop: 16 }}
            items={[
              { label: "Realized That Day", value: fmtMoney(detail.realized_pnl), className: pnlClass(detail.realized_pnl) },
              { label: "Fees That Day", value: fmtMoney(detail.total_commission), className: detail.total_commission < 0 ? "text-red" : "" },
              { label: "Wins", value: detail.wins, className: "text-green" },
              { label: "Losses", value: detail.losses, className: "text-red" },
              { label: "Trims", value: detail.trims },
            ]}
          />
          {openCount > 0 && (
            <label className="show-opens-toggle">
              <input type="checkbox" checked={showOpens} onChange={(e) => setShowOpens(e.target.checked)} />
              Show opening trades ({openCount})
            </label>
          )}
          {visibleTrades.length > 0 && (
            <div className="setup-list">
              {visibleTrades.map((t, i) => <TradeRow key={i} trade={t} />)}
            </div>
          )}
        </>
      ) : (
        <p className="muted" style={{ marginTop: 12 }}>No closed trades on this day.</p>
      )}
    </div>
  );
}
