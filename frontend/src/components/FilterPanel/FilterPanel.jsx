import { useState, useMemo, useEffect } from 'react';
import './FilterPanel.css';

const DAYS_OF_WEEK = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' },
];

// Helper function to extract country from a location object (same as Dashboard)
function extractCountry(loc) {
  // Priority 1: Check in locationNameAddressDetails array
  if (Array.isArray(loc.locationNameAddressDetails) && loc.locationNameAddressDetails.length > 0) {
    const nameDetails = loc.locationNameAddressDetails[0];
    if (nameDetails?.country) return nameDetails.country;
    if (nameDetails?.Country) return nameDetails.Country;
  }

  // Priority 2: Check direct country fields
  if (loc.country) return loc.country;
  if (loc.Country) return loc.Country;

  return null;
}

// Helper function to extract state from a location object (same as Dashboard)
function extractState(loc) {
  // Priority 1: Check in locationNameAddressDetails array (confirmed location)
  if (Array.isArray(loc.locationNameAddressDetails) && loc.locationNameAddressDetails.length > 0) {
    const nameDetails = loc.locationNameAddressDetails[0];
    if (nameDetails?.stateProvince) return nameDetails.stateProvince;
    if (nameDetails?.state) return nameDetails.state;
    if (nameDetails?.State) return nameDetails.State;
  }

  // Priority 2: Check in locationDetailDetails array
  if (Array.isArray(loc.locationDetailDetails) && loc.locationDetailDetails.length > 0) {
    const details = loc.locationDetailDetails[0];
    if (details?.stateProvince) return details.stateProvince;
    if (details?.state) return details.state;
    if (details?.State) return details.State;
    if (details?.stateCode) return details.stateCode;
    if (details?.StateCode) return details.StateCode;
  }

  // Priority 3: Check direct state fields
  if (Array.isArray(loc.stateProvince) && loc.stateProvince.length > 0) {
    return loc.stateProvince[0];
  }
  if (loc.stateProvince) return loc.stateProvince;
  if (loc.state) return loc.state;
  if (loc.State) return loc.State;
  if (loc.stateCode) return loc.stateCode;
  if (loc.StateCode) return loc.StateCode;
  if (loc.stateProvinceCode) return loc.stateProvinceCode;

  return null;
}

// Extract market from location (locationDetailDetails[].market) - each location has 1 market
function extractMarket(loc) {
  if (Array.isArray(loc.locationDetailDetails) && loc.locationDetailDetails.length > 0) {
    const details = loc.locationDetailDetails[0];
    const m = details?.market ?? details?.Market;
    if (m !== undefined && m !== null && m !== '') return String(m).trim();
  }
  if (loc.market !== undefined && loc.market !== null && loc.market !== '')
    return String(loc.market).trim();
  if (loc.Market !== undefined && loc.Market !== null && loc.Market !== '')
    return String(loc.Market).trim();
  return null;
}

