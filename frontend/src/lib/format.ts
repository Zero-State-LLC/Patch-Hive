/**
 * Formatting for what people read: dates as dates in the reader's locale, runs by number and
 * date, and hashes cut to a recognisable prefix. Raw ISO strings and full hashes never reach
 * the screen; a missing or unreadable date says so instead of guessing.
 */

const NOT_STATED = "Not stated";

type DateInput = string | number | Date | null | undefined;

function toDate(value: DateInput): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** "3 Nov 2026", or the reader's locale equivalent. */
export function formatDate(value: DateInput, locale?: string): string {
  const date = toDate(value);
  return date
    ? new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", year: "numeric" }).format(
        date,
      )
    : NOT_STATED;
}

/** "3 Nov 2026, 14:05", or the reader's locale equivalent. */
export function formatDateTime(value: DateInput, locale?: string): string {
  const date = toDate(value);
  return date
    ? new Intl.DateTimeFormat(locale, {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }).format(date)
    : NOT_STATED;
}

/** "Run 3, 3 Nov 2026": a generation run by its number and the day it ran. */
export function runLabel(run: { id: number; created_at?: string | null }, locale?: string): string {
  const day = toDate(run.created_at);
  return day ? `Run ${run.id}, ${formatDate(day, locale)}` : `Run ${run.id}`;
}

/**
 * The first characters of a hash or long id: enough to recognise, short enough to read. An id
 * like "rig-rev-6f81…" keeps its readable prefix and shortens only the hex after it.
 */
export function shortHash(value: string, length = 8): string {
  const prefixed = value.match(/^((?:[a-z0-9]+-)+)([0-9a-f]+)$/i);
  if (prefixed) return prefixed[1] + prefixed[2].slice(0, length);
  return value.length > length ? value.slice(0, length) : value;
}
