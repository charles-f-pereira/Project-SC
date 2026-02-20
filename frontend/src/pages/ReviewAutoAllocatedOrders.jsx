import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import client from '../api/client.js';
import './ReviewAutoAllocatedOrders.css';

const DEFAULT_LIMIT = 100;

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

  const fetchTransactions = useCallback(() => {
    setLoading(true);
    const params = { limit: DEFAULT_LIMIT, offset: 0 };
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
  }, [filters]);

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
            Last {DEFAULT_LIMIT} transactions (ordered by newest). Use filters to narrow. Click a PO
            number to view product details.
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
                    <td colSpan={11} className="empty-table-msg">
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
                    <td>{tx.locationName ?? tx.locationCode ?? '—'}</td>
                    <td>
                      {tx.setExpectedDeliveryDate
                        ? String(tx.setExpectedDeliveryDate).slice(0, 10)
                        : '—'}
                    </td>
                    <td>{tx.setExpectedDeliveryDOW ?? '—'}</td>
                    <td>
                      {tx.setOrderDateTme
                        ? new Date(tx.setOrderDateTme).toLocaleString(undefined, {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            hour12: false,
                          })
                        : '—'}
                    </td>
                    <td>
                      {tx.submittedDateTime
                        ? new Date(tx.submittedDateTime).toLocaleString(undefined, {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            hour12: false,
                          })
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
                    <td className="td-checkbox">
                      <input
                        type="checkbox"
                        checked={!!tx.confirmReceivedStatus}
                        disabled
                        title="Future: confirmed received by vendor"
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
