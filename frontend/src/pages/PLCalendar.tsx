import { useState, useEffect } from "react";
import { api, type MonthlyStats, type DailyPnL, type DayDetail } from "../api/client";
import { fmtMoney, fmtMoneyWhole, pnlClass } from "../utils/format";
import StatsBar from "../components/StatsBar";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Month grid as rows of 7 cells (Mon-first); null = padding outside the month. */
function getWeekRows(year: number, month: number): (number | null)[][] {
  const startDay = (new Date(year, month - 1, 1).getDay() + 6) % 7;
  const daysInMonth = new Date(year, month, 0).getDate();

  const cells: (number | null)[] = [
    ...Array<null>(startDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const rows: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) rows.push(cells.slice(i, i + 7));
  return rows;
}

function weekPnl(row: (number | null)[], pnlMap: Record<number, DailyPnL>): number {
  return row.reduce((sum: number, d) => sum + (d != null ? pnlMap[d]?.pnl ?? 0 : 0), 0);
}

const pad = (n: number) => String(n).padStart(2, "0");

export default function PLCalendar() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [stats, setStats] = useState<MonthlyStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [dayDetail, setDayDetail] = useState<DayDetail | null>(null);
  const [dayLoading, setDayLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setSelectedDay(null);
    setDayDetail(null);
    api.getMonthlyPnL(year, month).then(setStats).catch(console.error).finally(() => setLoading(false));
  }, [year, month]);

  const handleDayClick = (day: number) => {
    if (selectedDay === day) {
      setSelectedDay(null);
      setDayDetail(null);
      return;
    }
    setSelectedDay(day);
    setDayLoading(true);
    api.getDayDetail(`${year}-${pad(month)}-${pad(day)}`)
      .then(setDayDetail)
      .catch(console.error)
      .finally(() => setDayLoading(false));
  };

  const shiftMonth = (delta: number) => {
    const d = new Date(year, month - 1 + delta);
    setYear(d.getFullYear());
    setMonth(d.getMonth() + 1);
  };

  const pnlMap: Record<number, DailyPnL> = {};
  if (stats) for (const d of stats.daily) pnlMap[parseInt(d.date.split("-")[2], 10)] = d;

  const weeks = getWeekRows(year, month);

  return (
    <div>
      <div className="card">
        <div className="calendar-header">
          <button className="btn btn-secondary" onClick={() => shiftMonth(-1)}>&lt;</button>
          <h2 style={{ margin: 0 }}>{MONTHS[month - 1]} {year}</h2>
          <button className="btn btn-secondary" onClick={() => shiftMonth(1)}>&gt;</button>
        </div>

        {stats && !loading && (
          <StatsBar items={[
            { label: "Trades", value: stats.trade_count },
            { label: "Win Rate", value: `${stats.win_rate}%` },
            { label: "Wins", value: stats.wins, className: "text-green" },
            { label: "Losses", value: stats.losses, className: "text-red" },
            { label: "Profit Factor", value: stats.profit_factor },
            { label: "Monthly P&L", value: fmtMoney(stats.total_pnl), className: pnlClass(stats.total_pnl) },
          ]} />
        )}

        {loading ? (
          <p className="muted">Loading...</p>
        ) : (
          <div className="calendar-grid">
            <div className="calendar-row calendar-header-row">
              {DAYS.map((d) => <div key={d} className="calendar-day-header">{d}</div>)}
              <div className="calendar-day-header week-summary-header">Week</div>
            </div>
            {weeks.map((row, wi) => {
              const wp = weekPnl(row, pnlMap);
              return (
                <div key={wi} className="calendar-row">
                  {row.map((day, di) => {
                    const data = day != null ? pnlMap[day] : null;
                    return (
                      <div
                        key={di}
                        className={[
                          "calendar-cell",
                          day == null ? "empty" : data ? "clickable" : "",
                          data ? (data.pnl >= 0 ? "cell-green" : "cell-red") : "",
                          day != null && day === selectedDay ? "cell-selected" : "",
                        ].join(" ")}
                        onClick={() => day != null && data && handleDayClick(day)}
                      >
                        {day != null && (
                          <>
                            <span className="cell-day">{day}</span>
                            {data && <span className={`cell-pnl ${pnlClass(data.pnl)}`}>{fmtMoneyWhole(data.pnl)}</span>}
                            {data && <span className="cell-trades">{data.trade_count}t</span>}
                          </>
                        )}
                      </div>
                    );
                  })}
                  <div className={`calendar-cell week-summary ${pnlClass(wp)}`}>
                    {wp !== 0 && fmtMoneyWhole(wp)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {selectedDay !== null && (
        <div className="card day-detail-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>{MONTHS[month - 1]} {selectedDay}, {year}</h2>
            <button className="btn btn-secondary" onClick={() => { setSelectedDay(null); setDayDetail(null); }}>
              Close
            </button>
          </div>
          {dayLoading ? (
            <p className="muted">Loading...</p>
          ) : dayDetail ? (
            <>
              <StatsBar
                style={{ marginTop: 16 }}
                items={[
                  { label: "Realized That Day", value: fmtMoney(dayDetail.realized_pnl), className: pnlClass(dayDetail.realized_pnl) },
                  { label: "Wins", value: dayDetail.wins, className: "text-green" },
                  { label: "Losses", value: dayDetail.losses, className: "text-red" },
                  { label: "Trims", value: dayDetail.trims },
                ]}
              />
              {dayDetail.trades.length > 0 && (
                <div className="setup-list">
                  {dayDetail.trades.map((t, i) => (
                    <div key={i} className="setup-item">
                      <div className="setup-symbol">{t.symbol}</div>
                      <div className="setup-qty">{Math.abs(t.quantity)} @ {fmtMoney(t.trade_price)}</div>
                      <div className={`setup-status setup-${t.status.toLowerCase()}`}>{t.status}</div>
                      <div className={`setup-pnl ${pnlClass(t.realized_pnl)}`}>{fmtMoney(t.realized_pnl)}</div>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <p className="muted" style={{ marginTop: 12 }}>No closed trades on this day.</p>
          )}
        </div>
      )}
    </div>
  );
}
