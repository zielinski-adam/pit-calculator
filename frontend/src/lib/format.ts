/** Formatowanie wartości dla wyświetlania. */

/** Formatuj liczbę z polskim locale. */
export function fmtPLN(value: string | number, decimals = 2): string {
  return Number(value).toLocaleString("pl-PL", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Formatuj datę ISO na dd.mm.yyyy. */
export function fmtDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const [y, m, d] = dateStr.split("-");
  return `${d}.${m}.${y}`;
}

/** Formatuj ilość (bez zbędnych zer). */
export function fmtQty(value: string | number): string {
  const n = Number(value);
  return n % 1 === 0 ? n.toLocaleString("pl-PL") : n.toLocaleString("pl-PL", { maximumFractionDigits: 6 });
}

/** Klasa CSS dla zysku/straty. */
export function plClass(value: string | number): string {
  const n = Number(value);
  if (n > 0) return "text-green-600";
  if (n < 0) return "text-red-600";
  return "";
}
