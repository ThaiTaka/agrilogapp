/**
 * Date helpers — the client half of the epoch-ms contract.
 *
 * MUST agree with backend/app/core/timeutils.py exactly. The server buckets
 * report data one way and the client buckets it another; if they disagree by
 * a single day, the same season renders two different charts depending on
 * where the numbers came from.
 *
 * See Data_Requirements_Database.md §7.2.
 */

export const MS_PER_DAY = 86_400_000;

/**
 * UTC+7 in milliseconds.
 *
 * Vietnam has observed no daylight saving since 1975, so the local calendar
 * day is exact integer arithmetic — which is what lets PostgreSQL accept the
 * same expression as a STORED generated column and index it. Mirrors
 * APP_TZ_OFFSET_MS on the backend.
 */
export const TZ_OFFSET_MS = 7 * 60 * 60 * 1000; // 25_200_000

export function nowMs(): number {
  return Date.now();
}

/**
 * Days since the epoch in the app's fixed local timezone.
 *
 * Mirrors the SQL generated columns exactly:
 *     ((<date_col> + 25200000) / 86400000)::INTEGER
 */
export function localDayIndex(ms: number): number {
  return Math.floor((ms + TZ_OFFSET_MS) / MS_PER_DAY);
}

/** The local calendar date a day index names. */
export function dayIndexToDate(dayIndex: number): Date {
  return new Date(dayIndex * MS_PER_DAY);
}

/**
 * Snap a moment to the local day it falls in.
 *
 * Noon UTC rather than midnight: it keeps the value comfortably inside the
 * same local day whichever direction the UTC+7 offset is applied, so a stored
 * date never drifts across a day boundary.
 *
 * Every date a user PICKS should go through this. Mixing a picked date with a
 * raw `new Date()` makes two values on the same calendar day compare unequal —
 * which is how "ngày kết thúc trước ngày bắt đầu" fires on a season created
 * late in the evening and ended the same day.
 */
export function startOfLocalDay(value: Date | number): Date {
  const ms = value instanceof Date ? value.getTime() : value;
  return new Date(localDayIndex(ms) * MS_PER_DAY + 12 * 3600 * 1000);
}

/** Report bucket key, e.g. '2026-09'. */
export function localMonthKey(ms: number): string {
  const d = new Date(ms + TZ_OFFSET_MS);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

/** Report bucket key, e.g. '2026-09-12'. */
export function localDayKey(ms: number): string {
  const d = new Date(ms + TZ_OFFSET_MS);
  return (
    `${d.getUTCFullYear()}-` +
    `${String(d.getUTCMonth() + 1).padStart(2, '0')}-` +
    `${String(d.getUTCDate()).padStart(2, '0')}`
  );
}

/** ISO week bucket key, e.g. '2026-W37'. */
export function localWeekKey(ms: number): string {
  const d = new Date(ms + TZ_OFFSET_MS);
  const target = new Date(
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()),
  );
  // ISO-8601: week 1 is the week containing the first Thursday.
  const dayNum = (target.getUTCDay() + 6) % 7;
  target.setUTCDate(target.getUTCDate() - dayNum + 3);
  const firstThursday = new Date(Date.UTC(target.getUTCFullYear(), 0, 4));
  const firstDayNum = (firstThursday.getUTCDay() + 6) % 7;
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNum + 3);
  const week =
    1 + Math.round((target.getTime() - firstThursday.getTime()) / (7 * MS_PER_DAY));
  return `${target.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

// ─── Hiển thị cho người dùng ────────────────────────────────────────────────

/** '12/09/2026' — the format Vietnamese farmers read dates in. */
export function formatDate(value: Date | number | null | undefined): string {
  if (value === null || value === undefined) {
    return '—';
  }
  const ms = value instanceof Date ? value.getTime() : value;
  const d = new Date(ms + TZ_OFFSET_MS);
  return (
    `${String(d.getUTCDate()).padStart(2, '0')}/` +
    `${String(d.getUTCMonth() + 1).padStart(2, '0')}/` +
    `${d.getUTCFullYear()}`
  );
}

/** 'Vụ chưa kết thúc' when there is no end date yet. */
export function formatDateRange(start: Date | number, end: Date | number | null): string {
  return end ? `${formatDate(start)} – ${formatDate(end)}` : `${formatDate(start)} – nay`;
}

/** Số ngày đã trôi qua của mùa vụ. */
export function daysElapsed(start: Date | number, end?: Date | number | null): number {
  const startMs = start instanceof Date ? start.getTime() : start;
  const endMs = end ? (end instanceof Date ? end.getTime() : end) : Date.now();
  return Math.max(0, localDayIndex(endMs) - localDayIndex(startMs));
}
