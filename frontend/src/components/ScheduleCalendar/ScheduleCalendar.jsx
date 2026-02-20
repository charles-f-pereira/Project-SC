import { useMemo, useState, useEffect } from 'react';
import { Calendar, momentLocalizer } from 'react-big-calendar';
import moment from 'moment';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import 'moment/locale/en-gb';
import { scheduleToEvents } from '../../utils/scheduleToEvents';
import './ScheduleCalendar.css';

// Set Monday as first day of week (en-gb default, but explicit for clarity)
moment.locale('en-gb', { week: { dow: 1 } });

const localizer = momentLocalizer(moment);

// Colours per vendor (order = blue shades, delivery = green shades); override = dashed border
const VENDOR_ORDER_COLORS = ['#2980b9', '#3498db', '#5dade2', '#85c1e9', '#1a5276', '#2874a6'];
const VENDOR_DELIVERY_COLORS = ['#1e8449', '#27ae60', '#52be80', '#82e0aa', '#186a3b', '#229954'];

function getEventColor(event, view) {
  const r = event.resource;
  if (r?.type === 'holiday') return { bg: '#ff9800', border: 'none' };
  const idx = (r?.vendorIndex ?? 0) % Math.max(1, r?.totalVendors ?? 1);
  const orderPalette = VENDOR_ORDER_COLORS;
  const deliveryPalette = VENDOR_DELIVERY_COLORS;
  if (r?.type === 'order') {
    return {
      bg: orderPalette[idx % orderPalette.length],
      border: r?.isOverride ? '2px dashed #1a252f' : 'none',
    };
  }
  if (r?.type === 'delivery') {
    return {
      bg: deliveryPalette[idx % deliveryPalette.length],
      border: r?.isOverride ? '2px dashed #0e6655' : 'none',
    };
  }
  return { bg: '#3498db', border: 'none' };
}

