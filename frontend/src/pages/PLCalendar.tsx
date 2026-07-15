import { useState, useEffect } from "react";
import { api, type MonthlyStats, type DailyPnL, type DayDetail } from "../api/client";
import { fmtMoney, fmtProfitFactor, pnlClass } from "../utils/format";
import { MONTHS, isoDate } from "../utils/dates";
import StatsBar from "../components/StatsBar";
import CalendarGrid from "../components/CalendarGrid";
import DayDetailCard from "../components/DayDetailCard";

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

  const closeDetail = () => {
    setSelectedDay(null);
    setDayDetail(null);
  };

  const handleDayClick = (day: number) => {
    if (selectedDay === day) {
      closeDetail();
      return;
    }
    setSelectedDay(day);
    setDayLoading(true);
    api.getDayDetail(isoDate(year, month, day))
      .then(setDayDetail)
      .catch(console.error)
      .finally(() => setDayLoading(false));
  };

  const shiftMonth = (delta: number) => {
    const d = new Date(year, month - 1 + delta);
    setYear(d.getFullYear());
    setMonth(d.getMonth() + 1);
  };

  const pnlByDay: Record<number, DailyPnL> = {};
  if (stats) for (const d of stats.daily) pnlByDay[parseInt(d.date.split("-")[2], 10)] = d;

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
            { label: "Profit Factor", value: fmtProfitFactor(stats.profit_factor) },
            { label: "Monthly P&L", value: fmtMoney(stats.total_pnl), className: pnlClass(stats.total_pnl) },
          ]} />
        )}

        {loading ? (
          <p className="muted">Loading...</p>
        ) : (
          <CalendarGrid
            year={year}
            month={month}
            pnlByDay={pnlByDay}
            selectedDay={selectedDay}
            onDayClick={handleDayClick}
          />
        )}
      </div>

      {selectedDay !== null && (
        <DayDetailCard
          title={`${MONTHS[month - 1]} ${selectedDay}, ${year}`}
          detail={dayDetail}
          loading={dayLoading}
          onClose={closeDetail}
        />
      )}
    </div>
  );
}
