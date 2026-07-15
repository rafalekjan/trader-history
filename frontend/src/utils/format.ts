const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const usdWhole = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

/** "-$1,234.56" — correct sign placement and thousands separators. */
export const fmtMoney = (n: number) => usd.format(n);

/** "-$1,235" — compact form for calendar cells. */
export const fmtMoneyWhole = (n: number) => usdWhole.format(n);

/** CSS class for coloring a P&L number. */
export const pnlClass = (n: number) => (n >= 0 ? "text-green" : "text-red");

/** Profit factor; null from the API means no losing trades (infinite). */
export const fmtProfitFactor = (pf: number | null) => (pf == null ? "∞" : pf);

/** Human label for an IBKR asset category. */
export const assetLabel = (category: string) =>
  category === "Stocks" ? "Stock" : category === "Futures" ? "Future" : "Option";
