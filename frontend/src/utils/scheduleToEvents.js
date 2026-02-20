/**
 * Convert vendorLocationScheduleDetail and scheduleOverrideRowList to calendar events.
 *
 * Crunchtime delivery day encoding (per order day, e.g. deliverDayFriday):
 *   1 = Del Sun (same week), 2 = Del Mon, 3 = Del Tue, 4 = Del Wed, 5 = Del Thu, 6 = Del Fri, 7 = Del Sat
 *   8 = Del 2nd Sun (next week), 9 = Del 2nd Mon, 10 = Del 2nd Tue, ..., 14 = Del 2nd Sat
 *   15-21 = week+2
 * Week = week containing the order day (Sunday–Saturday). Same week = 1–7, next week = 8–14.
 *
 * Handles incomplete config: order day with no delivery day (order event only);
 * delivery day with no order day (delivery event only).
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

function parseTime(timeStr) {
  if (!timeStr || typeof timeStr !== 'string') return { hours: 0, minutes: 0 };
  const parts = timeStr.trim().split(/[:\s]/);
  const hours = parseInt(parts[0], 10) || 0;
  const minutes = parseInt(parts[1], 10) || 0;
  return { hours, minutes };
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

/** Delivery value (1-21) to human label; weekOffset 0 = same week, 1 = next week, 2 = week+2 */
export function deliveryValueToDayLabel(deliverDayValue) {
  const v = deliverDayValue != null ? parseInt(deliverDayValue, 10) : NaN;
  if (Number.isNaN(v) || v < 1 || v > 21) return '';
  const weekOffset = Math.floor((v - 1) / 7);
  const dayInWeek = (v - 1) % 7;
  const dayName = DELIVERY_DAY_NAMES[dayInWeek] || '';
  if (weekOffset === 0) return dayName;
  if (weekOffset === 1) return `del next week ${dayName}`;
  return `del week+${weekOffset} ${dayName}`;
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

const ORDER_DAY_TO_JS_DAY = {
  Monday: 1,
  Tuesday: 2,
  Wednesday: 3,
  Thursday: 4,
  Friday: 5,
  Saturday: 6,
  Sunday: 0,
};

/** Hash vendor code to a consistent colour index (0..N) for calendar */
export function vendorColorIndex(vendorCode, totalVendors) {
  if (!vendorCode || totalVendors <= 0) return 0;
  let h = 0;
  const s = String(vendorCode);
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return Math.abs(h) % Math.max(1, totalVendors);
}

/** Process one schedule detail array (standard or override) and push events */
function processDetailArray(
  events,
  item,
  details,
  startDate,
  endDate,
  isOverride,
  vendorIndex,
  totalVendors,
) {
  const locationCode = getVal(item, 'locationCode', 'LocationCode') || 'Location';
  const vendorCode = getVal(item, 'vendorCode', 'VendorCode', 'vendor') || 'Vendor';

  for (const detail of details) {
    for (const dayName of ORDER_DAY_NAMES) {
      const flagKey = `orderDay${dayName}Flag`;
      const timeKey = `orderByTime${dayName}`;
      const deliverKey = `deliverDay${dayName}`;
      const deliverKeyAbbr = ORDER_DAY_ABBR[dayName]
        ? `deliverDay${ORDER_DAY_ABBR[dayName]}`
        : null;

      const orderFlag = getVal(detail, flagKey, `orderDay${dayName}flag`);
      const orderFlagStr = String(orderFlag || '').toLowerCase();
      const hasOrderDay = !!(
        orderFlag === true ||
        orderFlag === 1 ||
        orderFlagStr === 'true' ||
        orderFlagStr === 'y'
      );
      const orderByTime = getVal(detail, timeKey, `orderByTime${dayName}`);
      const deliverDayValRaw = getVal(detail, deliverKey, deliverKeyAbbr, `deliverDay${dayName}`);
      const deliverDayVal = deliverDayValRaw != null ? parseInt(deliverDayValRaw, 10) : null;
      const hasDeliveryDay =
        deliverDayVal != null &&
        !Number.isNaN(deliverDayVal) &&
        deliverDayVal >= 1 &&
        deliverDayVal <= 21;
      const jsDay = ORDER_DAY_TO_JS_DAY[dayName] ?? 1;

      if (!hasOrderDay && !hasDeliveryDay) continue;

      const deliveryLabel = hasDeliveryDay ? deliveryValueToDayLabel(deliverDayVal) : '';
      const prefix = isOverride ? '[Override] ' : '';

      if (hasOrderDay) {
        let cursor = nextDayOfWeek(new Date(startDate), jsDay);
        let iter = 0;
        while (cursor <= endDate && iter < 104) {
          iter++;
          const weekSun = getWeekSunday(cursor);
          const deliveryDate = hasDeliveryDay ? deliveryValueToDate(weekSun, deliverDayVal) : null;

          const { hours, minutes } = parseTime(orderByTime);
          const orderStart = new Date(cursor);
          orderStart.setHours(hours, minutes, 0, 0);
          const orderEnd = new Date(orderStart);
          orderEnd.setMinutes(orderEnd.getMinutes() + 30);

          events.push({
            id: `order-${isOverride ? 'ov' : 'std'}-${locationCode}-${vendorCode}-${dayName}-${cursor.toISOString().slice(0, 10)}`,
            title: `${prefix}Order by ${orderByTime || '--'} · ${vendorCode}${deliveryLabel ? ` → ${deliveryLabel}` : ''}`,
            start: orderStart,
            end: orderEnd,
            allDay: false,
            resource: {
              type: 'order',
              locationCode,
              vendorCode,
              vendorIndex,
              totalVendors,
              isOverride,
              orderDay: dayName,
              orderByTime,
              deliveryDate,
              deliveryLabel,
              orderStartDate: new Date(orderStart),
              detail,
            },
          });

          if (
            hasDeliveryDay &&
            deliveryDate &&
            deliveryDate >= startDate &&
            deliveryDate <= endDate
          ) {
            const { hours, minutes } = parseTime(orderByTime);
            const deliveryStart = new Date(
              deliveryDate.getFullYear(),
              deliveryDate.getMonth(),
              deliveryDate.getDate(),
              hours,
              minutes,
              0,
              0,
            );
            const deliveryEnd = new Date(deliveryStart);
            deliveryEnd.setMinutes(deliveryEnd.getMinutes() + 30);
            events.push({
              id: `delivery-${isOverride ? 'ov' : 'std'}-${locationCode}-${vendorCode}-${dayName}-${deliveryDate.toISOString().slice(0, 10)}`,
              title: `${prefix}Delivery · ${vendorCode} (${deliveryLabel})`,
              start: deliveryStart,
              end: deliveryEnd,
              allDay: false,
              resource: {
                type: 'delivery',
                locationCode,
                vendorCode,
                vendorIndex,
                totalVendors,
                isOverride,
                orderDay: dayName,
                orderByTime,
                deliveryDate,
                deliveryLabel,
                orderStartDate: new Date(orderStart),
                detail,
              },
            });
          }

          cursor.setDate(cursor.getDate() + 7);
        }
      } else if (hasDeliveryDay) {
        for (let w = 0; w < 104; w++) {
          const weekSun = new Date(startDate);
          weekSun.setDate(weekSun.getDate() - weekSun.getDay() + w * 7);
          const deliveryDate = deliveryValueToDate(weekSun, deliverDayVal);
          if (deliveryDate && deliveryDate >= startDate && deliveryDate <= endDate) {
            events.push({
              id: `delivery-only-${isOverride ? 'ov' : 'std'}-${locationCode}-${vendorCode}-${dayName}-${deliveryDate.toISOString().slice(0, 10)}-${w}`,
              title: `${prefix}Delivery · ${vendorCode} (${deliveryLabel})`,
              start: new Date(
                deliveryDate.getFullYear(),
                deliveryDate.getMonth(),
                deliveryDate.getDate(),
              ),
              end: new Date(
                deliveryDate.getFullYear(),
                deliveryDate.getMonth(),
                deliveryDate.getDate(),
              ),
              allDay: true,
              resource: {
                type: 'delivery',
                locationCode,
                vendorCode,
                vendorIndex,
                totalVendors,
                isOverride,
                orderDay: dayName,
                deliveryDate,
                deliveryLabel,
                detail,
              },
            });
          }
        }
      }
    }
  }
}

export function scheduleToEvents(scheduleItems, options = {}) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const startDate = options.startDate
    ? new Date(options.startDate)
    : new Date(today.getFullYear(), today.getMonth() - 3, 1);
  startDate.setHours(0, 0, 0, 0);
  const endDate = options.endDate
    ? new Date(options.endDate)
    : new Date(today.getFullYear(), today.getMonth() + 4, 0);
  endDate.setHours(23, 59, 59, 999);

  const events = [];
  const totalVendors = Math.max(1, (scheduleItems || []).length);

  scheduleItems.forEach((item, vendorIndex) => {
    const locationCode = getVal(item, 'locationCode', 'LocationCode') || 'Location';
    const vendorCode = getVal(item, 'vendorCode', 'VendorCode', 'vendor') || 'Vendor';

    let standardDetails = getVal(
      item,
      'vendorLocationScheduleDetail',
      'VendorLocationScheduleDetail',
    );
    if (!standardDetails) standardDetails = [];
    if (!Array.isArray(standardDetails)) standardDetails = [standardDetails];

    let overrideDetails = getVal(item, 'scheduleOverrideRowList', 'ScheduleOverrideRowList');
    if (!overrideDetails) overrideDetails = [];
    if (!Array.isArray(overrideDetails)) overrideDetails = [overrideDetails];

    processDetailArray(
      events,
      item,
      standardDetails,
      startDate,
      endDate,
      false,
      vendorIndex,
      totalVendors,
    );
    if (overrideDetails.length) {
      processDetailArray(
        events,
        item,
        overrideDetails,
        startDate,
        endDate,
        true,
        vendorIndex,
        totalVendors,
      );
    }
  });

  return events;
}
