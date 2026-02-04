import { Calendar, momentLocalizer } from 'react-big-calendar'
import moment from 'moment'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import 'moment/locale/en-gb'
import './ScheduleCalendar.css'

// Set Monday as first day of week (en-gb default, but explicit for clarity)
moment.locale('en-gb', { week: { dow: 1 } })

const localizer = momentLocalizer(moment)

export default function ScheduleCalendar({ schedules, holidays, filters }) {
  // Convert schedules to calendar events
  const events = schedules.map((schedule, index) => {
    // This is a placeholder - actual implementation depends on schedule structure
    // You'll need to parse vendorLocationScheduleDetail to extract dates/times
    const baseDate = new Date()
    baseDate.setDate(baseDate.getDate() + (index % 30)) // Placeholder dates
    
    return {
      id: schedule.locationCode + '-' + schedule.vendorCode + '-' + index,
      title: `${schedule.locationCode || 'Location'} - ${schedule.vendorCode || 'Vendor'}`,
      start: baseDate,
      end: new Date(baseDate.getTime() + 2 * 60 * 60 * 1000), // 2 hours
      resource: schedule
    }
  })

  // Mark holidays on calendar (handle date/Date and name/Name from API)
  const holidayEvents = (holidays || []).map(holiday => {
    const dateStr = holiday.date || holiday.Date || ''
    const holidayDate = new Date(dateStr)
    return {
      id: 'holiday-' + dateStr + '-' + (holiday.country || ''),
      title: holiday.name || holiday.Name || 'Public Holiday',
      start: holidayDate,
      end: holidayDate,
      allDay: true,
      resource: { type: 'holiday', ...holiday }
    }
  })

  const allEvents = [...events, ...holidayEvents]

  const eventStyleGetter = (event) => {
    if (event.resource?.type === 'holiday') {
      return {
        style: {
          backgroundColor: '#ff9800',
          color: 'white',
          border: 'none'
        }
      }
    }
    return {
      style: {
        backgroundColor: '#3498db',
        color: 'white',
        border: 'none'
      }
    }
  }

  return (
    <div className="schedule-calendar">
      <div className="calendar-header">
        <h2>Delivery Schedules</h2>
        <div className="calendar-legend">
          <span className="legend-item">
            <span className="legend-color" style={{ backgroundColor: '#3498db' }}></span>
            Delivery Schedule
          </span>
          <span className="legend-item">
            <span className="legend-color" style={{ backgroundColor: '#ff9800' }}></span>
            Public Holiday
          </span>
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
        />
      </div>
      {schedules.length === 0 && (
        <div className="calendar-empty">
          <p>No schedules found. Adjust your filters or check API configuration.</p>
        </div>
      )}
    </div>
  )
}
