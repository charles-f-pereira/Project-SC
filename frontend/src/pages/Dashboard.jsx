import { useState, useEffect, useMemo } from 'react'
import FilterPanel from '../components/FilterPanel/FilterPanel.jsx'
import ScheduleCalendar from '../components/ScheduleCalendar/ScheduleCalendar.jsx'
import client from '../api/client.js'
import './Dashboard.css'

// Helper function to extract country from a location object
function extractCountry(loc) {
  // Priority 1: Check in locationNameAddressDetails array
  if (Array.isArray(loc.locationNameAddressDetails) && loc.locationNameAddressDetails.length > 0) {
    const nameDetails = loc.locationNameAddressDetails[0]
    if (nameDetails?.country) return nameDetails.country
    if (nameDetails?.Country) return nameDetails.Country
  }
  
  // Priority 2: Check direct country fields
  if (loc.country) return loc.country
  if (loc.Country) return loc.Country
  
  return null
}

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

// Map display country names to API country codes for public holidays
const COUNTRY_NAME_TO_CODE = {
  'Australia': 'AU',
  'United States': 'US',
  'USA': 'US',
  'United States of America': 'US'
}

export default function Dashboard() {
  const [locations, setLocations] = useState([])
  const [vendors, setVendors] = useState([])
  const [hierarchy, setHierarchy] = useState([])
  const [schedules, setSchedules] = useState([])
  const [holidays, setHolidays] = useState([])
  const [loading, setLoading] = useState(true)
  const [holidaysLoading, setHolidaysLoading] = useState(false)
  const [holidaysError, setHolidaysError] = useState(null)
  const [schedulesLoading, setSchedulesLoading] = useState(false)
  const [schedulesError, setSchedulesError] = useState(null)
  const [error, setError] = useState(null)

  // Filter state
  const [filters, setFilters] = useState({
    countries: [],
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

        // Fetch locations and vendors (hierarchy is fetched only when a single vendor is selected)
        const [locationsRes, vendorsRes] = await Promise.all([
          client.get('/api/locations', { params: { activeFlag: true } }).catch(() => ({ data: { data: [] } })),
          client.get('/api/vendors', { params: { activeFlag: true } }).catch(() => ({ data: { data: [] } }))
        ])

        const locations = locationsRes.data.data || []
        const vendors = vendorsRes.data.data || []

        setLocations(locations)
        setVendors(vendors)
      } catch (err) {
        console.error('Error fetching data:', err)
        setError(err.message || 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // Fetch hierarchy only when a single vendor is selected (for Distribution Centers filter)
  useEffect(() => {
    if (!filters.vendors || filters.vendors.length !== 1 || vendors.length === 0) {
      setHierarchy([])
      return
    }
    const vendorCode = filters.vendors[0]
    const vendor = vendors.find(
      (v) => (v.supplyCode || v.code || v.vendorCode || v.Code || '').toString().trim() === vendorCode.toString().trim()
    )
    const supplyCode = vendor ? (vendor.supplyCode || vendor.code || vendor.vendorCode || vendor.Code || '').toString().trim() : vendorCode
    if (!supplyCode) {
      setHierarchy([])
      return
    }
    const hierarchyType = `3-AU Supply Chain - ${supplyCode}`
    let cancelled = false
    client
      .get('/api/vendors/hierarchy', { params: { hierarchyType, levelNumber: 3 } })
      .then((res) => {
        if (!cancelled) setHierarchy(res.data?.data || [])
      })
      .catch(() => {
        if (!cancelled) setHierarchy([])
      })
    return () => { cancelled = true }
  }, [filters.vendors, vendors])

  // Extract unique countries from locations
  const availableCountries = useMemo(() => {
    const countries = new Set()
    locations.forEach(loc => {
      const country = extractCountry(loc)
      if (country) {
        const countryStr = typeof country === 'string' ? country.trim() : String(country).trim()
        if (countryStr.length > 0) {
          countries.add(countryStr)
        }
      }
    })
    
    const countriesArray = Array.from(countries).sort()
    console.log('Extracted countries:', countriesArray)
    return countriesArray
  }, [locations])

  // Extract unique states from locations (filtered by selected countries if any)
  const availableStates = useMemo(() => {
    const states = new Set()
    locations.forEach(loc => {
      // If countries are selected, only include states from those countries
      if (filters.countries && filters.countries.length > 0) {
        const locCountry = extractCountry(loc)
        if (locCountry) {
          const countryStr = typeof locCountry === 'string' ? locCountry.trim() : String(locCountry).trim()
          if (!filters.countries.includes(countryStr)) {
            return // Skip locations not in selected countries
          }
        } else {
          return // Skip locations without country if countries are filtered
        }
      }
      
      // Extract state from location
      const state = extractState(loc)
      if (state) {
        const stateStr = typeof state === 'string' ? state.trim() : String(state).trim()
        if (stateStr.length > 0) {
          states.add(stateStr)
        }
      }
    })
    
    const statesArray = Array.from(states).sort()
    console.log('Extracted states (filtered by countries):', statesArray)
    return statesArray
  }, [locations, filters.countries])

  // Extract distribution centers from hierarchy (levelNumber: 3, use parentLogicalName)
  // Also build a map of distribution center -> location codes for filtering
  const { availableDCs, dcToLocationCodes } = useMemo(() => {
    const dcs = new Set()
    const dcLocationMap = new Map() // Map of distribution center name -> Set of location codes
    
    hierarchy.forEach(item => {
      // Only process items with levelNumber: 3
      if (item.levelNumber === 3 || item.levelNumber === '3') {
        const dcName = item.parentLogicalName || item.distributionCenterCode || item.dcCode || ''
        const locationCode = item.locationCode || item.LocationCode || item.code || item.Code || ''
        
        if (dcName) {
          dcs.add(dcName)
          
          // Build mapping of DC to location codes
          if (locationCode) {
            if (!dcLocationMap.has(dcName)) {
              dcLocationMap.set(dcName, new Set())
            }
            dcLocationMap.get(dcName).add(locationCode)
          }
        }
      }
    })
    
    return {
      availableDCs: Array.from(dcs).sort(),
      dcToLocationCodes: dcLocationMap
    }
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

    // Distribution Centers filter (requires hierarchy lookup)
    if (filters.distributionCenters.length > 0) {
      const locationCodesInDCs = new Set()
      filters.distributionCenters.forEach(dcName => {
        const locationCodes = dcToLocationCodes.get(dcName)
        if (locationCodes) {
          locationCodes.forEach(code => locationCodesInDCs.add(code))
        }
      })
      filtered = filtered.filter(s => {
        const sCode = s.locationCode || s.LocationCode || s.code || s.Code
        return locationCodesInDCs.has(sCode)
      })
    }

    // Country filter (requires location lookup)
    if (filters.countries.length > 0) {
      const locationCodesInCountries = new Set()
      locations.forEach(loc => {
        const country = extractCountry(loc)
        const code = loc.code || loc.locationCode || loc.Code
        if (country) {
          const countryStr = typeof country === 'string' ? country.trim() : String(country).trim()
          if (countryStr.length > 0 && filters.countries.includes(countryStr)) {
            locationCodesInCountries.add(code)
          }
        }
      })
      filtered = filtered.filter(s => {
        const sCode = s.locationCode || s.LocationCode || s.code || s.Code
        return locationCodesInCountries.has(sCode)
      })
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
  }, [schedules, filters, locations, dcToLocationCodes])

  // Filter holidays by selected countries (show only holidays for selected countries)
  const filteredHolidays = useMemo(() => {
    if (!filters.countries || filters.countries.length === 0) {
      return holidays
    }
    const codesForSelected = new Set()
    filters.countries.forEach(name => {
      const code = COUNTRY_NAME_TO_CODE[name] || name
      if (code === 'AU' || code === 'US') codesForSelected.add(code)
    })
    if (codesForSelected.size === 0) return holidays
    return holidays.filter(h => codesForSelected.has(h.country || (h.Country || '').toUpperCase()))
  }, [holidays, filters.countries])

  const fetchPublicHolidays = async () => {
    try {
      setHolidaysLoading(true)
      setHolidaysError(null)
      const res = await client.get('/api/holidays/fetch', { params: { countries: 'AU,US' } })
      const data = res.data?.data || []
      setHolidays(data)
    } catch (err) {
      console.error('Error fetching public holidays:', err)
      setHolidaysError(err.response?.data?.detail || err.message || 'Failed to fetch public holidays')
    } finally {
      setHolidaysLoading(false)
    }
  }

  // Single-location fetch: one locationCode only (backend returns all vendors for that location)
  const scheduleFetchParams = useMemo(() => {
    if (!filters.locations?.length || filters.locations.length !== 1) return {}
    return { locationCode: filters.locations[0].trim() }
  }, [filters.locations])

  const fetchSchedules = async () => {
    setSchedulesError(null)
    if (!filters.locations?.length) {
      setSchedulesError('Please select exactly one location.')
      return
    }
    if (filters.locations.length !== 1) {
      setSchedulesError('Please select exactly one location (single location only for now).')
      return
    }
    try {
      setSchedulesLoading(true)
      const res = await client.get('/api/schedules/vendor-locations', { params: scheduleFetchParams })
      let data = res.data?.data || []
      console.log('[View Schedules] API response:', { count: data.length, firstKeys: data[0] ? Object.keys(data[0]) : [], sample: data[0] })
      // Optional: filter by selected vendors client-side
      if (filters.vendors?.length) {
        const vendSet = new Set(filters.vendors)
        data = data.filter(item => {
          const v = item.vendorCode || item.VendorCode || item.vendor || ''
          return vendSet.has(String(v).trim())
        })
        console.log('[View Schedules] After vendor filter:', data.length)
      }
      setSchedules(data)
    } catch (err) {
      console.error('Error fetching schedules:', err)
      setSchedulesError(err.response?.data?.detail || err.message || 'Failed to fetch schedules')
    } finally {
      setSchedulesLoading(false)
    }
  }

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
          countries={availableCountries}
          states={availableStates}
          distributionCenters={availableDCs}
          dcToLocationCodes={dcToLocationCodes}
          filters={filters}
          onFiltersChange={setFilters}
          onViewSchedules={fetchSchedules}
          schedulesLoading={schedulesLoading}
        />
        <div className="dashboard-calendar-section">
          <div className="calendar-actions">
            <button
              onClick={fetchPublicHolidays}
              disabled={holidaysLoading}
              className="fetch-ph-btn"
              title="Fetch public holidays for Australia and USA"
            >
              {holidaysLoading ? 'Fetching...' : 'Fetch PH data'}
            </button>
            {holidaysError && (
              <span className="holidays-error">{holidaysError}</span>
            )}
            {schedulesError && (
              <span className="holidays-error">{schedulesError}</span>
            )}
          </div>
          <ScheduleCalendar
            schedules={filteredSchedules}
            holidays={filteredHolidays}
            filters={filters}
          />
        </div>
      </div>
    </div>
  )
}
