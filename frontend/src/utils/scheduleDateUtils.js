/**
 * Helpers to derive next order date and next delivery date from Crunchtime
 * vendorLocationScheduleDetail (used by Auto Allocation when using each location's schedule).
 *
 * Crunchtime: orderDayMondayFlag, orderByTimeMonday, deliverDayMonday, ... (Monday–Sunday).
 * Delivery encoding: 1–7 same week Sun–Sat, 8–14 next week, 15–21 week+2.
 */

const ORDER_DAY_NAMES = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];
const ORDER_DAY_ABBR = {
  Monday: 'Mon',
  Tuesday: 'Tue',
  Wednesday: 'Wed',
  Thursday: 'Thu',
  Friday: 'Fri',
  Saturday: 'Sat',
  Sunday: 'Sun',
};
const DELIVERY_DAY_NAMES = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];
const ORDER_DAY_TO_JS_DAY = {
  Monday: 1,
  Tuesday: 2,
  Wednesday: 3,
  Thursday: 4,
  Friday: 5,
  Saturday: 6,
  Sunday: 0,
};
// getDay() 0=Sunday, 1=Monday, ... 6=Saturday -> day name for deliverDay* key
const JS_DAY_TO_ORDER_DAY_NAME = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];

function getVal(obj, ...keys) {
  for (const k of keys) {
    if (!k) continue;
    let v = obj[k];
    if (v !== undefined && v !== null) return v;
    const lower = k.charAt(0).toLowerCase() + k.slice(1);
    if (lower !== k) {
      v = obj[lower];
      if (v !== undefined && v !== null) return v;
    }
  }
  return undefined;
}

function nextDayOfWeek(date, dayOfWeek) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const currentDay = d.getDay();
  let diff = dayOfWeek - currentDay;
  if (diff < 0) diff += 7;
  d.setDate(d.getDate() + diff);
  return d;
}

function getWeekSunday(date) {
  const d = new Date(date);
  const day = d.getDay();
  d.setDate(d.getDate() - day);
  d.setHours(0, 0, 0, 0);
  return d;
}

function deliveryValueToDate(weekSunday, deliverDayValue) {
  const v = deliverDayValue != null ? parseInt(deliverDayValue, 10) : NaN;
  if (Number.isNaN(v) || v < 1 || v > 21) return null;
  const weekOffset = Math.floor((v - 1) / 7);
  const dayInWeek = (v - 1) % 7;
  const d = new Date(weekSunday);
  d.setDate(d.getDate() + weekOffset * 7 + dayInWeek);
  return d;
}

function toDateOnly(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

function toYYYYMMDD(date) {
  const d = new Date(date);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/**
 * Find the next order date on or after fromDate using schedule details.
 * Search window: fromDate through fromDate + maxDays (exclusive of last day).
 *
 * @param {Array<object>} scheduleDetailList - vendorLocationScheduleDetail array (or single detail)
 * @param {Date|string} fromDate - start date (Date or YYYY-MM-DD)
 * @param {number} maxDays - max days to look ahead (default 7)
 * @returns {string|null} YYYY-MM-DD of next order date, or null if none in window
 */
export function getNextOrderDateFromSchedule(scheduleDetailList, fromDate, maxDays = 7) {
  const list = Array.isArray(scheduleDetailList) ? scheduleDetailList : [scheduleDetailList];
  const start = toDateOnly(typeof fromDate === 'string' ? fromDate + 'T12:00:00' : fromDate);
  const end = new Date(start);
  end.setDate(end.getDate() + maxDays);

  let earliest = null;
  for (const detail of list) {
    for (const dayName of ORDER_DAY_NAMES) {
      const flagKey = `orderDay${dayName}Flag`;
      const orderFlag = getVal(detail, flagKey, `orderDay${dayName}flag`);
      const orderFlagStr = String(orderFlag || '').toLowerCase();
      const hasOrderDay = !!(
        orderFlag === true ||
        orderFlag === 1 ||
        orderFlagStr === 'true' ||
        orderFlagStr === 'y'
      );
      if (!hasOrderDay) continue;

      const jsDay = ORDER_DAY_TO_JS_DAY[dayName] ?? 1;
      const candidate = nextDayOfWeek(start, jsDay);
      if (candidate >= start && candidate < end) {
        const candStr = toYYYYMMDD(candidate);
        if (earliest == null || candStr < earliest) {
          earliest = candStr;
        }
      }
    }
  }
  return earliest;
}

/**
 * Find the next delivery date for a given order date from schedule details.
 * The order date falls on a weekday; we use the schedule row for that weekday and its deliverDay*.
 * Week = week containing the order date (Sun–Sat). Returns delivery date if within maxDaysAfterOrder.
 *
 * @param {Array<object>} scheduleDetailList - vendorLocationScheduleDetail array
 * @param {Date|string} orderDate - order date (Date or YYYY-MM-DD)
 * @param {number} maxDaysAfterOrder - max days after order date to look (default 8)
 * @returns {string|null} YYYY-MM-DD of delivery date, or null if none in window
 */
export function getNextDeliveryDateFromSchedule(
  scheduleDetailList,
  orderDate,
  maxDaysAfterOrder = 8,
) {
  const list = Array.isArray(scheduleDetailList) ? scheduleDetailList : [scheduleDetailList];
  const order = toDateOnly(typeof orderDate === 'string' ? orderDate + 'T12:00:00' : orderDate);
  const end = new Date(order);
  end.setDate(end.getDate() + maxDaysAfterOrder);

  const orderDayOfWeek = order.getDay();
  const orderDayName = JS_DAY_TO_ORDER_DAY_NAME[orderDayOfWeek];

  let earliest = null;
  for (const detail of list) {
    const flagKey = `orderDay${orderDayName}Flag`;
    const deliverKey = `deliverDay${orderDayName}`;
    const deliverKeyAbbr = ORDER_DAY_ABBR[orderDayName]
      ? `deliverDay${ORDER_DAY_ABBR[orderDayName]}`
      : null;
    const orderFlag = getVal(detail, flagKey, `orderDay${orderDayName}flag`);
    const orderFlagStr = String(orderFlag || '').toLowerCase();
    const hasOrderDay = !!(
      orderFlag === true ||
      orderFlag === 1 ||
      orderFlagStr === 'true' ||
      orderFlagStr === 'y'
    );
    if (!hasOrderDay) continue;

    const deliverDayValRaw = getVal(
      detail,
      deliverKey,
      deliverKeyAbbr,
      `deliverDay${orderDayName}`,
    );
    const deliverDayVal = deliverDayValRaw != null ? parseInt(deliverDayValRaw, 10) : null;
    if (
      deliverDayVal == null ||
      Number.isNaN(deliverDayVal) ||
      deliverDayVal < 1 ||
      deliverDayVal > 21
    ) {
      continue;
    }

    const weekSun = getWeekSunday(order);
    const deliveryDate = deliveryValueToDate(weekSun, deliverDayVal);
    if (deliveryDate) {
      const delOnly = toDateOnly(deliveryDate);
      if (delOnly >= order && delOnly <= end) {
        const candStr = toYYYYMMDD(delOnly);
        if (earliest == null || candStr < earliest) {
          earliest = candStr;
        }
      }
    }
  }
  return earliest;
}
