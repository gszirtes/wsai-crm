// HUF/EUR are the only two currencies the plan supports (schemas.py's
// Currency Literal) -- kept here so callers don't redeclare the pair.
export const CURRENCIES = ["EUR", "HUF"];

// Symbol placement differs (Ft trails, EUR's symbol leads), so this can't
// just be string interpolation with a swapped symbol.
export function formatMoney(n, currency = "EUR") {
  if (n == null) return "—";
  const formatted = new Intl.NumberFormat().format(n);
  return currency === "HUF" ? `${formatted} Ft` : `€${formatted}`;
}

// Plan 4.2: never sum HUF+EUR into one total -- render each currency that
// actually has a nonzero amount in a {currency: amount} dict, instead of
// picking one arbitrarily. Shared by every page that displays a per-currency
// money breakdown (Dashboard, Utilization) instead of each redefining it.
export function formatMoneyByCurrency(byCurrency) {
  if (byCurrency == null) return "—";
  const parts = Object.entries(byCurrency).filter(([, v]) => v).map(([c, v]) => formatMoney(v, c));
  return parts.length ? parts.join(" · ") : formatMoney(0, "EUR");
}
