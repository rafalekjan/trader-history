export interface StatItem {
  label: string;
  value: string | number;
  className?: string;
}

export default function StatsBar({ items, style }: { items: StatItem[]; style?: React.CSSProperties }) {
  return (
    <div className="stats-bar" style={style}>
      {items.map((s) => (
        <div className="stat" key={s.label}>
          <span className="stat-label">{s.label}</span>
          <span className={`stat-value ${s.className ?? ""}`}>{s.value}</span>
        </div>
      ))}
    </div>
  );
}
