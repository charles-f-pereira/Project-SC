import { useState, useEffect, useMemo } from 'react'
import FilterPanel from '../components/FilterPanel/FilterPanel.jsx'
import ScheduleCalendar from '../components/ScheduleCalendar/ScheduleCalendar.jsx'
import client from '../api/client.js'
import './Dashboard.css'

// Helper function to extract state from a location object
function extractState(loc) {
  // Priority 1: Check in locationNameAddressDetails array (confirmed location)
  if (Array.isArray(loc.locationNameAddressDetails) && loc.locationNameAddressDetails.length > 0) {
    const nameDetails = loc.locationNameAddressDetails[0]
    if (nameDetails?.stateProvince) return nameDetails.stateProvince
    if (nameDetails?.state) return nameDetails.state
    if (nameDetails?.State) return nameDetails.State
  }
  
  // Priority 2: Check in locationDetailDetails array
  if (Array.isArray(loc.locationDetailDetails) && loc.locationDetailDetails.length > 0) {
    const details = loc.locationDetailDetails[0]
    if (details?.stateProvince) return details.stateProvince
    if (details?.state) return details.state
    if (details?.State) return details.State
    if (details?.stateCode) return details.stateCode
    if (details?.StateCode) return details.StateCode
  }
  
  // Priority 3: Check direct state fields
  if (Array.isArray(loc.stateProvince) && loc.stateProvince.length > 0) {
    return loc.stateProvince[0]
  }
  if (loc.stateProvince) return loc.stateProvince
  if (loc.state) return loc.state
  if (loc.State) return loc.State
  if (loc.stateCode) return loc.stateCode
  if (loc.StateCode) return loc.StateCode
  if (loc.stateProvinceCode) return loc.stateProvinceCode
  
  return null
}

