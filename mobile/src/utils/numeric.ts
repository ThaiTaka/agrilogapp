/**
 * Money and quantity — the client half of the rounding contract.
 *
 * MUST agree with backend/app/core/numeric.py. Both sides round identically
 * at the boundary, so the stored value on device and server is bit-identical
 * and last-write-wins never fires on a value that merely *looks* different.
 *
 * See Data_Requirements_Database.md §7.1.
 */

/** Round to 3 decimal places — 0.250 kg, 12.500 L, 1.750 bao. */
export function quantizeQuantity(value: number): number {
  return Math.round(value * 1000) / 1000;
}

/** Round to 2 decimal places. VND. */
export function quantizeMoney(value: number): number {
  return Math.round(value * 100) / 100;
}

/**
 * quantity × unitCost, rounded once at the end.
 *
 * Rounding the intermediate product would drift by a đồng per line and by a
 * visible amount across a season's worth of transactions.
 */
export function lineTotal(quantity: number, unitCost: number): number {
  return quantizeMoney(quantizeQuantity(quantity) * quantizeMoney(unitCost));
}

/**
 * Parse what the farmer typed. Accepts '12,5' as well as '12.5' — Vietnamese
 * keyboards and habits produce the comma, and rejecting it would be a
 * pointless obstacle at the exact moment they are standing in a field.
 */
export function parseNumberInput(raw: string): number | null {
  const cleaned = raw.trim().replace(/\s/g, '').replace(',', '.');
  if (cleaned === '') {
    return null;
  }
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : null;
}

// ─── Hiển thị ───────────────────────────────────────────────────────────────

const vndFormatter = new Intl.NumberFormat('vi-VN', {
  maximumFractionDigits: 0,
});

/** '1.250.000 ₫' */
export function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return `${vndFormatter.format(Math.round(value))} ₫`;
}

/** '1,25 tr' / '1,2 tỷ' — for chart axes and tight tiles where the full
 *  number would not fit. */
export function formatMoneyShort(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—';
  }
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1_000_000_000) {
    return `${sign}${(abs / 1_000_000_000).toFixed(1).replace('.', ',')} tỷ`;
  }
  if (abs >= 1_000_000) {
    return `${sign}${(abs / 1_000_000).toFixed(1).replace('.', ',')} tr`;
  }
  if (abs >= 1_000) {
    return `${sign}${(abs / 1_000).toFixed(0)}k`;
  }
  return `${sign}${abs.toFixed(0)}`;
}

/** '12,5 kg' — trailing zeros trimmed, comma as the decimal separator. */
export function formatQuantity(value: number | null | undefined, unit?: string): string {
  if (value === null || value === undefined) {
    return '—';
  }
  const rounded = quantizeQuantity(value);
  const text = (Number.isInteger(rounded) ? String(rounded) : String(rounded)).replace(
    '.',
    ',',
  );
  return unit ? `${text} ${unit}` : text;
}
