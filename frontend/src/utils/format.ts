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