function sameDate(d1, d2) {
  if (!d1 || !d2) return false;
  const a = new Date(d1);
  const b = new Date(d2);
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/**
 * Find the single paired event for the selected one (order ↔ delivery).
 * Uses Crunchtime logic: each order has a computed deliveryDate (1–7 same week, 8–14 next week, etc.).
 * Pair by that delivery date so order Fri → delivery Mon next week matches correctly.
 * - Order → delivery: same vendor/location/orderDay/override, and delivery's date equals order.deliveryDate.
 * - Delivery → order: same vendor/location/orderDay/override, and order.deliveryDate equals delivery's date.
 */
function findPairedEvent(selected, events) {
  if (!selected?.resource || selected.resource.type === 'holiday') return null;
  const r = selected.resource;
  const type = r.type;
  const loc = r.locationCode;
  const vend = r.vendorCode;
  const orderDay = r.orderDay;
  const isOverride = !!r.isOverride;
  const orderDeliveryDate = r.deliveryDate || (type === 'delivery' ? selected.start : null);
  const deliveryEventDate = type === 'delivery' ? selected.start : null;

  const isSameVendorLoc = (er) =>
    er &&
    er.type !== 'holiday' &&
    er.locationCode === loc &&
    er.vendorCode === vend &&
    er.orderDay === orderDay &&
    !!er.isOverride === isOverride;

  if (type === 'order') {
    if (!orderDeliveryDate) return null;
    return (
      events.find((e) => {
        const er = e.resource;
        if (!isSameVendorLoc(er) || er.type !== 'delivery') return false;
        return (
          sameDate(e.start, orderDeliveryDate) ||
          (er.deliveryDate != null && sameDate(er.deliveryDate, orderDeliveryDate))
        );
      }) || null
    );
  }

  if (type === 'delivery') {
    if (!deliveryEventDate) return null;
    return (
      events.find((e) => {
        const er = e.resource;
        if (!isSameVendorLoc(er) || er.type !== 'order') return false;
        return er.deliveryDate != null && sameDate(er.deliveryDate, deliveryEventDate);
      }) || null
    );
  }

  return null;
}

export default function ScheduleCalendar({ schedules, holidays, filters }) {
  const [currentView, setCurrentView] = useState('month');
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [showStandard, setShowStandard] = useState(true);
  const [showOverride, setShowOverride] = useState(true);

  const scheduleEvents = useMemo(() => {
    const events = scheduleToEvents(schedules || [], {});
    console.log('[ScheduleCalendar] Schedules → events:', {
      scheduleCount: (schedules || []).length,
      eventCount: events.length,
      sampleEvent: events[0],
    });
    return events;
  }, [schedules]);

  const holidayEvents = (holidays || []).map((holiday) => {
    const dateStr = holiday.date || holiday.Date || '';
    const holidayDate = new Date(dateStr);
    return {
      id: 'holiday-' + dateStr + '-' + (holiday.country || ''),
      title: holiday.name || holiday.Name || 'Public Holiday',
      start: holidayDate,
      end: holidayDate,
      allDay: true,
      resource: { type: 'holiday', ...holiday },
    };
  });

  const filteredScheduleEvents = useMemo(() => {
    return scheduleEvents.filter((e) => {
      const r = e.resource;
      if (!r || (r.type !== 'order' && r.type !== 'delivery')) return true;
      if (r.isOverride) return showOverride;
      return showStandard;
    });
  }, [scheduleEvents, showStandard, showOverride]);

  const allEvents = [...filteredScheduleEvents, ...holidayEvents];

  useEffect(() => {
    if (selectedEvent && !allEvents.some((e) => e.id === selectedEvent.id)) {
      setSelectedEvent(null);
    }
  }, [allEvents, selectedEvent]);

  // Resolve selected event to the one in allEvents so resource.orderStartDate is guaranteed
  const selectedEventCanonical = useMemo(
    () => (selectedEvent && allEvents.find((e) => e.id === selectedEvent.id)) || selectedEvent,
    [selectedEvent, allEvents],
  );
  const pairedEvent = useMemo(
    () => (selectedEventCanonical ? findPairedEvent(selectedEventCanonical, allEvents) : null),
    [selectedEventCanonical, allEvents],
  );

  const eventStyleGetter = (event) => {
    const { bg, border } = getEventColor(event, currentView);
    const isSelected = selectedEvent && event.id === selectedEvent.id;
    const isPaired = pairedEvent && event.id === pairedEvent.id;
    const highlight = isSelected || isPaired;
    return {
      style: {
        backgroundColor: bg,
        color: 'white',
        border: border || 'none',
      },
      className: highlight ? 'rbc-event-pair-highlight' : undefined,
    };
  };

  return (
    <div className="schedule-calendar">
      <div className="calendar-header">
        <h2>Delivery Schedules</h2>
        <div className="calendar-header-right">
          <label className="calendar-filter-checkbox">
            <input
              type="checkbox"
              checked={showStandard}
              onChange={(e) => setShowStandard(e.target.checked)}
            />
            <span>Standard</span>
          </label>
          <label className="calendar-filter-checkbox">
            <input
              type="checkbox"
              checked={showOverride}
              onChange={(e) => setShowOverride(e.target.checked)}
            />
            <span>Override</span>
          </label>
          <div className="calendar-legend">
            <span className="legend-item">
              <span
                className="legend-color"
                style={{ backgroundColor: VENDOR_ORDER_COLORS[0] }}
              ></span>
              Order By (std)
            </span>
            <span className="legend-item">
              <span
                className="legend-color"
                style={{ backgroundColor: VENDOR_DELIVERY_COLORS[0] }}
              ></span>
              Delivery (std)
            </span>
            <span className="legend-item legend-dashed" title="Override schedules">
              <span className="legend-color legend-dashed-box"></span>
              Override
            </span>
            <span className="legend-item">
              <span className="legend-color" style={{ backgroundColor: '#ff9800' }}></span>
              Public Holiday
            </span>
          </div>
        </div>
      </div>
      <div className="calendar-container">
        <Calendar
          localizer={localizer}
          events={allEvents}
          startAccessor="start"
          endAccessor="end"
          style={{ height: 600 }}
          eventPropGetter={eventStyleGetter}
          defaultView="month"
          views={['month', 'week', 'day']}
          culture="en-GB"
          onView={setCurrentView}
          onSelectEvent={setSelectedEvent}
          selected={selectedEvent}
        />
      </div>
      {(!schedules || schedules.length === 0) && (
        <div className="calendar-empty">
          <p>No schedules found. Select one location and click &quot;View Schedules&quot;.</p>
        </div>
      )}
      {schedules && schedules.length > 0 && scheduleEvents.length === 0 && (
        <div className="calendar-empty calendar-empty-hint">
          <p>
            Schedule data received ({schedules.length} vendor/location) but no calendar events were
            generated.
          </p>
          <p>Check the browser console (F12) and the debug endpoint below for structure hints.</p>
        </div>
      )}
    </div>
  );
}
