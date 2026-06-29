const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || res.statusText); }
  return res.json();
}

export interface ImportResult { status: string; imported: number; message: string; }
export interface ImportedTrade {
  id: number; account_id: string; asset_category: string; currency: string;
  symbol: string; date_time: string; quantity: number; trade_price: number;
  close_price: number | null; proceeds: number; commission: number;
  realized_pnl: number; mtm_pnl: number; code: string;
}
export interface DailyPnL { date: string; pnl: number; trade_count: number; wins: number; losses: number; }
export interface MonthlyStats { year: number; month: number; total_pnl: number; trade_count: number; wins: number; losses: number; win_rate: number; profit_factor: number; daily: DailyPnL[]; }
export interface CumulativePnLPoint { date: string; cumulative_pnl: number; daily_pnl: number; }
export interface TradeSummary { net_realized_pnl: number; open_trades: number; logged_trades: number; win_rate: number; }
export interface OpenPosition { symbol: string; asset_category: string; quantity: number; avg_price: number; market_value: number; current_price: number | null; unrealized_pnl: number | null; }
export interface DayTradeEntry { symbol: string; asset_category: string; quantity: number; trade_price: number; realized_pnl: number; status: string; }
export interface DayDetail { date: string; realized_pnl: number; wins: number; losses: number; trims: number; trades: DayTradeEntry[]; }
export interface TradeRef { symbol: string; pnl: number; date: string; }
export interface FullStats { net_realized_pnl: number; win_rate: number; closed_trades: number; profit_factor: number; avg_win: number; avg_loss: number; best_trade: TradeRef | null; worst_trade: TradeRef | null; }
export interface DepositEntry { currency: string; settle_date: string; description: string; amount: number; }
export interface DepositsResponse { deposits: DepositEntry[]; total_native: Record<string, number>; total_usd: number; }

export const api = {
  uploadCSV: async (file: File): Promise<ImportResult> => {
    const form = new FormData(); form.append("file", file);
    const res = await fetch(`${BASE}/csv/upload`, { method: "POST", body: form });
    if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || res.statusText); }
    return res.json();
  },
  getImportedTrades: (opts: { limit?: number; offset?: number; search?: string; side?: string; tradeType?: string; sortBy?: string; sortDir?: string; } = {}) => {
    const p = new URLSearchParams({ limit: String(opts.limit ?? 200), offset: String(opts.offset ?? 0), sort_by: opts.sortBy ?? "date", sort_dir: opts.sortDir ?? "desc" });
    if (opts.search) p.set("search", opts.search);
    if (opts.side) p.set("side", opts.side);
    if (opts.tradeType) p.set("trade_type", opts.tradeType);
    return request<ImportedTrade[]>(`/imported-trades?${p}`);
  },
  getTradeSummary: () => request<TradeSummary>("/analytics/summary"),
  getOpenPositions: () => request<OpenPosition[]>("/analytics/open-positions"),
  getDayDetail: (date: string) => request<DayDetail>(`/analytics/day-detail?date=${date}`),
  getMonthlyPnL: (year: number, month: number) => request<MonthlyStats>(`/analytics/monthly-pnl?year=${year}&month=${month}`),
  getCumulativePnL: () => request<CumulativePnLPoint[]>("/analytics/cumulative-pnl"),
  getFullStats: (startDate?: string, endDate?: string) => {
    const p = new URLSearchParams();
    if (startDate) p.set("start_date", startDate);
    if (endDate) p.set("end_date", endDate);
    const qs = p.toString();
    return request<FullStats>(`/analytics/stats${qs ? "?" + qs : ""}`);
  },
  getDeposits: () => request<DepositsResponse>("/analytics/deposits"),
  closePosition: (data: { symbol: string; asset_category: string; close_price: number; close_date: string; quantity: number }) =>
    request("/trades/close-position", { method: "POST", body: JSON.stringify(data) }),
  deleteBySymbol: (symbol: string) =>
    request(`/trades/by-symbol/${encodeURIComponent(symbol)}`, { method: "DELETE" }),
  refreshPrices: () => request<{ status: string; updated: number; last_updated: string | null }>("/analytics/prices/refresh", { method: "POST" }),
  getPrices: () => request<{ prices: Record<string, { price: number; updated_at: string }>; last_updated: string | null }>("/analytics/prices"),
};
