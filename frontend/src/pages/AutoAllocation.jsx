import { useState, useEffect, useMemo } from 'react'
import FilterPanel from '../components/FilterPanel/FilterPanel.jsx'
import client from '../api/client.js'
import './AutoAllocation.css'

function extractCountry(loc) {
  if (Array.isArray(loc.locationNameAddressDetails) && loc.locationNameAddressDetails.length > 0) {
    const nameDetails = loc.locationNameAddressDetails[0]
    if (nameDetails?.country) return nameDetails.country
    if (nameDetails?.Country) return nameDetails.Country
  }
  if (loc.country) return loc.country
  if (loc.Country) return loc.Country
  return null
}

function extractState(loc) {
  if (Array.isArray(loc.locationNameAddressDetails) && loc.locationNameAddressDetails.length > 0) {
    const nameDetails = loc.locationNameAddressDetails[0]
    if (nameDetails?.stateProvince) return nameDetails.stateProvince
    if (nameDetails?.state) return nameDetails.state
    if (nameDetails?.State) return nameDetails.State
  }
  if (Array.isArray(loc.locationDetailDetails) && loc.locationDetailDetails.length > 0) {
    const details = loc.locationDetailDetails[0]
    if (details?.stateProvince) return details.stateProvince
    if (details?.state) return details.state
    if (details?.stateCode) return details.stateCode
  }
  if (loc.stateProvince) return loc.stateProvince
  if (loc.state) return loc.state
  if (loc.stateCode) return loc.stateCode
  return null
}

const MAX_PRODUCT_LINES = 10
const SYDNEY_TZ = 'Australia/Sydney'

/** True if the search term looks like a product number (e.g. P-10003, ABC-123). */
function looksLikeProductNumber(term) {
  const t = (term || '').trim()
  if (!t) return false
  return /^[A-Za-z0-9]+-[A-Za-z0-9]+$/.test(t) || /^P-\d+$/i.test(t) || /^\d+$/.test(t)
}

/** Build display rows from getAllVendorProductPricing response: main rows + optional secondary (alt) rows. */
function buildVendorPricingRows(apiData, includeAlt) {
  const rows = []
  if (!Array.isArray(apiData)) return rows
  apiData.forEach((item, mainIndex) => {
    const market = item.market ?? item.Market ?? '—'
    const productNumber = item.productNumber ?? item.ProductNumber ?? '—'
    const productName = item.productName ?? item.ProductName ?? '—'
    const vendorProductNumber = item.vendorProductNumber ?? item.VendorProductNumber ?? '—'
    const vendorPackSize = item.vendorPackSize ?? item.VendorPackSize ?? '—'
    rows.push({
      id: `main-${mainIndex}-${vendorProductNumber}`,
      market,
      productNumber,
      productName,
      vendorProductNumber,
      vendorUnit: vendorPackSize,
      isAlt: false,
    })
    if (includeAlt && Array.isArray(item.secondaryVendorProducts)) {
      (item.secondaryVendorProducts || []).forEach((sec, secIndex) => {
        rows.push({
          id: `alt-${mainIndex}-${secIndex}-${sec.vendorProductNumber || secIndex}`,
          market,
          productNumber,
          productName: sec.vendorProductName ?? sec.VendorProductName ?? productName,
          vendorProductNumber: sec.vendorProductNumber ?? sec.VendorProductNumber ?? '—',
          vendorUnit: sec.vendorPackSize ?? sec.VendorPackSize ?? '—',
          isAlt: true,
        })
      })
    }
  })
  return rows
}

/** Current date/time in Sydney (AEST/AEDT) as YYYY-MM-DDTHH:mm for comparison and min attribute */
function getNowSydneyLocal() {
  const d = new Date()
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: SYDNEY_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
  const parts = formatter.formatToParts(d)
  const get = (type) => parts.find(p => p.type === type)?.value ?? ''
  const year = get('year')
  const month = get('month').padStart(2, '0')
  const day = get('day').padStart(2, '0')
  const hour = get('hour').padStart(2, '0')
  const minute = get('minute').padStart(2, '0')
  return `${year}-${month}-${day}T${hour}:${minute}`
}

