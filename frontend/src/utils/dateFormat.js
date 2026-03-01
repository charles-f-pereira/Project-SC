/**
 * Format datetimes for display in the Auto Allocation app.
 * Display formats use DD-MON-YYYY (date only) and DD-MON-YY HH:MM (dateTime)
 * for clarity across time zones and locales.
 */

const MONTH_ABBREV = [
  'JAN',
  'FEB',
  'MAR',
  'APR',
  'MAY',
  'JUN',
  'JUL',
  'AUG',
  'SEP',
  'OCT',
  'NOV',
  'DEC',
];

function pad2(n) {
  return String(n).padStart(2, '0');
}

/**
 * Format a date for display: DD-MON-YYYY (e.g. 25-FEB-2025).
 * For date-only strings (YYYY-MM-DD), uses the date as-is to avoid timezone shift.
 * For date/time values, uses local date parts.
 * @param {string|Date} value - ISO date string, YYYY-MM-DD, or Date instance
 * @returns {string} Formatted string or "" if invalid
 */
export function formatDateDisplay(value) {
  if (value == null) return '';
  const str = typeof value === 'string' ? value.trim().slice(0, 10) : '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(str)) {
    const [, y, m, d] = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    const monthIndex = parseInt(m, 10) - 1;
    if (monthIndex < 0 || monthIndex > 11) return '';
    return `${pad2(parseInt(d, 10))}-${MONTH_ABBREV[monthIndex]}-${y}`;
  }
  const d = typeof value === 'string' ? new Date(value) : value;
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) return '';
  const day = d.getDate();
  const month = d.getMonth();
  const year = d.getFullYear();
  return `${pad2(day)}-${MONTH_ABBREV[month]}-${year}`;
}

/**
 * Format a date/time for display: DD-MON-YY HH:MM (e.g. 25-FEB-25 14:30).
 * Uses local date/time so there is no ambiguity across time zones.
 * @param {string|Date} value - ISO date string or Date instance
 * @returns {string} Formatted string or "" if invalid
 */
export function formatDateTimeDisplay(value) {
  if (value == null) return '';
  const d = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return '';
  const day = d.getDate();
  const month = d.getMonth();
  const year = d.getFullYear() % 100;
  const hours = d.getHours();
  const minutes = d.getMinutes();
  return `${pad2(day)}-${MONTH_ABBREV[month]}-${pad2(year)} ${pad2(hours)}:${pad2(minutes)}`;
}

/**
 * Format a date/time for display: local timezone, 24hr, HH:MM.
 * @deprecated Prefer formatDateDisplay / formatDateTimeDisplay for review screens.
 * @param {string|Date} value - ISO date string or Date instance
 * @returns {string} Formatted string e.g. "06/02/2025, 14:30" or "" if invalid
 */
export function formatDateTimeLocal(value) {
  if (value == null) return '';
  const d = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}
