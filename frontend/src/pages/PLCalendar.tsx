import { useState, useEffect } from "react";
import { api, type MonthlyStats, type DailyPnL, type DayDetail } from "../api/client";

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];

function getCalendarDays(year: number, month: number) {
  const firstDay = new Date(year, month - 1, 1);
  let startDay = firstDay.getDay() - 1;
  if (startDay < 0) startDay = 6;
  const daysInMonth = new Date(year, month, 0).getDate();
  const cells: (number | null)[] = [];
  for (let i = 0; i < startDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function getWeekRows(cells: (number | null)[]): (number | null)[][] {
  const rows: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) rows.push(cells.slice(i, i + 7));
  return rows;
}

function weekPnl(row: (number | null)[], pnlMap: Record<number, DailyPnL>): number {
  let total = 0;
  for (const d of row) { if (d && pnlMap[d]) total += pnlMap[d].pnl; }
  return total;
}

function pad(n: number) { return n < 10 ? `0${n}` : `${n}`; }

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
    setLoading(true); setSelectedDay(null); setDayDetail(null);
    api.getMonthlyPnL(year, month).then(setStats).catch(console.error).finally(() => setLoading(false));
  }, [year, month]);

  const handleDayClick = (day: number) => {
    if (selectedDay === day) { setSelectedDay(null); setDayDetail(null); return; }
    setSelectedDay(day); setDayLoading(true);
    api.getDayDetail(`${year}-${pad(month)}-${pad(day)}`).then(setDayDetail).catch(console.error).finally(() => setDayLoading(false));
  };

  const prevMonth = () => { if (month === 1) { setMonth(12); setYear(y => y - 1); } else setMonth(m => m - 1); };
  const nextMonth = () => { if (month === 12) { setMonth(1); setYear(y => y + 1); } else setMonth(m => m + 1); };

  const pnlMap: Record<number, DailyPnL> = {};
  if (stats) for (const d of stats.daily) pnlMap[parseInt(d.date.split("-")[2], 10)] = d;

  const cells = getCalendarDays(year, month);
  const weeks = getWeekRows(cells);

  return (
    <div>
      <div className="card">
        <div className="calendar-header">
          <button className="btn btn-secondary" onClick={prevMonth}>&lt;</button>
          <h2 style={{ margin: 0 }}>{MONTHS[month - 1]} {year}</h2>
          <button className="btn btn-secondary" onClick={nextMonth}>&gt;</button>
        </div>

        {stats && !loading && (
          <div className="stats-bar">
            <div className="stat"><span className="stat-label">Trades</span><span className="stat-value">{stats.trade_count}</span></div>
            <div className="stat"><span className="stat-label">Win Rate</span><span className="stat-value">{stats.win_rate}%</span></div>
            <div className="stat"><span className="stat-label">Wins</span><span className="stat-value text-green">{stats.wins}</span></div>
            <div className="stat"><span className="stat-label">Losses</span><span className="stat-value text-red">{stats.losses}</span></div>
            <div className="stat"><span className="stat-label">Profit Factor</span><span className="stat-value">{stats.profit_factor}</span></div>
            <div className="stat"><span className="stat-label">Monthly P&L</span><span className={`stat-value ${stats.total_pnl >= 0 ? "text-green" : "text-red"}`}>${stats.total_pnl.toFixed(2)}</span></div>
          </div>
        )}

        {loading ? <p>Loading...</p> : (
          <div className="calendar-grid">
            <div className="calendar-row calendar-header-row">
              {DAYS.map((d) => <div key={d} className="calendar-day-header">{d}</div>)}
              <div className="calendar-day-header week-summary-header">Week</div>
            </div>
            {weeks.map((row, wi) => (
              <div key={wi} className="calendar-row">
                {row.map((day, di) => {
                  const data = day ? pnlMap[day] : null;
                  return (
                    <div key={di}
                      className={`calendar-cell ${!day ? "empty" : data ? "clickable" : ""} ${data ? (data.pnl >= 0 ? "cell-green" : "cell-red") : ""} ${day !== null && day === selectedDay ? "cell-selected" : ""}`}
                      onClick={() => day && data && handleDayClick(day)}
                    >
                      {day && (<>
                        <span className="cell-day">{day}</span>
                        {data && <span className={`cell-pnl ${data.pnl >= 0 ? "text-green" : "text-red"}`}>${data.pnl.toFixed(0)}</span>}
                        {data && <span className="cell-trades">{data.trade_count}t</span>}
                      </>)}
                    </div>
                  );
                })}
                <div className={`calendar-cell week-summary ${weekPnl(row, pnlMap) >= 0 ? "text-green" : "text-red"}`}>
                  {weekPnl(row, pnlMap) !== 0 && `$${weekPnl(row, pnlMap).toFixed(0)}`}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedDay !== null && (
        <div className="card day-detail-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>{MONTHS[month - 1]} {selectedDay}, {year}</h2>
            <button className="btn btn-secondary" onClick={() => { setSelectedDay(null); setDayDetail(null); }}>Close</button>
          </div>
          {dayLoading ? <p>Loading...</p> : dayDetail ? (<>
            <div className="stats-bar" style={{ marginTop: 16 }}>
              <div className="stat"><span className="stat-label">Realized That Day</span><span className={`stat-value ${dayDetail.realized_pnl >= 0 ? "text-green" : "text-red"}`}>${dayDetail.realized_pnl.toFixed(2)}</span></div>
              <div className="stat"><span className="stat-label">Wins</span><span className="stat-value text-green">{dayDetail.wins}</span></div>
              <div className="stat"><span className="stat-label">Losses</span><span className="stat-value text-red">{dayDetail.losses}</span></div>
              <div className="stat"><span className="stat-label">Trims</span><span className="stat-value">{dayDetail.trims}</span></div>
            </div>
            {dayDetail.trades.length > 0 && (
              <div className="setup-list">
                {dayDetail.trades.map((t, i) => (
                  <div key={i} className="setup-item">
                    <div className="setup-symbol">{t.symbol}</div>
                    <div className="setup-qty">{Math.abs(t.quantity)} @ ${t.trade_price.toFixed(2)}</div>
                    <div className={`setup-status setup-${t.status.toLowerCase()}`}>{t.status}</div>
                    <div className={`setup-pnl ${t.realized_pnl >= 0 ? "text-green" : "text-red"}`}>${t.realized_pnl.toFixed(2)}</div>
                  </div>
                ))}
              </div>
            )}
          </>) : <p className="muted" style={{ marginTop: 12 }}>No closed trades on this day.</p>}
        </div>
      )}
    </div>
  );
}
