import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';
import client from '../api/client.js';
import { formatDateDisplay, formatDateTimeDisplay } from '../utils/dateFormat.js';
import './ReviewAutoAllocatedOrders.css';

/** No filters: show 100 most recent. With any filter: allow full result set (backend cap 50k). */
const LIMIT_UNFILTERED = 100;
const LIMIT_FILTERED = 50000;

/** Order status dropdown value → `not_submitted` API param (status != SUBMITTED). */
const ORDER_STATUS_NOT_YET_SUBMITTED = '__NOT_YET_SUBMITTED__';

function isVendorConfirmReceived(tx) {
  const v = tx?.confirmReceivedStatus;
  if (v === true || v === 'true') return true;
  if (typeof v === 'string' && v.toLowerCase() === 'received') return true;
  return false;
}

function exportFilename(ext) {
  const yyyy = new Date().getFullYear();
  const mm = String(new Date().getMonth() + 1).padStart(2, '0');
  const dd = String(new Date().getDate()).padStart(2, '0');
  return `review-auto-allocated-orders-${yyyy}-${mm}-${dd}.${ext}`;
}

function downloadAsExcel(transactions, formatDateDisplayFn, formatDateTimeDisplayFn) {
  const headers = [
    'Status',
    'State',
    'Market',
    'Vendor',
    'Distribution Center',
    'Acc Code',
    'Location Name',
    'Expected Delivery Date',
    'Expected Delivery Day',
    'Set Submit Date',
    'Submitted Date',
    'PO Number',
    'Confirmed Received',
    'Confirmed Received At',
  ];
  const rows = transactions.map((tx) => [
    tx.status ?? '',
    tx.state ?? '',
    tx.market ?? '',
    tx.vendorName ?? '',
    tx.distributionCenter ?? '',
    tx.accountNumber ?? '',
    tx.locationName ?? tx.locationCode ?? '',
    tx.setExpectedDeliveryDate ? formatDateDisplayFn(tx.setExpectedDeliveryDate) || '' : '',
    tx.setExpectedDeliveryDOW ?? '',
    tx.setOrderDateTme ? formatDateTimeDisplayFn(tx.setOrderDateTme) || '' : '',
    tx.submittedDateTime ? formatDateTimeDisplayFn(tx.submittedDateTime) || '' : '',
    tx.transactionNo ?? '',
    isVendorConfirmReceived(tx) ? 'Confirmed' : '',
    tx.confirmRecievedDateTime ? formatDateTimeDisplayFn(tx.confirmRecievedDateTime) || '' : '',
  ]);
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
  XLSX.utils.book_append_sheet(wb, ws, 'Review');
  XLSX.writeFile(wb, exportFilename('xlsx'));
}

function downloadAsPdf(transactions, formatDateDisplayFn, formatDateTimeDisplayFn) {
  const headers = [
    'Status',
    'State',
    'Market',
    'Vendor',
    'Dist Center',
    'Acc Code',
    'Location',
    'Exp Del Date',
    'Exp Del Day',
    'Set Submit',
    'Submitted',
    'PO Number',
    'Confirmed',
    'Confirmed At',
  ];
  const body = transactions.map((tx) => [
    tx.status ?? '',
    tx.state ?? '',
    tx.market ?? '',
    tx.vendorName ?? '',
    tx.distributionCenter ?? '',
    tx.accountNumber ?? '',
    tx.locationName ?? tx.locationCode ?? '',
    tx.setExpectedDeliveryDate ? formatDateDisplayFn(tx.setExpectedDeliveryDate) || '' : '',
    tx.setExpectedDeliveryDOW ?? '',
    tx.setOrderDateTme ? formatDateTimeDisplayFn(tx.setOrderDateTme) || '' : '',
    tx.submittedDateTime ? formatDateTimeDisplayFn(tx.submittedDateTime) || '' : '',
    tx.transactionNo ?? '',
    isVendorConfirmReceived(tx) ? 'Confirmed' : '',
    tx.confirmRecievedDateTime ? formatDateTimeDisplayFn(tx.confirmRecievedDateTime) || '' : '',
  ]);
  const doc = new jsPDF({ orientation: 'landscape' });
  autoTable(doc, {
    head: [headers],
    body,
    styles: { fontSize: 7 },
  });
  doc.save(exportFilename('pdf'));
}

