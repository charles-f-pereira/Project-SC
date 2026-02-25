/**
 * Format datetimes for display in the Auto Allocation app.
 * All datetime stamps (except Expected Delivery Day) use:
 * - User's local timezone
 * - 24-hour time
 * - Time as HH:MM (no seconds)
 */

/**
 * Format a date/time for display: local timezone, 24hr, HH:MM.
 * @param {string|Date} value - ISO date string or Date instance
 * @returns {string} Formatted string e.g. "06/02/2025, 14:30" or "" if invalid
 */
export function formatDateTimeLocal(value) {
  if (value == null) return ''
  const d = typeof value === 'string' ? new Date(value) : value
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}
