import { useState, useMemo } from 'react'
import './FilterPanel.css'

const DAYS_OF_WEEK = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' }
]

// Helper function to extract state from a location object (same as Dashboard)
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

export default function FilterPanel({ locations, vendors, states, distributionCenters, filters, onFiltersChange }) {
  const [locationSearch, setLocationSearch] = useState('')
  const [vendorSearch, setVendorSearch] = useState('')
  
  // Track which filter sections are expanded (default: all collapsed)
  const [expandedSections, setExpandedSections] = useState({
    states: false,
    locations: false,
    vendors: false,
    distributionCenters: false,
    deliveryDays: false,
    orderingDays: false
  })
  
  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  // Filter locations by state first, then by search term
  const filteredLocations = useMemo(() => {
    return locations.filter(loc => {
      // Filter by state if states are selected
      if (filters.states && filters.states.length > 0) {
        const locState = extractState(loc)
        if (locState) {
          const stateStr = typeof locState === 'string' ? locState.trim() : String(locState).trim()
          if (!filters.states.includes(stateStr)) {
            return false // Exclude if state doesn't match
          }
        } else {
          return false // Exclude if no state found and states are filtered
        }
      }
      
      // Filter by search term
      if (!locationSearch) return true
      const searchLower = locationSearch.toLowerCase()
      
      // Handle locationNameAddressDetails as array or object
      let nameDetails = null
      if (Array.isArray(loc.locationNameAddressDetails) && loc.locationNameAddressDetails.length > 0) {
        nameDetails = loc.locationNameAddressDetails[0]
      } else if (loc.locationNameAddressDetails && typeof loc.locationNameAddressDetails === 'object') {
        nameDetails = loc.locationNameAddressDetails
      }
      
      const name = (nameDetails?.locationName || loc.name || loc.locationName || loc.Name || loc.description || loc.Description || '').toString().toLowerCase()
      const code = (loc.code || loc.locationCode || loc.Code || '').toString().toLowerCase()
      return name.includes(searchLower) || code.includes(searchLower)
    })
  }, [locations, filters.states, locationSearch])

  const filteredVendors = vendors.filter(v => {
    if (!vendorSearch) return true
    const searchLower = vendorSearch.toLowerCase()
    const name = (v.name || v.vendorName || v.Name || v.description || v.Description || '').toLowerCase()
    const code = (v.code || v.vendorCode || v.Code || '').toLowerCase()
    return name.includes(searchLower) || code.includes(searchLower)
  })

  const handleMultiSelect = (filterKey, value, checked) => {
    const currentValues = filters[filterKey] || []
    if (checked) {
      onFiltersChange({
        ...filters,
        [filterKey]: [...currentValues, value]
      })
    } else {
      onFiltersChange({
        ...filters,
        [filterKey]: currentValues.filter(v => v !== value)
      })
    }
  }

  const handleDayToggle = (dayType, dayValue, checked) => {
    const currentDays = filters[dayType] || []
    if (checked) {
      onFiltersChange({
        ...filters,
        [dayType]: [...currentDays, dayValue]
      })
    } else {
      onFiltersChange({
        ...filters,
        [dayType]: currentDays.filter(d => d !== dayValue)
      })
    }
  }

  const clearFilters = () => {
    onFiltersChange({
      locations: [],
      vendors: [],
      states: [],
      distributionCenters: [],
      deliveryDays: [],
      orderingDays: []
    })
  }

  const hasActiveFilters = Object.values(filters).some(arr => Array.isArray(arr) && arr.length > 0)
  
  // Helper to get active filter count for a section
  const getActiveFilterCount = (filterKey) => {
    const filterValues = filters[filterKey] || []
    return Array.isArray(filterValues) ? filterValues.length : 0
  }

  // Calculate the number of locations filtered by selected states
  const stateFilteredLocationCount = useMemo(() => {
    if (!filters.states || filters.states.length === 0) {
      return null // No state filter applied
    }
    
    return locations.filter(loc => {
      const locState = extractState(loc)
      if (locState) {
        const stateStr = typeof locState === 'string' ? locState.trim() : String(locState).trim()
        return filters.states.includes(stateStr)
      }
      return false
    }).length
  }, [locations, filters.states])

  return (
    <div className="filter-panel">
      <div className="filter-panel-header">
        <h2>Filters</h2>
        {hasActiveFilters && (
          <button onClick={clearFilters} className="clear-filters-btn">
            Clear All
          </button>
        )}
      </div>

      {/* States filter - moved to top */}
      <div className="filter-section">
        <div className="filter-section-header" onClick={() => toggleSection('states')}>
          <div className="filter-section-title">
            <h3>
              States
              {stateFilteredLocationCount !== null && (
                <span className="filter-location-count"> ({stateFilteredLocationCount} location{stateFilteredLocationCount !== 1 ? 's' : ''})</span>
              )}
            </h3>
            {getActiveFilterCount('states') > 0 && (
              <span className="filter-badge">{getActiveFilterCount('states')}</span>
            )}
          </div>
          <span className="filter-toggle-icon">{expandedSections.states ? '▼' : '▶'}</span>
        </div>
        {expandedSections.states && (
          <div className="filter-checkbox-list">
            {states.map(state => (
              <label key={state} className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={filters.states.includes(state)}
                  onChange={(e) => handleMultiSelect('states', state, e.target.checked)}
                />
                <span>{state}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Locations filter - moved to second position */}
      <div className="filter-section">
        <div className="filter-section-header" onClick={() => toggleSection('locations')}>
          <div className="filter-section-title">
            <h3>Locations</h3>
            {getActiveFilterCount('locations') > 0 && (
              <span className="filter-badge">{getActiveFilterCount('locations')}</span>
            )}
          </div>
          <span className="filter-toggle-icon">{expandedSections.locations ? '▼' : '▶'}</span>
        </div>
        {expandedSections.locations && (
          <>
            <input
              type="text"
              placeholder="Search locations..."
              value={locationSearch}
              onChange={(e) => setLocationSearch(e.target.value)}
              className="filter-search"
            />
            <div className="filter-checkbox-list">
              {filteredLocations.slice(0, 50).map((loc, index) => {
                const locationCode = loc.code || loc.locationCode || loc.Code || loc.LocationCode || ''
                
                // Handle locationNameAddressDetails as array or object
                let nameDetails = null
                if (Array.isArray(loc.locationNameAddressDetails) && loc.locationNameAddressDetails.length > 0) {
                  nameDetails = loc.locationNameAddressDetails[0]
                } else if (Array.isArray(loc.LocationNameAddressDetails) && loc.LocationNameAddressDetails.length > 0) {
                  nameDetails = loc.LocationNameAddressDetails[0]
                } else if (loc.locationNameAddressDetails && typeof loc.locationNameAddressDetails === 'object') {
                  nameDetails = loc.locationNameAddressDetails
                } else if (loc.LocationNameAddressDetails && typeof loc.LocationNameAddressDetails === 'object') {
                  nameDetails = loc.LocationNameAddressDetails
                }
                
                // Try multiple variations of the locationName field
                const locationName = (nameDetails?.locationName 
                  || nameDetails?.LocationName 
                  || nameDetails?.name
                  || nameDetails?.Name
                  || loc.name 
                  || loc.locationName 
                  || loc.LocationName
                  || loc.Name 
                  || loc.description 
                  || loc.Description 
                  || '').toString().trim()
                
                // Use locationName if it exists and is not empty, otherwise fall back to code
                const displayText = (locationName && locationName.length > 0) ? locationName : locationCode
                
                return (
                  <label key={locationCode || `location-${index}`} className="filter-checkbox">
                    <input
                      type="checkbox"
                      checked={filters.locations.includes(locationCode)}
                      onChange={(e) => handleMultiSelect('locations', locationCode, e.target.checked)}
                    />
                    <span>{displayText}</span>
                  </label>
                )
              })}
              {filteredLocations.length > 50 && (
                <p className="filter-note">Showing first 50 of {filteredLocations.length} locations</p>
              )}
            </div>
          </>
        )}
      </div>

      {/* Vendors filter */}
      <div className="filter-section">
        <div className="filter-section-header" onClick={() => toggleSection('vendors')}>
          <div className="filter-section-title">
            <h3>Vendors</h3>
            {getActiveFilterCount('vendors') > 0 && (
              <span className="filter-badge">{getActiveFilterCount('vendors')}</span>
            )}
          </div>
          <span className="filter-toggle-icon">{expandedSections.vendors ? '▼' : '▶'}</span>
        </div>
        {expandedSections.vendors && (
          <>
            <input
              type="text"
              placeholder="Search vendors..."
              value={vendorSearch}
              onChange={(e) => setVendorSearch(e.target.value)}
              className="filter-search"
            />
            <div className="filter-checkbox-list">
              {filteredVendors.map(vendor => {
                const vendorCode = vendor.code || vendor.vendorCode || vendor.Code || ''
                const vendorName = vendor.name || vendor.vendorName || vendor.Name || vendor.description || vendor.Description || ''
                const displayText = vendorName || vendorCode || 'Unknown Vendor'
                return (
                  <label key={vendorCode} className="filter-checkbox">
                    <input
                      type="checkbox"
                      checked={filters.vendors.includes(vendorCode)}
                      onChange={(e) => handleMultiSelect('vendors', vendorCode, e.target.checked)}
                    />
                    <span>{displayText}</span>
                  </label>
                )
              })}
            </div>
          </>
        )}
      </div>

      {/* Distribution Centers filter */}
      <div className="filter-section">
        <div className="filter-section-header" onClick={() => toggleSection('distributionCenters')}>
          <div className="filter-section-title">
            <h3>Distribution Centers</h3>
            {getActiveFilterCount('distributionCenters') > 0 && (
              <span className="filter-badge">{getActiveFilterCount('distributionCenters')}</span>
            )}
          </div>
          <span className="filter-toggle-icon">{expandedSections.distributionCenters ? '▼' : '▶'}</span>
        </div>
        {expandedSections.distributionCenters && (
          <div className="filter-checkbox-list">
            {distributionCenters.map(dc => (
              <label key={dc} className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={filters.distributionCenters.includes(dc)}
                  onChange={(e) => handleMultiSelect('distributionCenters', dc, e.target.checked)}
                />
                <span>{dc}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Ordering Days filter */}
      <div className="filter-section">
        <div className="filter-section-header" onClick={() => toggleSection('orderingDays')}>
          <div className="filter-section-title">
            <h3>Ordering Days</h3>
            {getActiveFilterCount('orderingDays') > 0 && (
              <span className="filter-badge">{getActiveFilterCount('orderingDays')}</span>
            )}
          </div>
          <span className="filter-toggle-icon">{expandedSections.orderingDays ? '▼' : '▶'}</span>
        </div>
        {expandedSections.orderingDays && (
          <div className="filter-checkbox-list">
            {DAYS_OF_WEEK.map(day => (
              <label key={day.value} className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={filters.orderingDays.includes(day.value)}
                  onChange={(e) => handleDayToggle('orderingDays', day.value, e.target.checked)}
                />
                <span>{day.label}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Delivery Days filter */}
      <div className="filter-section">
        <div className="filter-section-header" onClick={() => toggleSection('deliveryDays')}>
          <div className="filter-section-title">
            <h3>Delivery Days</h3>
            {getActiveFilterCount('deliveryDays') > 0 && (
              <span className="filter-badge">{getActiveFilterCount('deliveryDays')}</span>
            )}
          </div>
          <span className="filter-toggle-icon">{expandedSections.deliveryDays ? '▼' : '▶'}</span>
        </div>
        {expandedSections.deliveryDays && (
          <div className="filter-checkbox-list">
            {DAYS_OF_WEEK.map(day => (
              <label key={day.value} className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={filters.deliveryDays.includes(day.value)}
                  onChange={(e) => handleDayToggle('deliveryDays', day.value, e.target.checked)}
                />
                <span>{day.label}</span>
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
