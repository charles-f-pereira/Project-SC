import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import * as XLSX from 'xlsx';
import client from '../api/client.js';
import { formatDateDisplay, formatDateTimeDisplay } from '../utils/dateFormat.js';
import './ReviewAutoAllocatedOrders.css';

const DEFAULT_LIMIT = 100;
/** When any filter is applied, request up to this many rows so filtered results are not capped at 100 */
const FILTERED_LIMIT = 500;

function exportFilename(ext) {
  const yyyy = new Date().getFullYear();
  const mm = String(new Date().getMonth() + 1).padStart(2, '0');
  const dd = String(new Date().getDate()).padStart(2, '0');
  return `review-auto-allocated-orders-${yyyy}-${mm}-${dd}.${ext}`;
}

function downloadAsExcel(transactions, formatDateDisplayFn, formatDateTimeDisplayFn) {
  const headers = [
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
  ];
  const rows = transactions.map((tx) => [
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
    tx.confirmReceivedStatus ?? '',
  ]);
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
  XLSX.utils.book_append_sheet(wb, ws, 'Review');
  XLSX.writeFile(wb, exportFilename('xlsx'));
}

function downloadAsPdf(transactions, formatDateDisplayFn, formatDateTimeDisplayFn) {
  const headers = [
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
  ];
  const body = transactions.map((tx) => [
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
    tx.confirmReceivedStatus ?? '',
  ]);
  const doc = new jsPDF({ orientation: 'landscape' });
  autoTable(doc, {
    head: [headers],
    body,
    styles: { fontSize: 7 },
  });
  doc.save(exportFilename('pdf'));
}

export default function ReviewAutoAllocatedOrders() {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filterOptions, setFilterOptions] = useState({
    states: [],
    markets: [],
    vendors: [],
    locations: [],
  });
  const [filters, setFilters] = useState({
    state: '',
    market: '',
    vendor: '',
    location: '',
    fromDate: '',
    toDate: '',
    poNumber: '',
    notSubmitted: false,
  });
  const [popup, setPopup] = useState(null);

  const fetchFilterOptions = useCallback(() => {
    client
      .get('/api/purchase-orders/transactions/filter-options')
      .then((res) =>
        setFilterOptions(res.data || { states: [], markets: [], vendors: [], locations: [] }),
      )
      .catch(() => setFilterOptions({ states: [], markets: [], vendors: [], locations: [] }));
  }, []);

  const hasActiveFilters = !!(
    filters.state ||
    filters.market ||
    filters.vendor ||
    filters.location ||
    filters.fromDate ||
    filters.toDate ||
    (filters.poNumber && filters.poNumber.trim()) ||
    filters.notSubmitted
  );

  const fetchTransactions = useCallback(() => {
    setLoading(true);
    const limit = hasActiveFilters ? FILTERED_LIMIT : DEFAULT_LIMIT;
    const params = { limit, offset: 0 };
    if (filters.state) params.state = filters.state;
    if (filters.market) params.market = filters.market;
    if (filters.vendor) params.vendor = filters.vendor;
    if (filters.location) params.location = filters.location;
    if (filters.fromDate) params.from_date = filters.fromDate;
    if (filters.toDate) params.to_date = filters.toDate;
    if (filters.poNumber && filters.poNumber.trim()) params.po = filters.poNumber.trim();
    if (filters.notSubmitted) params.not_submitted = true;
    client
      .get('/api/purchase-orders/transactions', { params })
      .then((res) => setTransactions(res.data?.data || []))
      .catch(() => setTransactions([]))
      .finally(() => setLoading(false));
  }, [filters, hasActiveFilters]);

  useEffect(() => {
    fetchFilterOptions();
  }, [fetchFilterOptions]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  const applyFilters = () => {
    fetchTransactions();
  };

  const clearFilters = () => {
    setFilters({
      state: '',
      market: '',
      vendor: '',
      location: '',
      fromDate: '',
      toDate: '',
      poNumber: '',
      notSubmitted: false,
    });
    setLoading(true);
    client
      .get('/api/purchase-orders/transactions', { params: { limit: DEFAULT_LIMIT, offset: 0 } })
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

  const closePopup = () => setPopup(null);

  return (
    <div className="review-auto-allocated">
      <div className="review-auto-allocated-inner">
        <section className="review-section-card">
          <h2>Review Auto Allocated Orders</h2>
          <p className="section-note">
            Last {hasActiveFilters ? FILTERED_LIMIT : DEFAULT_LIMIT} transactions
            {hasActiveFilters ? ' (with filters applied)' : ' (ordered by newest)'}. Use filters to
            narrow. Click a PO number to view product details.
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
              <label className="review-filter-label">
                <span>Location</span>
                <select
                  value={filters.location}
                  onChange={(e) => setFilters((f) => ({ ...f, location: e.target.value }))}
                  className="review-filter-select"
                >
                  <option value="">All</option>
                  {filterOptions.locations.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </label>
              <label className="review-filter-label">
                <span>From date</span>
                <input
                  type="date"
                  value={filters.fromDate}
                  onChange={(e) => setFilters((f) => ({ ...f, fromDate: e.target.value }))}
                  className="review-filter-input"
                />
              </label>
              <label className="review-filter-label">
                <span>To date</span>
                <input
                  type="date"
                  value={filters.toDate}
                  onChange={(e) => setFilters((f) => ({ ...f, toDate: e.target.value }))}
                  className="review-filter-input"
                />
              </label>
              <label className="review-filter-label">
                <span>PO Number</span>
                <input
                  type="text"
                  value={filters.poNumber}
                  onChange={(e) => setFilters((f) => ({ ...f, poNumber: e.target.value }))}
                  placeholder="e.g. PO97"
                  className="review-filter-input"
                />
              </label>
              <label className="review-filter-label review-filter-checkbox-label">
                <input
                  type="checkbox"
                  checked={filters.notSubmitted}
                  onChange={(e) => setFilters((f) => ({ ...f, notSubmitted: e.target.checked }))}
                  className="review-filter-checkbox"
                  aria-label="Show only orders not yet submitted"
                />
                <span>Not yet submitted</span>
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
                    <td colSpan={12} className="empty-table-msg">
                      No transactions yet. Submit an order from Auto Allocation.
                    </td>
                  </tr>
                )}
                {transactions.map((tx, idx) => (
                  <tr key={tx.autoAllocateTransID ?? idx}>
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
                    <td className="td-checkbox td-confirmed-received">
                      <input
                        type="checkbox"
                        checked={!!tx.confirmReceivedStatus}
                        disabled
                        title="Confirmed received by vendor"
                        aria-label="Confirmed received"
                      />
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