function normalizeLocationOptions(raw) {
  if (!Array.isArray(raw)) return [];
  return raw.map((entry) =>
    typeof entry === 'string' ? { code: entry, name: entry } : { ...entry },
  );
}

/** Map CrunchTime location row (from GET /api/locations) to { code, name }. */
function mapCrunchTimeLocationOption(loc) {
  if (!loc || typeof loc !== 'object') return null;
  const code = String(loc.locationCode ?? loc.LocationCode ?? loc.code ?? loc.Code ?? '').trim();
  if (!code) return null;
  let name = loc.locationName ?? loc.LocationName ?? loc.name ?? loc.Name ?? '';
  const nameAddr = loc.locationNameAddressDetails ?? loc.LocationNameAddressDetails;
  if (!name && Array.isArray(nameAddr) && nameAddr[0]) {
    const n0 = nameAddr[0];
    name = n0.locationName ?? n0.LocationName ?? n0.name ?? '';
  }
  const trimmed = String(name).trim();
  return { code, name: trimmed || code };
}

function buildLocationCatalogFromApi(rawList) {
  if (!Array.isArray(rawList)) return [];
  const byCode = new Map();
  for (const loc of rawList) {
    const opt = mapCrunchTimeLocationOption(loc);
    if (opt && !byCode.has(opt.code)) byCode.set(opt.code, opt);
  }
  return Array.from(byCode.values()).sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
  );
}

const emptyFilters = () => ({
  state: '',
  market: '',
  vendor: '',
  transactionStatus: '',
  locationCodes: [],
  expectedDeliveryFrom: '',
  expectedDeliveryTo: '',
  setOrderDateFrom: '',
  setOrderDateTo: '',
  submittedDateFrom: '',
  submittedDateTo: '',
  poNumber: '',
});

