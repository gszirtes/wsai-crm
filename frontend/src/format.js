// Shared money formatter: HUF/EUR are the only two currencies the plan
// supports (schemas.py's Currency Literal) -- symbol placement differs
// (Ft trails, EUR's symbol leads), so this can't just be string interpolation
// with a swapped symbol.
export function formatMoney(n, currency = "EUR") {
  if (n == null) return "—";
  const formatted = new Intl.NumberFormat().format(n);
  return currency === "HUF" ? `${formatted} Ft` : `€${formatted}`;
}