export default function Dashboard() {
  const [locations, setLocations] = useState([])
  const [vendors, setVendors] = useState([])
  const [hierarchy, setHierarchy] = useState([])
  const [schedules, setSchedules] = useState([])
  const [holidays, setHolidays] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filter state
  const [filters, setFilters] = useState({
    locations: [],
    vendors: [],
    states: [],
    distributionCenters: [],
    deliveryDays: [],
    orderingDays: []
  })

  // Fetch initial data
  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true)
        setError(null)

        // Fetch all data in parallel
        const [locationsRes, vendorsRes, hierarchyRes, schedulesRes, holidaysRes] = await Promise.all([
          client.get('/api/locations', { params: { activeFlag: true } }).catch(() => ({ data: { data: [] } })),
          client.get('/api/vendors').catch(() => ({ data: { data: [] } })),
          client.get('/api/vendors/hierarchy').catch(() => ({ data: { data: [] } })),
          client.get('/api/schedules/vendor-locations').catch(() => ({ data: { data: [] } })),
          client.get('/api/holidays').catch(() => ({ data: { data: [] } }))
        ])

        setLocations(locationsRes.data.data || [])
        setVendors(vendorsRes.data.data || [])
        setHierarchy(hierarchyRes.data.data || [])
        setSchedules(schedulesRes.data.data || [])
        setHolidays(holidaysRes.data.data || [])
        
        // Debug: Log first location to see structure and find state field
        if (locationsRes.data.data && locationsRes.data.data.length > 0) {
          const firstLoc = locationsRes.data.data[0]
          console.log('First location structure:', firstLoc)
          console.log('All location keys:', Object.keys(firstLoc))
          
          // Handle locationNameAddressDetails as array or object
          let nameDetails = null
          if (Array.isArray(firstLoc.locationNameAddressDetails) && firstLoc.locationNameAddressDetails.length > 0) {
            nameDetails = firstLoc.locationNameAddressDetails[0]
            console.log('locationNameAddressDetails[0]:', nameDetails)
          } else if (firstLoc.locationNameAddressDetails && typeof firstLoc.locationNameAddressDetails === 'object') {
            nameDetails = firstLoc.locationNameAddressDetails
          }
          console.log('Location name:', nameDetails?.locationName)
          
          // Check all possible state fields
          console.log('Checking state fields:')
          console.log('  stateProvince:', firstLoc.stateProvince)
          console.log('  state:', firstLoc.state)
          console.log('  State:', firstLoc.State)
          console.log('  stateCode:', firstLoc.stateCode)
          console.log('  StateCode:', firstLoc.StateCode)
          console.log('  stateProvinceCode:', firstLoc.stateProvinceCode)
          
          // Check if state is in locationDetailDetails array
          if (Array.isArray(firstLoc.locationDetailDetails) && firstLoc.locationDetailDetails.length > 0) {
            console.log('locationDetailDetails[0]:', firstLoc.locationDetailDetails[0])
            console.log('  stateProvince in details:', firstLoc.locationDetailDetails[0]?.stateProvince)
            console.log('  state in details:', firstLoc.locationDetailDetails[0]?.state)
          }
        }
      } catch (err) {
        console.error('Error fetching data:', err)
        setError(err.message || 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // Extract unique states from locations
  const availableStates = useMemo(() => {
    const states = new Set()
    locations.forEach(loc => {
      const state = extractState(loc)
      if (state) {
        const stateStr = typeof state === 'string' ? state.trim() : String(state).trim()
        if (stateStr.length > 0) {
          states.add(stateStr)
        }
      }
    })
    
    const statesArray = Array.from(states).sort()
    console.log('Extracted states:', statesArray)
    return statesArray
  }, [locations])

  // Extract distribution centers from hierarchy
  const availableDCs = useMemo(() => {
    const dcs = new Set()
    hierarchy.forEach(item => {
      if (item.distributionCenterCode) dcs.add(item.distributionCenterCode)
      if (item.dcCode) dcs.add(item.dcCode)
    })
    return Array.from(dcs).sort()
  }, [hierarchy])

  // Filter schedules based on current filters
  const filteredSchedules = useMemo(() => {
    let filtered = [...schedules]

    if (filters.locations.length > 0) {
      filtered = filtered.filter(s => {
        const sCode = s.locationCode || s.LocationCode || s.code || s.Code
        return filters.locations.includes(sCode)
      })
    }

    if (filters.vendors.length > 0) {
      filtered = filtered.filter(s => {
        const vCode = s.vendorCode || s.VendorCode || s.vendor || s.Vendor
        return filters.vendors.includes(vCode)
      })
    }

    if (filters.distributionCenters.length > 0) {
      filtered = filtered.filter(s => 
        filters.distributionCenters.includes(s.distributionCenterCode) ||
        filters.distributionCenters.includes(s.dcCode)
      )
    }

    // State filter (requires location lookup)
    if (filters.states.length > 0) {
      const locationCodesInStates = new Set()
      locations.forEach(loc => {
        const state = extractState(loc)
        const code = loc.code || loc.locationCode || loc.Code
        if (state) {
          const stateStr = typeof state === 'string' ? state.trim() : String(state).trim()
          if (stateStr.length > 0 && filters.states.includes(stateStr)) {
            locationCodesInStates.add(code)
          }
        }
      })
      filtered = filtered.filter(s => {
        const sCode = s.locationCode || s.LocationCode || s.code || s.Code
        return locationCodesInStates.has(sCode)
      })
    }

    // Day filters would be applied here based on schedule details
    // This requires understanding the schedule structure

    return filtered
  }, [schedules, filters, locations])

  if (loading) {
    return (
      <div className="dashboard-loading">
        <p>Loading schedule data...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="dashboard-error">
        <p>Error: {error}</p>
        <p>Please check your API configuration and ensure the backend is running.</p>
      </div>
    )
  }

  return (
    <div className="dashboard">
      <div className="dashboard-content">
        <FilterPanel
          locations={locations}
          vendors={vendors}
          states={availableStates}
          distributionCenters={availableDCs}
          filters={filters}
          onFiltersChange={setFilters}
        />
        <div className="dashboard-calendar-section">
          <ScheduleCalendar
            schedules={filteredSchedules}
            holidays={holidays}
            filters={filters}
          />
        </div>
      </div>
    </div>
  )
}