export default function FilterPanel({
  locations,
  vendors,
  countries,
  states,
  markets,
  distributionCenters,
  dcToLocationCodes,
  filters,
  onFiltersChange,
  onViewSchedules,
  schedulesLoading,
  hideDayFilters = false,
  showViewSchedules = true,
  hierarchyLocationCodes = null,
}) {
  const [locationSearch, setLocationSearch] = useState('');
  const [vendorSearch, setVendorSearch] = useState('');
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Track which filter sections are expanded (default: all collapsed)
  const [expandedSections, setExpandedSections] = useState({
    markets: false,
    countries: false,
    states: false,
    locations: false,
    vendors: false,
    distributionCenters: false,
    deliveryDays: false,
    orderingDays: false,
  });

  const toggleSection = (section) => {
    setExpandedSections((prev) => {
      const isCurrentlyExpanded = prev[section];
      if (isCurrentlyExpanded) {
        // Clicking the open section: just collapse it
        return { ...prev, [section]: false };
      }
      // Opening a section: collapse all others and expand this one
      return {
        markets: false,
        countries: false,
        states: false,
        locations: false,
        vendors: false,
        distributionCenters: false,
        deliveryDays: false,
        orderingDays: false,
        [section]: true,
      };
    });
  };

  const toggleAllSections = () => {
    const anyExpanded = Object.values(expandedSections).some((expanded) => expanded === true);
    const newState = !anyExpanded;
    setExpandedSections({
      markets: newState,
      countries: newState,
      states: newState,
      locations: newState,
      vendors: newState,
      distributionCenters: newState,
      deliveryDays: newState,
      orderingDays: newState,
    });
  };

  // Filter locations by country first, then state, then distribution centers, then by search term
  const filteredLocations = useMemo(() => {
    // Build set of location codes that belong to selected distribution centers
    const locationCodesInDCs = new Set();
    if (
      filters.distributionCenters &&
      filters.distributionCenters.length > 0 &&
      dcToLocationCodes
    ) {
      filters.distributionCenters.forEach((dcName) => {
        const locationCodes = dcToLocationCodes.get(dcName);
        if (locationCodes) {
          locationCodes.forEach((code) => locationCodesInDCs.add(code));
        }
      });
    }

    return locations.filter((loc) => {
      // Exclude location with code "000000"
      const locationCode = loc.code || loc.locationCode || loc.Code || loc.LocationCode || '';
      if (locationCode === '000000') {
        return false;
      }

      // Filter by market if markets are selected (each location has 1 market)
      if (filters.markets && filters.markets.length > 0) {
        const locMarket = extractMarket(loc);
        if (locMarket) {
          const marketStr =
            typeof locMarket === 'string' ? locMarket.trim() : String(locMarket).trim();
          if (marketStr.length > 0 && !filters.markets.includes(marketStr)) {
            return false;
          }
        } else {
          return false;
        }
      }

      // Filter by country if countries are selected
      if (filters.countries && filters.countries.length > 0) {
        const locCountry = extractCountry(loc);
        if (locCountry) {
          const countryStr =
            typeof locCountry === 'string' ? locCountry.trim() : String(locCountry).trim();
          if (!filters.countries.includes(countryStr)) {
            return false; // Exclude if country doesn't match
          }
        } else {
          return false; // Exclude if no country found and countries are filtered
        }
      }

      // Filter by state if states are selected
      if (filters.states && filters.states.length > 0) {
        const locState = extractState(loc);
        if (locState) {
          const stateStr = typeof locState === 'string' ? locState.trim() : String(locState).trim();
          if (!filters.states.includes(stateStr)) {
            return false; // Exclude if state doesn't match
          }
        } else {
          return false; // Exclude if no state found and states are filtered
        }
      }

      // Filter by distribution centers if distribution centers are selected
      if (filters.distributionCenters && filters.distributionCenters.length > 0) {
        if (!locationCodesInDCs.has(locationCode)) {
          return false; // Exclude if location code is not in selected distribution centers
        }
      }

      // Filter by search term
      if (!locationSearch) return true;
      const searchLower = locationSearch.toLowerCase();

      // Handle locationNameAddressDetails as array or object
      let nameDetails = null;
      if (
        Array.isArray(loc.locationNameAddressDetails) &&
        loc.locationNameAddressDetails.length > 0
      ) {
        nameDetails = loc.locationNameAddressDetails[0];
      } else if (
        loc.locationNameAddressDetails &&
        typeof loc.locationNameAddressDetails === 'object'
      ) {
        nameDetails = loc.locationNameAddressDetails;
      }

      const name = (
        nameDetails?.locationName ||
        loc.name ||
        loc.locationName ||
        loc.Name ||
        loc.description ||
        loc.Description ||
        ''
      )
        .toString()
        .toLowerCase();
      const code = (loc.code || loc.locationCode || loc.Code || '').toString().toLowerCase();
      return name.includes(searchLower) || code.includes(searchLower);
    });
  }, [
    locations,
    filters.markets,
    filters.countries,
    filters.states,
    filters.distributionCenters,
    dcToLocationCodes,
    locationSearch,
  ]);

  // Set of location codes that pass country/state/market/DC filters (no search) – used for "Select all" and to prune invalid selections
  const availableLocationCodes = useMemo(() => {
    const locationCodesInDCs = new Set();
    if (
      filters.distributionCenters &&
      filters.distributionCenters.length > 0 &&
      dcToLocationCodes
    ) {
      filters.distributionCenters.forEach((dcName) => {
        const codes = dcToLocationCodes.get(dcName);
        if (codes) codes.forEach((code) => locationCodesInDCs.add(code));
      });
    }
    const set = new Set();
    locations.forEach((loc) => {
      const locationCode = loc.code || loc.locationCode || loc.Code || loc.LocationCode || '';
      if (locationCode === '000000') return;
      if (filters.markets && filters.markets.length > 0) {
        const locMarket = extractMarket(loc);
        if (!locMarket) return;
        const marketStr = String(locMarket).trim();
        if (marketStr.length === 0 || !filters.markets.includes(marketStr)) return;
      }
      if (filters.countries && filters.countries.length > 0) {
        const locCountry = extractCountry(loc);
        if (!locCountry) return;
        if (!filters.countries.includes(String(locCountry).trim())) return;
      }
      if (filters.states && filters.states.length > 0) {
        const locState = extractState(loc);
        if (!locState) return;
        if (!filters.states.includes(String(locState).trim())) return;
      }
      if (filters.distributionCenters && filters.distributionCenters.length > 0) {
        if (!locationCodesInDCs.has(locationCode)) return;
      }
      set.add(locationCode);
    });
    return set;
  }, [
    locations,
    filters.markets,
    filters.countries,
    filters.states,
    filters.distributionCenters,
    dcToLocationCodes,
  ]);

  // When other filters change, remove any selected location that is no longer available
  useEffect(() => {
    const current = filters.locations || [];
    if (current.length === 0) return;
    const kept = current.filter((code) => availableLocationCodes.has(code));
    if (kept.length !== current.length) {
      onFiltersChange({ ...filters, locations: kept });
    }
  }, [availableLocationCodes, filters, onFiltersChange]);

  const handleLocationsSelectAll = (checked) => {
    if (checked) {
      onFiltersChange({ ...filters, locations: Array.from(availableLocationCodes) });
    } else {
      onFiltersChange({ ...filters, locations: [] });
    }
  };

  // Location codes that match selected state(s) and/or market(s) (for vendor filtering when hierarchy is available)
  const locationCodesInSelectedStateMarket = useMemo(() => {
    if (
      (!filters.states || filters.states.length === 0) &&
      (!filters.markets || filters.markets.length === 0)
    ) {
      return null;
    }
    const set = new Set();
    locations.forEach((loc) => {
      const code = loc.code || loc.locationCode || loc.Code || loc.LocationCode || '';
      if (code === '000000') return;
      if (filters.states && filters.states.length > 0) {
        const locState = extractState(loc);
        if (!locState || !filters.states.includes(String(locState).trim())) return;
      }
      if (filters.markets && filters.markets.length > 0) {
        const locMarket = extractMarket(loc);
        if (!locMarket || !filters.markets.includes(String(locMarket).trim())) return;
      }
      set.add(String(code).trim());
    });
    return set.size ? set : null;
  }, [locations, filters.states, filters.markets]);

  const filteredVendors = useMemo(() => {
    return vendors.filter((v) => {
      const vendorCode =
        v.code || v.vendorCode || v.Code || v.supplyCode || '';
      const vendorCodeStr = String(vendorCode).trim();

      // Filter by country if countries are selected
      if (filters.countries && filters.countries.length > 0) {
        const vendorCountry = v.countryName || v.country || v.Country || v.CountryName || '';
        if (vendorCountry) {
          const countryStr =
            typeof vendorCountry === 'string' ? vendorCountry.trim() : String(vendorCountry).trim();
          if (!filters.countries.includes(countryStr)) {
            return false;
          }
        } else {
          return false;
        }
      }

      // Filter by state/market when we have hierarchy for this vendor (one vendor selected): only show if vendor serves at least one location in selected state/market
      if (
        locationCodesInSelectedStateMarket &&
        hierarchyLocationCodes &&
        hierarchyLocationCodes.size > 0 &&
        filters.vendors &&
        filters.vendors.length === 1 &&
        filters.vendors[0] === vendorCodeStr
      ) {
        const hasOverlap = [...hierarchyLocationCodes].some((code) =>
          locationCodesInSelectedStateMarket.has(code),
        );
        if (!hasOverlap) return false;
      }

      // Filter by search term
      if (!vendorSearch) return true;
      const searchLower = vendorSearch.toLowerCase();
      const name = (
        v.supplyName ||
        v.name ||
        v.vendorName ||
        v.Name ||
        v.description ||
        v.Description ||
        ''
      ).toLowerCase();
      const code = (v.code || v.vendorCode || v.Code || v.supplyCode || '').toLowerCase();
      return name.includes(searchLower) || code.includes(searchLower);
    });
  }, [
    vendors,
    filters.countries,
    filters.vendors,
    filters.states,
    filters.markets,
    vendorSearch,
    hierarchyLocationCodes,
    locationCodesInSelectedStateMarket,
  ]);

  const handleMultiSelect = (filterKey, value, checked) => {
    const currentValues = filters[filterKey] || [];
    if (checked) {
      onFiltersChange({
        ...filters,
        [filterKey]: [...currentValues, value],
      });
    } else {
      onFiltersChange({
        ...filters,
        [filterKey]: currentValues.filter((v) => v !== value),
      });
    }
  };

  const handleDayToggle = (dayType, dayValue, checked) => {
    const currentDays = filters[dayType] || [];
    if (checked) {
      onFiltersChange({
        ...filters,
        [dayType]: [...currentDays, dayValue],
      });
    } else {
      onFiltersChange({
        ...filters,
        [dayType]: currentDays.filter((d) => d !== dayValue),
      });
    }
  };

  const clearFilters = () => {
    onFiltersChange({
      markets: [],
      countries: [],
      locations: [],
      vendors: [],
      states: [],
      distributionCenters: [],
      deliveryDays: [],
      orderingDays: [],
    });
  };

  const hasActiveFilters = Object.values(filters).some(
    (arr) => Array.isArray(arr) && arr.length > 0,
  );

  // Helper to get active filter count for a section
  const getActiveFilterCount = (filterKey) => {
    const filterValues = filters[filterKey] || [];
    return Array.isArray(filterValues) ? filterValues.length : 0;
  };

  // Calculate the number of locations filtered by selected countries
  const countryFilteredLocationCount = useMemo(() => {
    if (!filters.countries || filters.countries.length === 0) {
      return null; // No country filter applied
    }

    return locations.filter((loc) => {
      const locCountry = extractCountry(loc);
      if (locCountry) {
        const countryStr =
          typeof locCountry === 'string' ? locCountry.trim() : String(locCountry).trim();
        return filters.countries.includes(countryStr);
      }
      return false;
    }).length;
  }, [locations, filters.countries]);

  // Calculate the number of locations filtered by selected states
  const stateFilteredLocationCount = useMemo(() => {
    if (!filters.states || filters.states.length === 0) {
      return null; // No state filter applied
    }

    return locations.filter((loc) => {
      const locState = extractState(loc);
      if (locState) {
        const stateStr = typeof locState === 'string' ? locState.trim() : String(locState).trim();
        return filters.states.includes(stateStr);
      }
      return false;
    }).length;
  }, [locations, filters.states]);

  // Locations that match current country and state filters (and selected locations or vendor hierarchy when set)
  const locationsByCountryAndState = useMemo(() => {
    let base = locations.filter((loc) => {
      const locationCode = loc.code || loc.locationCode || loc.Code || loc.LocationCode || '';
      if (locationCode === '000000') return false;
      if (filters.countries && filters.countries.length > 0) {
        const locCountry = extractCountry(loc);
        if (!locCountry) return false;
        const countryStr =
          typeof locCountry === 'string' ? locCountry.trim() : String(locCountry).trim();
        if (!filters.countries.includes(countryStr)) return false;
      }
      if (filters.states && filters.states.length > 0) {
        const locState = extractState(loc);
        if (!locState) return false;
        const stateStr = typeof locState === 'string' ? locState.trim() : String(locState).trim();
        if (!filters.states.includes(stateStr)) return false;
      }
      return true;
    });
    if (filters.locations && filters.locations.length > 0) {
      const selectedSet = new Set(filters.locations.map((c) => String(c).trim()));
      base = base.filter((loc) => {
        const code = loc.code || loc.locationCode || loc.Code || loc.LocationCode || '';
        return selectedSet.has(String(code).trim());
      });
    }
    if (hierarchyLocationCodes && hierarchyLocationCodes.size > 0) {
      base = base.filter((loc) => {
        const code = loc.code || loc.locationCode || loc.Code || loc.LocationCode || '';
        return hierarchyLocationCodes.has(String(code).trim());
      });
    }
    return base;
  }, [locations, filters.countries, filters.states, filters.locations, hierarchyLocationCodes]);

  // Markets list is dynamic: only markets for locations in the selected country/countries and state(s)
  const availableMarketsFiltered = useMemo(() => {
    const set = new Set();
    locationsByCountryAndState.forEach((loc) => {
      const m = extractMarket(loc);
      if (m !== undefined && m !== null && m !== '') set.add(String(m).trim());
    });
    return Array.from(set).sort();
  }, [locationsByCountryAndState]);

  // When country/state change, drop any selected markets that are no longer in the dynamic list
  useEffect(() => {
    const current = filters.markets || [];
    if (current.length === 0) return;
    const allowed = new Set(availableMarketsFiltered);
    const kept = current.filter((m) => allowed.has(m));
    if (kept.length !== current.length) {
      onFiltersChange({ ...filters, markets: kept });
    }
  }, [availableMarketsFiltered, filters, onFiltersChange]);

  // When available countries shrink (e.g. state selected), drop any selected country not in the list
  useEffect(() => {
    const current = filters.countries || [];
    if (current.length === 0) return;
    const allowed = new Set(countries);
    const kept = current.filter((c) => allowed.has(c));
    if (kept.length !== current.length) {
      onFiltersChange({ ...filters, countries: kept });
    }
  }, [countries, filters, onFiltersChange]);

  // When available states shrink (e.g. market or location selected), drop any selected state not in the list
  useEffect(() => {
    const current = filters.states || [];
    if (current.length === 0) return;
    const allowed = new Set(states);
    const kept = current.filter((s) => allowed.has(s));
    if (kept.length !== current.length) {
      onFiltersChange({ ...filters, states: kept });
    }
  }, [states, filters, onFiltersChange]);

  // Calculate the number of locations filtered by selected markets
  const marketFilteredLocationCount = useMemo(() => {
    if (!filters.markets || filters.markets.length === 0) {
      return null;
    }
    return locations.filter((loc) => {
      const locMarket = extractMarket(loc);
      if (!locMarket) return false;
      const marketStr = typeof locMarket === 'string' ? locMarket.trim() : String(locMarket).trim();
      return marketStr.length > 0 && filters.markets.includes(marketStr);
    }).length;
  }, [locations, filters.markets]);

  // Calculate the number of locations filtered by selected distribution centers
  const dcFilteredLocationCount = useMemo(() => {
    if (
      !filters.distributionCenters ||
      filters.distributionCenters.length === 0 ||
      !dcToLocationCodes
    ) {
      return null; // No DC filter applied
    }
    const locationCodesInDCs = new Set();
    filters.distributionCenters.forEach((dcName) => {
      const codes = dcToLocationCodes.get(dcName);
      if (codes) codes.forEach((code) => locationCodesInDCs.add(code));
    });
    return locations.filter((loc) => {
      const code = loc.code || loc.locationCode || loc.Code || loc.LocationCode || '';
      return locationCodesInDCs.has(code);
    }).length;
  }, [locations, filters.distributionCenters, dcToLocationCodes]);

  return (
    <div className="filter-panel-wrapper">
      <div className={`filter-panel ${isCollapsed ? 'filter-panel--collapsed' : ''}`}>
        {!isCollapsed && (
          <button
            type="button"
            onClick={() => setIsCollapsed(true)}
            className="filter-panel-collapse-tab"
            title="Collapse filters to get more space"
            aria-label="Collapse filters"
          >
            <span className="filter-panel-collapse-arrow">◀</span>
          </button>
        )}
        <div className="filter-panel-header-pinned">
          <div className="filter-panel-header">
            {isCollapsed ? (
              <button
                type="button"
                onClick={() => setIsCollapsed(false)}
                className="filter-panel-expand-btn"
                title="Show filters"
              >
                <span className="filter-panel-expand-icon">▶</span>
                <span className="filter-panel-expand-label">Filters</span>
              </button>
            ) : (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <h2>Filters</h2>
                  <button
                    onClick={toggleAllSections}
                    className="expand-collapse-all-btn"
                    title={
                      Object.values(expandedSections).some((expanded) => expanded)
                        ? 'Collapse All'
                        : 'Expand All'
                    }
                  >
                    {Object.values(expandedSections).some((expanded) => expanded)
                      ? 'Collapse All'
                      : 'Expand All'}
                  </button>
                </div>
                {hasActiveFilters && (
                  <button onClick={clearFilters} className="clear-filters-btn">
                    Clear All
                  </button>
                )}
              </>
            )}
          </div>
          {!isCollapsed && showViewSchedules && onViewSchedules && (
            <button
              onClick={onViewSchedules}
              disabled={schedulesLoading}
              className="view-schedules-btn"
              title="Fetch and display schedules for the selected filters"
            >
              {schedulesLoading ? 'Loading...' : 'View Schedules'}
            </button>
          )}
        </div>

        {!isCollapsed && (
          <div className="filter-panel-body">
            {/* Countries filter */}
            <div className="filter-section">
              <div className="filter-section-header" onClick={() => toggleSection('countries')}>
                <div className="filter-section-title">
                  <h3>
                    Countries
                    {countryFilteredLocationCount !== null && (
                      <span className="filter-location-count">
                        {' '}
                        ({countryFilteredLocationCount} location
                        {countryFilteredLocationCount !== 1 ? 's' : ''})
                      </span>
                    )}
                  </h3>
                  {getActiveFilterCount('countries') > 0 && (
                    <span className="filter-badge">{getActiveFilterCount('countries')}</span>
                  )}
                </div>
                <span className="filter-toggle-icon">{expandedSections.countries ? '▼' : '▶'}</span>
              </div>
              {expandedSections.countries && (
                <div className="filter-checkbox-list">
                  {countries.map((country) => (
                    <label key={country} className="filter-checkbox">
                      <input
                        type="checkbox"
                        checked={filters.countries.includes(country)}
                        onChange={(e) => handleMultiSelect('countries', country, e.target.checked)}
                      />
                      <span>{country}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* States filter */}
            <div className="filter-section">
              <div className="filter-section-header" onClick={() => toggleSection('states')}>
                <div className="filter-section-title">
                  <h3>
                    States
                    {stateFilteredLocationCount !== null && (
                      <span className="filter-location-count">
                        {' '}
                        ({stateFilteredLocationCount} location
                        {stateFilteredLocationCount !== 1 ? 's' : ''})
                      </span>
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
                  {states.map((state) => (
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

            {/* Markets filter - between States & Locations; list only markets for locations in selected country/countries and state(s) */}
            <div className="filter-section">
              <div className="filter-section-header" onClick={() => toggleSection('markets')}>
                <div className="filter-section-title">
                  <h3>
                    Markets
                    {marketFilteredLocationCount !== null && (
                      <span className="filter-location-count">
                        {' '}
                        ({marketFilteredLocationCount} location
                        {marketFilteredLocationCount !== 1 ? 's' : ''})
                      </span>
                    )}
                  </h3>
                  {getActiveFilterCount('markets') > 0 && (
                    <span className="filter-badge">{getActiveFilterCount('markets')}</span>
                  )}
                </div>
                <span className="filter-toggle-icon">{expandedSections.markets ? '▼' : '▶'}</span>
              </div>
              {expandedSections.markets && (
                <div className="filter-checkbox-list">
                  {(availableMarketsFiltered || []).map((market) => (
                    <label key={market} className="filter-checkbox">
                      <input
                        type="checkbox"
                        checked={(filters.markets || []).includes(market)}
                        onChange={(e) => handleMultiSelect('markets', market, e.target.checked)}
                      />
                      <span>{market}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Locations filter */}
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
                  <div className="filter-select-all-row">
                    <label className="filter-select-all-label">
                      <input
                        type="checkbox"
                        checked={
                          availableLocationCodes.size > 0 &&
                          (filters.locations || []).length === availableLocationCodes.size
                        }
                        ref={(el) => {
                          if (el)
                            el.indeterminate =
                              availableLocationCodes.size > 0 &&
                              (filters.locations || []).length > 0 &&
                              (filters.locations || []).length < availableLocationCodes.size;
                        }}
                        onChange={(e) => handleLocationsSelectAll(e.target.checked)}
                        aria-label="Select all locations"
                      />
                      <span>Select all</span>
                    </label>
                    {availableLocationCodes.size > 0 && (
                      <span className="filter-select-all-count">
                        ({availableLocationCodes.size} location
                        {availableLocationCodes.size !== 1 ? 's' : ''})
                      </span>
                    )}
                  </div>
                  <input
                    type="text"
                    placeholder="Search locations..."
                    value={locationSearch}
                    onChange={(e) => setLocationSearch(e.target.value)}
                    className="filter-search"
                  />
                  <div className="filter-checkbox-list">
                    {filteredLocations
                      .map((loc, index) => {
                        const locationCode =
                          loc.code || loc.locationCode || loc.Code || loc.LocationCode || '';

                        // Handle locationNameAddressDetails as array or object
                        let nameDetails = null;
                        if (
                          Array.isArray(loc.locationNameAddressDetails) &&
                          loc.locationNameAddressDetails.length > 0
                        ) {
                          nameDetails = loc.locationNameAddressDetails[0];
                        } else if (
                          Array.isArray(loc.LocationNameAddressDetails) &&
                          loc.LocationNameAddressDetails.length > 0
                        ) {
                          nameDetails = loc.LocationNameAddressDetails[0];
                        } else if (
                          loc.locationNameAddressDetails &&
                          typeof loc.locationNameAddressDetails === 'object'
                        ) {
                          nameDetails = loc.locationNameAddressDetails;
                        } else if (
                          loc.LocationNameAddressDetails &&
                          typeof loc.LocationNameAddressDetails === 'object'
                        ) {
                          nameDetails = loc.LocationNameAddressDetails;
                        }

                        // Try multiple variations of the locationName field
                        const locationName = (
                          nameDetails?.locationName ||
                          nameDetails?.LocationName ||
                          nameDetails?.name ||
                          nameDetails?.Name ||
                          loc.name ||
                          loc.locationName ||
                          loc.LocationName ||
                          loc.Name ||
                          loc.description ||
                          loc.Description ||
                          ''
                        )
                          .toString()
                          .trim();

                        // Use locationName if it exists and is not empty, otherwise fall back to code
                        const displayText =
                          locationName && locationName.length > 0 ? locationName : locationCode;

                        return { loc, locationCode, displayText, index };
                      })
                      .sort((a, b) => a.displayText.localeCompare(b.displayText))
                      .slice(0, 50)
                      .map(({ loc, locationCode, displayText, index }) => (
                        <label
                          key={locationCode || `location-${index}`}
                          className="filter-checkbox"
                        >
                          <input
                            type="checkbox"
                            checked={filters.locations.includes(locationCode)}
                            onChange={(e) =>
                              handleMultiSelect('locations', locationCode, e.target.checked)
                            }
                          />
                          <span>{displayText}</span>
                        </label>
                      ))}
                    {filteredLocations.length > 50 && (
                      <p className="filter-note">
                        Showing first 50 of {filteredLocations.length} locations
                      </p>
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
                    {filteredVendors
                      .map((vendor) => {
                        const vendorCode =
                          vendor.code ||
                          vendor.vendorCode ||
                          vendor.Code ||
                          vendor.supplyCode ||
                          '';
                        const vendorName =
                          vendor.supplyName ||
                          vendor.name ||
                          vendor.vendorName ||
                          vendor.Name ||
                          vendor.description ||
                          vendor.Description ||
                          '';
                        const displayText = vendorName || vendorCode || 'Unknown Vendor';
                        return { vendor, vendorCode, displayText };
                      })
                      .sort((a, b) => a.displayText.localeCompare(b.displayText))
                      .map(({ vendor, vendorCode, displayText }) => (
                        <label key={vendorCode} className="filter-checkbox">
                          <input
                            type="checkbox"
                            checked={filters.vendors.includes(vendorCode)}
                            onChange={(e) =>
                              handleMultiSelect('vendors', vendorCode, e.target.checked)
                            }
                          />
                          <span>{displayText}</span>
                        </label>
                      ))}
                  </div>
                </>
              )}
            </div>

            {/* Distribution Centers filter - when selected, locations filter by DC via locationCode */}
            <div className="filter-section">
              <div
                className="filter-section-header"
                onClick={() => toggleSection('distributionCenters')}
              >
                <div className="filter-section-title">
                  <h3>
                    Distribution Centers
                    {dcFilteredLocationCount !== null && (
                      <span className="filter-location-count">
                        {' '}
                        ({dcFilteredLocationCount} location
                        {dcFilteredLocationCount !== 1 ? 's' : ''})
                      </span>
                    )}
                  </h3>
                  {getActiveFilterCount('distributionCenters') > 0 && (
                    <span className="filter-badge">
                      {getActiveFilterCount('distributionCenters')}
                    </span>
                  )}
                </div>
                <span className="filter-toggle-icon">
                  {expandedSections.distributionCenters ? '▼' : '▶'}
                </span>
              </div>
              {expandedSections.distributionCenters && (
                <div className="filter-checkbox-list">
                  {distributionCenters.map((dc) => (
                    <label key={dc} className="filter-checkbox">
                      <input
                        type="checkbox"
                        checked={filters.distributionCenters.includes(dc)}
                        onChange={(e) =>
                          handleMultiSelect('distributionCenters', dc, e.target.checked)
                        }
                      />
                      <span>{dc}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Ordering Days filter - hidden when hideDayFilters (e.g. Auto Allocation) */}
            {!hideDayFilters && (
              <div className="filter-section">
                <div
                  className="filter-section-header"
                  onClick={() => toggleSection('orderingDays')}
                >
                  <div className="filter-section-title">
                    <h3>Ordering Days</h3>
                    {getActiveFilterCount('orderingDays') > 0 && (
                      <span className="filter-badge">{getActiveFilterCount('orderingDays')}</span>
                    )}
                  </div>
                  <span className="filter-toggle-icon">
                    {expandedSections.orderingDays ? '▼' : '▶'}
                  </span>
                </div>
                {expandedSections.orderingDays && (
                  <div className="filter-checkbox-list">
                    {DAYS_OF_WEEK.map((day) => (
                      <label key={day.value} className="filter-checkbox">
                        <input
                          type="checkbox"
                          checked={filters.orderingDays.includes(day.value)}
                          onChange={(e) =>
                            handleDayToggle('orderingDays', day.value, e.target.checked)
                          }
                        />
                        <span>{day.label}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Delivery Days filter - hidden when hideDayFilters */}
            {!hideDayFilters && (
              <div className="filter-section">
                <div
                  className="filter-section-header"
                  onClick={() => toggleSection('deliveryDays')}
                >
                  <div className="filter-section-title">
                    <h3>Delivery Days</h3>
                    {getActiveFilterCount('deliveryDays') > 0 && (
                      <span className="filter-badge">{getActiveFilterCount('deliveryDays')}</span>
                    )}
                  </div>
                  <span className="filter-toggle-icon">
                    {expandedSections.deliveryDays ? '▼' : '▶'}
                  </span>
                </div>
                {expandedSections.deliveryDays && (
                  <div className="filter-checkbox-list">
                    {DAYS_OF_WEEK.map((day) => (
                      <label key={day.value} className="filter-checkbox">
                        <input
                          type="checkbox"
                          checked={filters.deliveryDays.includes(day.value)}
                          onChange={(e) =>
                            handleDayToggle('deliveryDays', day.value, e.target.checked)
                          }
                        />
                        <span>{day.label}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