export default function ReviewAutoAllocatedOrders() {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filterOptions, setFilterOptions] = useState({
    states: [],
    markets: [],
    vendors: [],
    locations: [],
    statuses: [],
  });
  const [filters, setFilters] = useState(emptyFilters);
  const [popup, setPopup] = useState(null);
  const [selectedCancelIds, setSelectedCancelIds] = useState([]);
  const [cancellingBatch, setCancellingBatch] = useState(false);
  const [locationMenuOpen, setLocationMenuOpen] = useState(false);
  const [locationDropdownSearch, setLocationDropdownSearch] = useState('');
  const locationMenuRef = useRef(null);

  const cancellableSelectedCount = useMemo(() => {
    const sel = new Set(selectedCancelIds);
    return transactions.filter(
      (t) => t.status === 'SCHEDULED' && t.autoAllocateTransID && sel.has(t.autoAllocateTransID),
    ).length;
  }, [transactions, selectedCancelIds]);

  const filteredLocationsForDropdown = useMemo(() => {
    const list = filterOptions.locations;
    const q = locationDropdownSearch.trim().toLowerCase();
    if (!q) return list;
    return list.filter((loc) => {
      const name = String(loc.name ?? '').toLowerCase();
      const code = String(loc.code ?? '').toLowerCase();
      return name.includes(q) || code.includes(q);
    });
  }, [filterOptions.locations, locationDropdownSearch]);

  const fetchFilterOptions = useCallback(() => {
    Promise.all([
      client.get('/api/purchase-orders/transactions/filter-options').catch(() => ({ data: {} })),
      client
        .get('/api/locations', { params: { activeFlag: true } })
        .catch(() => ({ data: { data: [] } })),
    ]).then(([optRes, locRes]) => {
      const d = optRes.data || {};
      const rawLocs = locRes.data?.data;
      let locations = buildLocationCatalogFromApi(Array.isArray(rawLocs) ? rawLocs : []);
      if (locations.length === 0) {
        locations = normalizeLocationOptions(d.locations || []);
      }
      setFilterOptions({
        states: d.states || [],
        markets: d.markets || [],
        vendors: d.vendors || [],
        locations,
        statuses: d.statuses || [],
      });
    });
  }, []);

  const hasActiveFilters = !!(
    filters.state ||
    filters.market ||
    filters.vendor ||
    filters.transactionStatus ||
    (filters.locationCodes && filters.locationCodes.length > 0) ||
    filters.expectedDeliveryFrom ||
    filters.expectedDeliveryTo ||
    filters.setOrderDateFrom ||
    filters.setOrderDateTo ||
    filters.submittedDateFrom ||
    filters.submittedDateTo ||
    (filters.poNumber && filters.poNumber.trim())
  );

  const buildTransactionParams = useCallback(() => {
    const limit = hasActiveFilters ? LIMIT_FILTERED : LIMIT_UNFILTERED;
    const params = { limit, offset: 0 };
    if (filters.state) params.state = filters.state;
    if (filters.market) params.market = filters.market;
    if (filters.vendor) params.vendor = filters.vendor;
    if (filters.transactionStatus === ORDER_STATUS_NOT_YET_SUBMITTED) {
      params.not_submitted = true;
    } else if (filters.transactionStatus) {
      params.transaction_status = filters.transactionStatus;
    }
    if (filters.locationCodes?.length) params.location_codes = filters.locationCodes.join(',');
    if (filters.expectedDeliveryFrom) params.expected_delivery_from = filters.expectedDeliveryFrom;
    if (filters.expectedDeliveryTo) params.expected_delivery_to = filters.expectedDeliveryTo;
    if (filters.setOrderDateFrom) params.set_order_date_from = filters.setOrderDateFrom;
    if (filters.setOrderDateTo) params.set_order_date_to = filters.setOrderDateTo;
    if (filters.submittedDateFrom) params.submitted_date_from = filters.submittedDateFrom;
    if (filters.submittedDateTo) params.submitted_date_to = filters.submittedDateTo;
    if (filters.poNumber && filters.poNumber.trim()) params.po = filters.poNumber.trim();
    return params;
  }, [filters, hasActiveFilters]);

  const fetchTransactions = useCallback(() => {
    setLoading(true);
    client
      .get('/api/purchase-orders/transactions', { params: buildTransactionParams() })
      .then((res) => setTransactions(res.data?.data || []))
      .catch(() => setTransactions([]))
      .finally(() => setLoading(false));
  }, [buildTransactionParams]);

  useEffect(() => {
    fetchFilterOptions();
  }, [fetchFilterOptions]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        await client.post('/api/purchase-orders/sync-confirm-receipts').catch(() => {});
      } catch {
        /* ignore sync errors; still load grid */
      }
      if (cancelled) return;
      try {
        const res = await client.get('/api/purchase-orders/transactions', {
          params: buildTransactionParams(),
        });
        if (!cancelled) setTransactions(res.data?.data || []);
      } catch {
        if (!cancelled) setTransactions([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial load only; Apply/Refresh/cancel refetch
  }, []);

  useEffect(() => {
    const allowed = new Set(
      transactions
        .filter((t) => t.status === 'SCHEDULED' && t.autoAllocateTransID)
        .map((t) => t.autoAllocateTransID),
    );
    setSelectedCancelIds((prev) => prev.filter((id) => allowed.has(id)));
  }, [transactions]);

  useEffect(() => {
    if (!locationMenuOpen) {
      setLocationDropdownSearch('');
      return;
    }
    const close = () => setLocationMenuOpen(false);
    const onDocDown = (e) => {
      if (locationMenuRef.current && !locationMenuRef.current.contains(e.target)) close();
    };
    const onKey = (e) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('mousedown', onDocDown);
    document.addEventListener('touchstart', onDocDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocDown);
      document.removeEventListener('touchstart', onDocDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [locationMenuOpen]);

  const applyFilters = () => {
    fetchTransactions();
  };

  const applyFromLocationDropdown = () => {
    applyFilters();
    setLocationMenuOpen(false);
  };

  const clearFilters = () => {
    setFilters(emptyFilters());
    setLocationMenuOpen(false);
    setSelectedCancelIds([]);
    setLoading(true);
    client
      .get('/api/purchase-orders/transactions', { params: { limit: LIMIT_UNFILTERED, offset: 0 } })
      .then((res) => setTransactions(res.data?.data || []))
      .catch(() => setTransactions([]))
      .finally(() => setLoading(false));
  };

  const openPoDetails = (tx) => {
    setPopup({
      id: tx.autoAllocateTransID,
      transactionNo: tx.transactionNo || 'PO',
      details: null,
      loading: true,
    });
    client
      .get(`/api/purchase-orders/transactions/${tx.autoAllocateTransID}/details`)
      .then((res) => {
        setPopup((prev) =>
          prev ? { ...prev, details: res.data?.data || [], loading: false } : null,
        );
      })
      .catch(() => {
        setPopup((prev) => (prev ? { ...prev, details: [], loading: false } : null));
      });
  };

  const toggleCancelSelection = (id) => {
    if (!id || cancellingBatch) return;
    setSelectedCancelIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const cancelSelectedScheduled = async () => {
    const toCancel = transactions.filter(
      (t) =>
        t.status === 'SCHEDULED' &&
        t.autoAllocateTransID &&
        selectedCancelIds.includes(t.autoAllocateTransID),
    );
    if (toCancel.length === 0) return;
    if (
      !window.confirm(
        `Cancel ${toCancel.length} scheduled order(s)? They will not be sent to the vendor.`,
      )
    ) {
      return;
    }
    setCancellingBatch(true);
    try {
      for (const tx of toCancel) {
        await client.patch(`/api/purchase-orders/transactions/${tx.autoAllocateTransID}/cancel`);
      }
      setSelectedCancelIds([]);
      await fetchTransactions();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : err.message || 'Could not cancel order';
      window.alert(msg);
      await fetchTransactions();
    } finally {
      setCancellingBatch(false);
    }
  };

  const closePopup = () => setPopup(null);

  const toggleLocationCode = (code) => {
    setFilters((f) => {
      const next = new Set(f.locationCodes);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return { ...f, locationCodes: Array.from(next) };
    });
  };

  const selectAllLocations = () => {
    setFilters((f) => ({
      ...f,
      locationCodes: filterOptions.locations.map((loc) => loc.code),
    }));
  };

  const clearLocationFilter = () => {
    setFilters((f) => ({ ...f, locationCodes: [] }));
  };

  return (
    <div className="review-auto-allocated">
      <div className="review-auto-allocated-inner">
        <section className="review-section-card">
          <h2>Review Auto Allocated Orders</h2>
          <p className="section-note">
            {hasActiveFilters
              ? `Showing matching orders (up to ${LIMIT_FILTERED.toLocaleString()} rows). Refine filters and click Apply.`
              : `Showing the ${LIMIT_UNFILTERED} most recent transactions. Apply one or more filters to search the full history (up to ${LIMIT_FILTERED.toLocaleString()} rows).`}{' '}
            Dates for &quot;Set submit&quot; and &quot;Submitted&quot; use the stored UTC calendar
            day. Click a PO number for product details.
          </p>
          <div className="review-actions">
            <Link to="/auto-allocation" className="link-to-auto-allocation">
              ← Auto Allocation
            </Link>
            <button
              type="button"
              onClick={fetchTransactions}
              disabled={loading}
              className="refresh-transactions-btn"
            >
              {loading ? 'Loading...' : 'Refresh'}
            </button>
            <button
              type="button"
              onClick={() =>
                downloadAsExcel(transactions, formatDateDisplay, formatDateTimeDisplay)
              }
              disabled={transactions.length === 0}
              className="review-download-btn"
              title="Download filtered data as Excel"
            >
              Download Excel
            </button>
            <button
              type="button"
              onClick={() => downloadAsPdf(transactions, formatDateDisplay, formatDateTimeDisplay)}
              disabled={transactions.length === 0}
              className="review-download-btn"
              title="Download filtered data as PDF"
            >
              Download PDF
            </button>
            <button
              type="button"
              onClick={cancelSelectedScheduled}
              disabled={cancellableSelectedCount === 0 || loading || cancellingBatch}
              className="review-download-btn review-bulk-cancel-btn"
              title="Cancel selected scheduled orders (not yet submitted)"
            >
              {cancellingBatch ? 'Cancelling…' : 'Cancel'}
            </button>
          </div>

          <div className="review-filters">
            <div className="review-filters-row">
              <label className="review-filter-label">
                <span>State</span>
                <select
                  value={filters.state}
                  onChange={(e) => setFilters((f) => ({ ...f, state: e.target.value }))}
                  className="review-filter-select"
                >
                  <option value="">All</option>
                  {filterOptions.states.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label className="review-filter-label">
                <span>Market</span>
                <select
                  value={filters.market}
                  onChange={(e) => setFilters((f) => ({ ...f, market: e.target.value }))}
                  className="review-filter-select"
                >
                  <option value="">All</option>
                  {filterOptions.markets.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
              <label className="review-filter-label">
                <span>Vendor</span>
                <select
                  value={filters.vendor}
                  onChange={(e) => setFilters((f) => ({ ...f, vendor: e.target.value }))}
                  className="review-filter-select"
                >
                  <option value="">All</option>
                  {filterOptions.vendors.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <div
                className="review-filter-label review-filter-label-location"
                ref={locationMenuRef}
              >
                <span id="review-location-filter-label">Locations</span>
                <div className="review-location-dropdown">
                  <button
                    type="button"
                    id="review-location-dropdown-trigger"
                    className="review-filter-select review-location-dropdown-trigger"
                    aria-expanded={locationMenuOpen}
                    aria-haspopup="dialog"
                    aria-controls="review-location-dropdown-panel"
                    onClick={() => setLocationMenuOpen((o) => !o)}
                  >
                    <span className="review-location-dropdown-trigger-text">
                      {filters.locationCodes.length === 0
                        ? 'All'
                        : `${filters.locationCodes.length} selected`}
                    </span>
                    <span className="review-location-dropdown-chevron" aria-hidden>
                      {locationMenuOpen ? '▲' : '▼'}
                    </span>
                  </button>
                  {locationMenuOpen ? (
                    <div
                      id="review-location-dropdown-panel"
                      className="review-location-dropdown-panel"
                      role="dialog"
                      aria-labelledby="review-location-filter-label"
                    >
                      <div className="review-location-filter-toolbar review-location-dropdown-toolbar">
                        <input
                          type="search"
                          className="review-location-dropdown-search"
                          placeholder="Search name or code…"
                          value={locationDropdownSearch}
                          onChange={(e) => setLocationDropdownSearch(e.target.value)}
                          aria-label="Filter locations in list by name or code"
                        />
                        <div className="review-location-filter-toolbar-actions">
                          <button
                            type="button"
                            className="review-location-toolbar-btn"
                            onClick={selectAllLocations}
                            disabled={filterOptions.locations.length === 0}
                          >
                            Select all
                          </button>
                          <button
                            type="button"
                            className="review-location-toolbar-btn"
                            onClick={clearLocationFilter}
                            disabled={filters.locationCodes.length === 0}
                          >
                            Clear all
                          </button>
                          <button
                            type="button"
                            className="review-filter-btn apply review-location-dropdown-apply"
                            onClick={applyFromLocationDropdown}
                            disabled={loading}
                          >
                            Apply
                          </button>
                        </div>
                      </div>
                      <div
                        className="review-location-table-scroll review-location-table-scroll--dropdown"
                        role="group"
                        aria-label="Select locations to filter"
                      >
                        {filterOptions.locations.length === 0 ? (
                          <p className="review-location-empty">
                            No locations to show. Active company sites load from the locations API;
                            if that is empty, locations that appear in auto-allocation history are
                            used instead.
                          </p>
                        ) : filteredLocationsForDropdown.length === 0 ? (
                          <p className="review-location-empty">No locations match your search.</p>
                        ) : (
                          <table className="review-location-table">
                            <thead>
                              <tr>
                                <th className="review-location-th-check" scope="col">
                                  <span className="review-location-th-sr-only">Select</span>
                                </th>
                                <th className="review-location-th-name" scope="col">
                                  Location
                                </th>
                                <th className="review-location-th-code" scope="col">
                                  Code
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              {filteredLocationsForDropdown.map((loc) => (
                                <tr key={loc.code} className="review-location-data-row">
                                  <td className="review-location-td-check">
                                    <input
                                      type="checkbox"
                                      checked={filters.locationCodes.includes(loc.code)}
                                      onChange={() => toggleLocationCode(loc.code)}
                                      aria-label={`${loc.name || loc.code}, code ${loc.code}`}
                                    />
                                  </td>
                                  <td
                                    className="review-location-td-name"
                                    title={loc.name || loc.code}
                                  >
                                    {loc.name || loc.code}
                                  </td>
                                  <td className="review-location-td-code" title={loc.code}>
                                    {loc.code}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
              <label className="review-filter-label">
                <span>Order status</span>
                <select
                  value={filters.transactionStatus}
                  onChange={(e) => setFilters((f) => ({ ...f, transactionStatus: e.target.value }))}
                  className="review-filter-select"
                  aria-label="Filter by order status or not yet submitted"
                >
                  <option value="">All</option>
                  <option value={ORDER_STATUS_NOT_YET_SUBMITTED}>Not yet submitted</option>
                  {(filterOptions.statuses || [])
                    .filter((s) => s !== ORDER_STATUS_NOT_YET_SUBMITTED)
                    .map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                </select>
              </label>
            </div>

            <div className="review-filters-date-groups">
              <fieldset className="review-date-fieldset">
                <legend>Expected delivery</legend>
                <div className="review-date-pair">
                  <label>
                    <span className="review-date-label">From</span>
                    <input
                      type="date"
                      value={filters.expectedDeliveryFrom}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, expectedDeliveryFrom: e.target.value }))
                      }
                      className="review-filter-input"
                    />
                  </label>
                  <label>
                    <span className="review-date-label">To</span>
                    <input
                      type="date"
                      value={filters.expectedDeliveryTo}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, expectedDeliveryTo: e.target.value }))
                      }
                      className="review-filter-input"
                    />
                  </label>
                </div>
              </fieldset>
              <fieldset className="review-date-fieldset">
                <legend>Set submit date (scheduled trigger)</legend>
                <div className="review-date-pair">
                  <label>
                    <span className="review-date-label">From</span>
                    <input
                      type="date"
                      value={filters.setOrderDateFrom}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, setOrderDateFrom: e.target.value }))
                      }
                      className="review-filter-input"
                    />
                  </label>
                  <label>
                    <span className="review-date-label">To</span>
                    <input
                      type="date"
                      value={filters.setOrderDateTo}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, setOrderDateTo: e.target.value }))
                      }
                      className="review-filter-input"
                    />
                  </label>
                </div>
              </fieldset>
              <fieldset className="review-date-fieldset">
                <legend>Submitted date (sent to vendor)</legend>
                <div className="review-date-pair">
                  <label>
                    <span className="review-date-label">From</span>
                    <input
                      type="date"
                      value={filters.submittedDateFrom}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, submittedDateFrom: e.target.value }))
                      }
                      className="review-filter-input"
                    />
                  </label>
                  <label>
                    <span className="review-date-label">To</span>
                    <input
                      type="date"
                      value={filters.submittedDateTo}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, submittedDateTo: e.target.value }))
                      }
                      className="review-filter-input"
                    />
                  </label>
                </div>
              </fieldset>
            </div>

            <div className="review-filters-row">
              <label className="review-filter-label review-filter-label-wide">
                <span>PO number (partial match)</span>
                <input
                  type="text"
                  value={filters.poNumber}
                  onChange={(e) => setFilters((f) => ({ ...f, poNumber: e.target.value }))}
                  placeholder="e.g. PO97"
                  className="review-filter-input"
                />
              </label>
            </div>

            <div className="review-filters-actions">
              <button
                type="button"
                onClick={applyFilters}
                disabled={loading}
                className="review-filter-btn apply"
              >
                Apply
              </button>
              <button type="button" onClick={clearFilters} className="review-filter-btn clear">
                Clear
              </button>
            </div>
          </div>

          <div className="transactions-table-wrap">
            <table className="transactions-table">
              <thead>
                <tr>
                  <th>Select</th>
                  <th>Status</th>
                  <th>State</th>
                  <th>Market</th>
                  <th>Vendor</th>
                  <th>Distribution Center</th>
                  <th>Acc Code</th>
                  <th>Location Name</th>
                  <th>Expected Delivery Date</th>
                  <th>Expected Delivery Day</th>
                  <th>Set Submit Date</th>
                  <th>Submitted Date</th>
                  <th>PO Number</th>
                  <th>Confirmed Received</th>
                </tr>
              </thead>
              <tbody>
                {transactions.length === 0 && !loading && (
                  <tr>
                    <td colSpan={14} className="empty-table-msg">
                      No transactions yet. Submit an order from Auto Allocation.
                    </td>
                  </tr>
                )}
                {transactions.map((tx, idx) => (
                  <tr key={tx.autoAllocateTransID ?? idx}>
                    <td className="td-checkbox td-select">
                      {tx.status === 'SCHEDULED' && tx.autoAllocateTransID ? (
                        <input
                          type="checkbox"
                          checked={selectedCancelIds.includes(tx.autoAllocateTransID)}
                          onChange={() => toggleCancelSelection(tx.autoAllocateTransID)}
                          disabled={cancellingBatch}
                          aria-label={`Select scheduled order ${
                            tx.transactionNo || tx.autoAllocateTransID
                          } for cancel`}
                        />
                      ) : (
                        <span className="review-select-placeholder" aria-hidden="true">
                          —
                        </span>
                      )}
                    </td>
                    <td>{tx.status ?? '—'}</td>
                    <td>{tx.state ?? '—'}</td>
                    <td>{tx.market ?? '—'}</td>
                    <td>{tx.vendorName ?? '—'}</td>
                    <td>{tx.distributionCenter ?? '—'}</td>
                    <td>{tx.accountNumber ?? '—'}</td>
                    <td>{tx.locationName ?? tx.locationCode ?? '—'}</td>
                    <td>
                      {tx.setExpectedDeliveryDate
                        ? formatDateDisplay(tx.setExpectedDeliveryDate) || '—'
                        : '—'}
                    </td>
                    <td>{tx.setExpectedDeliveryDOW ?? '—'}</td>
                    <td>
                      {tx.setOrderDateTme ? formatDateTimeDisplay(tx.setOrderDateTme) || '—' : '—'}
                    </td>
                    <td>
                      {tx.submittedDateTime
                        ? formatDateTimeDisplay(tx.submittedDateTime) || '—'
                        : '—'}
                    </td>
                    <td>
                      {tx.transactionNo ? (
                        <button
                          type="button"
                          onClick={() => openPoDetails(tx)}
                          className="po-number-link"
                          title="View product details"
                        >
                          {tx.transactionNo}
                        </button>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="td-confirmed-received">
                      {isVendorConfirmReceived(tx) ? (
                        <span
                          title={
                            tx.confirmRecievedDateTime
                              ? formatDateTimeDisplay(tx.confirmRecievedDateTime) ||
                                'Confirmed received by vendor'
                              : 'Confirmed received by vendor'
                          }
                        >
                          Confirmed
                        </span>
                      ) : (
                        <span className="review-confirmed-placeholder">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {popup && (
        <div
          className="po-details-overlay"
          onClick={closePopup}
          role="dialog"
          aria-modal="true"
          aria-labelledby="po-details-title"
        >
          <div className="po-details-modal" onClick={(e) => e.stopPropagation()}>
            <div className="po-details-header">
              <h3 id="po-details-title">PO {popup.transactionNo} – Product details</h3>
              <button
                type="button"
                onClick={closePopup}
                className="po-details-close"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div className="po-details-body">
              {popup.loading ? (
                <p className="po-details-loading">Loading…</p>
              ) : (
                <table className="po-details-table">
                  <thead>
                    <tr>
                      <th>Product Number</th>
                      <th>Product Name</th>
                      <th>Vendor Unit</th>
                      <th>Qty</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(!popup.details || popup.details.length === 0) && (
                      <tr>
                        <td colSpan={4} className="empty-table-msg">
                          No line items.
                        </td>
                      </tr>
                    )}
                    {(popup.details || []).map((row, i) => (
                      <tr key={i}>
                        <td>{row.productNumber ?? '—'}</td>
                        <td>{row.productName ?? '—'}</td>
                        <td>{row.vendorUnit ?? '—'}</td>
                        <td>{row.orderQuantity ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
