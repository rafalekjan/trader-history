import type { DailyPnL } from "../api/client";
import { fmtMoneyWhole, pnlClass } from "../utils/format";

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

function weekPnl(row: (number | null)[], pnlByDay: Record<number, DailyPnL>): number {
  return row.reduce((sum: number, d) => sum + (d != null ? pnlByDay[d]?.pnl ?? 0 : 0), 0);
}

interface Props {
  year: number;
  month: number; // 1-based
  pnlByDay: Record<number, DailyPnL>;
  selectedDay: number | null;
  onDayClick: (day: number) => void;
}

export default function CalendarGrid({ year, month, pnlByDay, selectedDay, onDayClick }: Props) {
  const weeks = getWeekRows(year, month);

  return (
    <div className="calendar-grid">
      <div className="calendar-row calendar-header-row">
        {DAYS.map((d) => <div key={d} className="calendar-day-header">{d}</div>)}
        <div className="calendar-day-header week-summary-header">Week</div>
      </div>
      {weeks.map((row, wi) => {
        const wp = weekPnl(row, pnlByDay);
        return (
          <div key={wi} className="calendar-row">
            {row.map((day, di) => {
              const data = day != null ? pnlByDay[day] : null;
              return (
                <div
                  key={di}
                  className={[
                    "calendar-cell",
                    day == null ? "empty" : data ? "clickable" : "",
                    data ? (data.pnl >= 0 ? "cell-green" : "cell-red") : "",
                    day != null && day === selectedDay ? "cell-selected" : "",
                  ].join(" ")}
                  onClick={() => day != null && data && onDayClick(day)}
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
  );
}