/** Today's date in Sydney as YYYY-MM-DD for date inputs and validation. */
function getTodaySydneyDate() {
  const d = new Date()
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: SYDNEY_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
  const parts = formatter.formatToParts(d)
  const get = (type) => parts.find(p => p.type === type)?.value ?? ''
  return `${get('year')}-${get('month').padStart(2, '0')}-${get('day').padStart(2, '0')}`
}

export default function AutoAllocation() {
  const [locations, setLocations] = useState([])
  const [vendors, setVendors] = useState([])
  const [hierarchy, setHierarchy] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expectedDeliveryDate, setExpectedDeliveryDate] = useState('')
  const [orderDateTime, setOrderDateTime] = useState('')
  const [lineItems, setLineItems] = useState([])
  const [productSearch, setProductSearch] = useState('')
  const [products, setProducts] = useState([])
  const [productsLoading, setProductsLoading] = useState(false)
  const [productsError, setProductsError] = useState(null)
  const [productsSearched, setProductsSearched] = useState(false)
  const [showAltItems, setShowAltItems] = useState(false)
  const [submitLoading, setSubmitLoading] = useState(false)
  const [submitResult, setSubmitResult] = useState(null)

  const [filters, setFilters] = useState({
    markets: [],
    countries: [],
    locations: [],
    vendors: [],
    states: [],
    distributionCenters: [],
    deliveryDays: [],
    orderingDays: []
  })

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true)
        setError(null)
        const [locationsRes, vendorsRes] = await Promise.all([
          client.get('/api/locations', { params: { activeFlag: true } }).catch(() => ({ data: { data: [] } })),
          client.get('/api/vendors', { params: { activeFlag: true } }).catch(() => ({ data: { data: [] } }))
        ])
        setLocations(locationsRes.data.data || [])
        setVendors(vendorsRes.data.data || [])
      } catch (err) {
        console.error('Error fetching data:', err)
        setError(err.message || 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  useEffect(() => {
    if (!filters.vendors?.length || filters.vendors.length !== 1 || vendors.length === 0) {
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

  const availableMarkets = useMemo(() => {
    const set = new Set()
    locations.forEach(loc => {
      if (Array.isArray(loc.locationDetailDetails) && loc.locationDetailDetails.length > 0) {
        const details = loc.locationDetailDetails[0]
        const m = details?.market ?? details?.Market
        if (m !== undefined && m !== null && m !== '') set.add(String(m).trim())
      }
      if (loc.market !== undefined && loc.market !== null && loc.market !== '') set.add(String(loc.market).trim())
      if (loc.Market !== undefined && loc.Market !== null && loc.Market !== '') set.add(String(loc.Market).trim())
    })
    return Array.from(set).sort()
  }, [locations])

  const availableCountries = useMemo(() => {
    const countries = new Set()
    locations.forEach(loc => {
      const country = extractCountry(loc)
      if (country) {
        const s = typeof country === 'string' ? country.trim() : String(country).trim()
        if (s.length > 0) countries.add(s)
      }
    })
    return Array.from(countries).sort()
  }, [locations])

  const availableStates = useMemo(() => {
    const states = new Set()
    locations.forEach(loc => {
      if (filters.countries?.length) {
        const locCountry = extractCountry(loc)
        if (!locCountry || !filters.countries.includes(String(locCountry).trim())) return
      }
      const state = extractState(loc)
      if (state) {
        const s = typeof state === 'string' ? state.trim() : String(state).trim()
        if (s.length > 0) states.add(s)
      }
    })
    return Array.from(states).sort()
  }, [locations, filters.countries])

  const { availableDCs, dcToLocationCodes } = useMemo(() => {
    const dcs = new Set()
    const dcLocationMap = new Map()
    hierarchy.forEach(item => {
      if (item.levelNumber === 3 || item.levelNumber === '3') {
        const dcName = item.parentLogicalName || item.distributionCenterCode || item.dcCode || ''
        const locationCode = item.locationCode || item.LocationCode || item.code || item.Code || ''
        if (dcName) {
          dcs.add(dcName)
          if (locationCode) {
            if (!dcLocationMap.has(dcName)) dcLocationMap.set(dcName, new Set())
            dcLocationMap.get(dcName).add(locationCode)
          }
        }
      }
    })
    return { availableDCs: Array.from(dcs).sort(), dcToLocationCodes: dcLocationMap }
  }, [hierarchy])

  /** Order date (YYYY-MM-DD or YYYY-MM-DDTHH:mm) to Crunchtime effectiveDate (mm/dd/yyyy). */
  const orderDateToEffectiveDate = (orderDateStr) => {
    const s = (orderDateStr || '').trim()
    if (!s) return null
    const datePart = s.split('T')[0]
    const [y, m, d] = datePart.split('-')
    if (!y || !m || !d) return null
    return `${m}/${d}/${y}`
  }

  const fetchProducts = async () => {
    const term = productSearch.trim()
    if (!term) {
      setProductsError('Enter a product name or product number to search.')
      setProductsSearched(true)
      return
    }
    const vendorCount = filters.vendors?.length ?? 0
    const marketCount = filters.markets?.length ?? 0
    if (vendorCount !== 1 && marketCount !== 1) {
      setProductsError('Please select a Vendor and a Market to continue.')
      setProductsSearched(true)
      return
    }
    if (vendorCount !== 1) {
      setProductsError('Please select a Vendor to continue.')
      setProductsSearched(true)
      return
    }
    if (marketCount !== 1) {
      setProductsError('Please select a Market to continue.')
      setProductsSearched(true)
      return
    }
    const effectiveDate = orderDateToEffectiveDate(orderDateTime)
    if (!effectiveDate) {
      setProductsError('Please set Order date & time to search products.')
      setProductsSearched(true)
      return
    }
    setProductsError(null)
    setProductsLoading(true)
    setProductsSearched(true)
    try {
      const selectedVendorCode = (filters.vendors && filters.vendors[0]) || ''
      const selectedVendor = vendors.find(
        v => (v.code || v.vendorCode || v.Code || v.supplyCode || '').toString().trim() === selectedVendorCode
      )
      const vendorParam = selectedVendor
        ? (selectedVendor.supplyName || selectedVendor.name || selectedVendor.vendorName || selectedVendor.Name || selectedVendorCode)
        : selectedVendorCode
      const params = {
        effective_date: effectiveDate,
        market: (filters.markets && filters.markets[0]) || '',
        vendor: vendorParam,
      }
      if (looksLikeProductNumber(term)) {
        params.product_number = term
      } else {
        params.product_name = term
      }
      const res = await client.get('/api/products/vendor-product-pricing', { params })
      const data = res.data?.data ?? []
      setProducts(Array.isArray(data) ? data : [])
    } catch (err) {
      if (!err.response) {
        setProductsError('Network error: ensure the backend is running (e.g. uvicorn on port 8000) and restart the frontend dev server.')
        setProducts([])
        return
      }
      if (err.response?.status === 500) {
        setProductsError('Product Not Found')
        setProducts([])
        return
      }
      const detail = err.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg || d).join(' ') : err.message || 'Failed to load products'
      setProductsError(msg)
      setProducts([])
    } finally {
      setProductsLoading(false)
    }
  }

  /** Display rows: main + optional secondary (alt) from getAllVendorProductPricing response. */
  const productDisplayRows = useMemo(
    () => buildVendorPricingRows(products, showAltItems).slice(0, 100),
    [products, showAltItems]
  )

  const addProductToTable = (product) => {
    if (lineItems.length >= MAX_PRODUCT_LINES) return
    const id = `${product.vendorProductNumber || product.id || Date.now()}-${lineItems.length}`
    const newItem = {
      id,
      productName: product.productName || product.name || '—',
      vendorProductNumber: product.vendorProductNumber || product.vendorProductNo || '—',
      vendorUnit: product.vendorUnit || product.unit || '—',
      qty: 1
    }
    setLineItems(prev => [...prev, newItem])
  }

  const updateLineItemQty = (id, qty) => {
    const n = Math.max(0, parseInt(qty, 10) || 0)
    setLineItems(prev => prev.map(item => item.id === id ? { ...item, qty: n } : item))
  }

  const removeLineItem = (id) => {
    setLineItems(prev => prev.filter(item => item.id !== id))
  }

  const handleSubmitOrder = async () => {
    setSubmitResult(null)
    const locationCodes = filters.locations || []
    const vendorCodes = filters.vendors || []
    const validLines = lineItems.filter(li => (li.qty || 0) > 0)

    if (locationCodes.length === 0) {
      setSubmitResult({ success: false, message: 'Select at least one location.' })
      return
    }
    if (vendorCodes.length !== 1) {
      setSubmitResult({ success: false, message: 'Select exactly one vendor.' })
      return
    }
    if (!expectedDeliveryDate.trim()) {
      setSubmitResult({ success: false, message: 'Set the expected delivery date.' })
      return
    }
    const todaySydney = getTodaySydneyDate()
    if (expectedDeliveryDate < todaySydney) {
      setSubmitResult({ success: false, message: 'Expected delivery date must be today or in the future.' })
      return
    }
    if (!orderDateTime.trim()) {
      setSubmitResult({ success: false, message: 'Set the order date and time.' })
      return
    }
    const nowSydney = getNowSydneyLocal()
    if (orderDateTime < nowSydney) {
      setSubmitResult({ success: false, message: 'Order date & time must be current or future.' })
      return
    }
    if (validLines.length === 0) {
      setSubmitResult({ success: false, message: 'Add at least one product with quantity greater than 0.' })
      return
    }

    const payload = {
      order_date_time: orderDateTime.length <= 16 ? `${orderDateTime}:00` : orderDateTime,
      expected_delivery_date: expectedDeliveryDate,
      location_codes: locationCodes,
      vendor_code: vendorCodes[0],
      line_items: validLines.map(li => ({
        product_name: li.productName,
        vendor_product_number: li.vendorProductNumber,
        vendor_unit: li.vendorUnit || '',
        qty: Math.max(0, parseInt(li.qty, 10) || 0)
      }))
    }

    try {
      setSubmitLoading(true)
      const res = await client.post('/api/purchase-orders/submit', payload)
      setSubmitResult(res.data || { success: true, message: 'Order submitted.' })
    } catch (err) {
      const detail = err.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg || d).join(' ') : err.message || 'Failed to submit order'
      setSubmitResult({ success: false, message: msg })
    } finally {
      setSubmitLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="auto-allocation-loading">
        <p>Loading...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="auto-allocation-error">
        <p>Error: {error}</p>
      </div>
    )
  }

  return (
    <div className="auto-allocation">
      <div className="auto-allocation-content">
        <FilterPanel
          locations={locations}
          vendors={vendors}
          countries={availableCountries}
          states={availableStates}
          markets={availableMarkets}
          distributionCenters={availableDCs}
          dcToLocationCodes={dcToLocationCodes}
          filters={filters}
          onFiltersChange={setFilters}
          hideDayFilters
          showViewSchedules={false}
        />

        <div className="auto-allocation-main">
          <section className="auto-allocation-section expected-delivery-section">
            <h2>Expected delivery date</h2>
            <p className="section-note">Select the date by when products should be delivered to the selected locations. Must be today or in the future.</p>
            <input
              type="date"
              value={expectedDeliveryDate}
              onChange={(e) => setExpectedDeliveryDate(e.target.value)}
              min={getTodaySydneyDate()}
              className="expected-delivery-date-input"
              aria-describedby="expected-delivery-hint"
            />
            <p id="expected-delivery-hint" className="input-hint">Cannot be in the past.</p>
          </section>

          <section className="auto-allocation-section order-datetime-section">
            <h2>Order date & time</h2>
            <p className="section-note">When the order should be placed or scheduled. Must be current or future.</p>
            <input
              type="datetime-local"
              value={orderDateTime}
              onChange={(e) => setOrderDateTime(e.target.value)}
              min={getNowSydneyLocal()}
              className="order-datetime-input"
              aria-describedby="order-datetime-hint"
            />
            <p id="order-datetime-hint" className="input-hint">Cannot be in the past.</p>
          </section>

          <section className="auto-allocation-section products-section">
            <h2>Products</h2>
            <p className="section-note">Select one Vendor and one Market in the filters, set Order date & time, then search by product name or number. Click a row to add to the order. Max {MAX_PRODUCT_LINES} products.</p>
            <div className="product-search-row">
              <input
                type="text"
                placeholder="Product name or number (e.g. P-10003 or Meat - Chicken Maryland)"
                value={productSearch}
                onChange={(e) => setProductSearch(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchProducts()}
                className="product-search-input"
                disabled={productsLoading}
              />
              <button
                type="button"
                onClick={fetchProducts}
                disabled={productsLoading}
                className="product-search-btn"
              >
                {productsLoading ? 'Searching...' : 'Search'}
              </button>
            </div>
            <div className="product-show-alt-row">
              <label className="product-show-alt-label">
                <input
                  type="checkbox"
                  checked={showAltItems}
                  onChange={(e) => setShowAltItems(e.target.checked)}
                />
                <span>Show Alt items</span>
              </label>
              <span className="product-show-alt-hint">When selected, alternate vendor products are listed with *</span>
            </div>
            {productsError && (
              <p className="products-error-msg">{productsError}</p>
            )}
            <div className="product-catalogue-table-wrap">
              {!productsSearched && (
                <p className="no-products-msg">Select one Vendor and one Market, set Order date & time, then enter a product name or number and click Search.</p>
              )}
              {productsSearched && !productsLoading && productDisplayRows.length === 0 && !productsError && (
                <p className="no-products-msg">No products found. Try a different name or number.</p>
              )}
              {productDisplayRows.length > 0 && (
                <table className="product-catalogue-table">
                  <thead>
                    <tr>
                      <th>Market</th>
                      <th>Product Number</th>
                      <th>Product Name</th>
                      <th>Vendor Product Number</th>
                      <th>Vendor unit</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {productDisplayRows.map((row) => (
                      <tr
                        key={row.id}
                        className={row.isAlt ? 'product-catalogue-row-alt' : ''}
                      >
                        <td>{row.market}</td>
                        <td>{row.productNumber}</td>
                        <td>{row.isAlt ? `${row.productName} *` : row.productName}</td>
                        <td>{row.vendorProductNumber}</td>
                        <td>{row.vendorUnit}</td>
                        <td>
                          <button
                            type="button"
                            onClick={() => addProductToTable(row)}
                            disabled={lineItems.length >= MAX_PRODUCT_LINES}
                            className="add-product-btn"
                            title="Add to order"
                          >
                            Add
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>

          <section className="auto-allocation-section order-lines-section">
            <h2>Order lines</h2>
            <p className="section-note">Selected products and quantities for the selected locations/vendors and expected delivery date.</p>
            <div className="order-lines-table-wrap">
              <table className="order-lines-table">
                <thead>
                  <tr>
                    <th>Product Name</th>
                    <th>Vendor Product Number</th>
                    <th>Vendor Unit</th>
                    <th>Qty</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {lineItems.length === 0 && (
                    <tr>
                      <td colSpan={5} className="empty-table-msg">Add products from the list above.</td>
                    </tr>
                  )}
                  {lineItems.map(item => (
                    <tr key={item.id}>
                      <td>{item.productName}</td>
                      <td>{item.vendorProductNumber}</td>
                      <td>{item.vendorUnit}</td>
                      <td>
                        <input
                          type="number"
                          min={0}
                          value={item.qty}
                          onChange={(e) => updateLineItemQty(item.id, e.target.value)}
                          className="qty-input"
                        />
                      </td>
                      <td>
                        <button type="button" onClick={() => removeLineItem(item.id)} className="remove-line-btn" title="Remove line">✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="auto-allocation-section submit-section">
            <h2>Submit order</h2>
            <p className="section-note">Review filters, expected delivery date, order date/time and order lines, then submit to schedule the order.</p>
            {submitResult && (
              <div className={`submit-result ${submitResult.success ? 'submit-result-success' : 'submit-result-error'}`}>
                {submitResult.message}
                {submitResult.success && submitResult.location_count != null && (
                  <span className="submit-result-meta"> — {submitResult.location_count} location(s), {submitResult.line_count} line(s)</span>
                )}
              </div>
            )}
            <button
              type="button"
              onClick={handleSubmitOrder}
              disabled={submitLoading}
              className="submit-order-btn"
            >
              {submitLoading ? 'Submitting...' : 'Schedule / Submit order'}
            </button>
          </section>
        </div>
      </div>
    </div>
  )
}
