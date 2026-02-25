# Project SC - Ordering & Delivery Schedule & Purchase Order Administration

## Project Overview

Project SC is a web application that enables corporate head office staff—in particular the **Supply Chain (SC) team**—to:

1. **Administer ordering and delivery schedules** for 250+ restaurants across 10+ vendors, with calendar-based visualization and public holiday overlays.
2. **Place batch/bulk purchase orders** on behalf of restaurants/locations so that products (e.g. a new sauce) are delivered by the time new product launches (e.g. new menu item with the new sauce).

The application integrates with existing Crunchtime systems and provides a unified interface for vendor–location–distribution center relationships, schedule management, and purchase order processing.

## Objectives

- Centralize ordering and delivery schedule management for 250+ restaurant locations
- Support 10+ vendors with multiple distribution centers (typically state-based, but flexible)
- **Allow the SC team to place batch/bulk purchase orders** for products (e.g. new sauce) so delivery aligns with product launch timing
- Integrate with existing Crunchtime API infrastructure from Project-CT
- Provide calendar-based visualization with public holiday overlays
- Enable efficient filtering and viewing of schedules by location, vendor, state, DC, and delivery days
- **Phase 1 (PO):** Integrate product catalog and vendor pricing from Crunchtime, and submit purchase orders via Crunchtime APIs
- Future: Support vendor schedule imports in various formats

## Scope & Framework in Place

The following is in place or in progress for Project SC:

| # | Area | Status |
|---|------|--------|
| 1 | Location details | In place |
| 2 | Vendor details | In place |
| 3 | Distribution centres | In place |
| 4 | Expected order & delivery dates | In place (calendar; order/delivery pairing refinement parked for later) |
| 5 | Product details | **New** – Phase 1 |
| 6 | Purchase order processing | **New** – Phase 1 |

**Batch purchase order use case (Phase 1):** The SC team will place batch/bulk purchase orders for a **new product (e.g. a sauce)** so that the sauce is delivered to each restaurant/location by the time the **new product with the new sauce launches**. The existing location, vendor, DC, and schedule data will support selecting locations, vendors, and timing for these orders.

## Technical Architecture

### Backend (FastAPI)
- **Framework**: FastAPI (Python) - consistent with Project-CT
- **API Integration**: 
  - Crunchtime API endpoints (reuse connection patterns from Project-CT)
  - Public Holidays API (api-ninjas.com)
- **Scheduling**: APScheduler runs inside the FastAPI process; a job every 2 minutes processes SCHEDULED purchase orders (submits to Crunchtime when trigger time has passed, with 5×5‑minute retries on failure).
- **Structure**: 
  - `/backend/app/core/` - Configuration and API clients
  - `/backend/app/schedules/` - Schedule management routes
  - `/backend/app/vendors/` - Vendor and DC management
  - `/backend/app/locations/` - Location management
  - `/backend/app/holidays/` - Public holiday integration
  - `/backend/app/products/` - Product catalog (Phase 1; getAllCompanyProductsEnhancedV1, getAllVendorProductPricing)
  - `/backend/app/purchase_orders/` - Purchase order processing (Phase 1; savePurchaseOrders)
  - `/backend/app/scheduler.py` - Scheduled PO job (APScheduler)

### Frontend (React + Vite)
- **Framework**: React with Vite (consistent with Project-CT vendor_frontend)
- **Key Components**:
  - Schedule Calendar View
  - Filter Panel (Location, Vendor, State, DC, Days)
  - Location/Vendor Selector
  - Holiday Overlay Visualization
- **State Management**: React Context or Zustand for filter state
- **Calendar Library**: Consider react-big-calendar or similar

### Data Flow

```
Crunchtime APIs → FastAPI Backend → React Frontend
Public Holidays API → FastAPI Backend → React Frontend (Calendar Overlay)
```

### PostgreSQL transaction store (Auto Allocation)

Transactional records for Auto Allocation submissions are persisted in PostgreSQL for audit and future EDI/workflow use.

- **Database:** `GYG-CT-Helper`
- **Schema:** `CTH`
- **Credentials (in `.env`):** `pgName` (username), `pgPassword` (password). Optionally `pgHost`, `pgPort`, `pgDatabase` if not using defaults.

**Tables:**

| Table | Purpose |
|-------|--------|
| `CTH.autoAllocationTransHdr` | One row **per location**. Auto Allocation may generate multiple locations in one batch; submission to Crunchtime `savePurchaseOrders` is done per location; each location gets a unique `autoAllocateTransID`. Each row stores: **country, state, locationCode, locationName, market** (from the selected location, sent by the frontend in `location_details`); **vendorCode, vendorName** (vendor name from frontend); distribution centre; `createDateTime` (UTC); `setOrderDateTme` (UTC); `setExpectedDeliveryDate`, `setExpectedDeliveryDOW`; `submittedDateTime` (UTC); `transactionNo` from Crunchtime `orderNumber`. **Workflow:** `status` (`SCHEDULED` | `SUBMITTED` | `FAILED`); `submission_attempts`, `last_attempt_at`, `failure_reason` (for retries and future alerting); `alert_sent_at` (when a failure alert was sent; reserved for future use). Future: `submitUserId`, `vendorEdiFlag`, `confirmReceivedStatus`, `confirmRecievedDateTime`. |
| `CTH.autoAllocationTransDtl` | Line items per header: **productNumber** (company product number), product name, vendor unit, order quantity, **vendorProductNumber** (for Crunchtime replay when submitting scheduled POs). Vendor is on the header only (no vendorCode column in detail). `autoAllocateTransID` references `autoAllocationTransHdr.autoAllocateTransID`. |

- **Timestamps:** All stored in UTC. The front end displays order date/time in AEST/AEDT; `setOrderDateTme` is stored in UTC.
- **Multi-location:** The Auto Allocation flow can select multiple locations and one vendor/product set. When submitting via `https://webservices-test.net-chef.com/purchaseorder/v1/savePurchaseOrders` (when implemented), the backend will call the Crunchtime API **per location**. Each such submission is persisted as a separate header row (unique `autoAllocateTransID`) with that location’s code/name and its associated detail rows. So `locationCode` and `locationName` in each header row hold a single location; multiple locations result in multiple header rows.
- **Crunchtime:** After each successful per-location call to `savePurchaseOrders`, the response `orderNumber` is recorded in that header’s `transactionNo`.

**Order date/time (trigger time):** Order date/time is interpreted as **Sydney time (AEST/AEDT)** and is the time when the order is sent to the vendor (or shortly after). The user can schedule up to **14 days ahead**. If the chosen time is within **5 minutes of “now”** (Sydney), the backend treats it as **submit now**: it calls Crunchtime immediately and records the row with `status = SUBMITTED` and `setOrderDateTme` = actual submit time (UTC). If the chosen time is later, the row is stored with `status = SCHEDULED` and `setOrderDateTme` = that time in UTC; a background job (APScheduler inside the FastAPI app) runs every 2 minutes and submits those rows to Crunchtime when `setOrderDateTme <= now` (UTC). Failed submissions are retried up to **5 times**, **5 minutes apart**; after 5 failures the row is set to `status = FAILED` with `failure_reason` and `last_attempt_at` (for future alerting). The `alert_sent_at` column is reserved for when a failure alert is sent.

**SQL script:** [`backend/sql/cth_auto_allocation_tables.sql`](backend/sql/cth_auto_allocation_tables.sql) — run against the database to create the schema and tables. For existing databases, [`backend/sql/migrate_scheduled_po_columns.sql`](backend/sql/migrate_scheduled_po_columns.sql) adds the workflow and replay columns.

### Product catalogue (CTH)

Tables for a local product catalogue built from Crunchtime **getAllCompanyProductsEnhanced** (or **getCompanyProductsEnhancedByPage**) and **getAllCategories**, used in a later phase to support efficient product search and filter (e.g. by concept, department, UDC, category) without requiring an explicit product name/number on every API call.

| Table | Purpose |
|-------|--------|
| `CTH.CompanyProduct` | One row per company product; columns from `companyProductEnhancedHeaderDetails` (number, name, active_flag, category_name, subcategory_name, microcategory_name, etc.; optional raw_json JSONB). |
| `CTH.Concept` | Lookup from `companyProductEnhancedConceptDetails` (code, active_flag). Filter products by concept. |
| `CTH.Department` | Lookup from `companyProductEnhancedDepartmentDetails` (code, active_flag). Filter by department. |
| `CTH.UserDefinedCategories` | Lookup from `companyProductEnhancedUserDefinedCategoryDetails` (code, active_flag). Filter by UDC. |
| `CTH.Categories` | From **getAllCategories** `category/v1/getAllCategories`; one row per `categoryDetailDetails` element (category_name, subcategory_name, microcategory_name, gl_description, gl_number). |
| `CTH.CompanyProductConcept`, `CTH.CompanyProductDepartment`, `CTH.CompanyProductUserDefinedCategory` | Junction tables (many-to-many) linking products to concepts, departments, and UDCs. |

**SQL script:** [`backend/sql/cth_product_catalogue_tables.sql`](backend/sql/cth_product_catalogue_tables.sql) — run after the Auto Allocation script (schema CTH already exists). Catalogue load/sync (Python calling the APIs and populating these tables) and product search/filter using them are planned for a later phase.

## Crunchtime API Endpoints

### Required Endpoints (from Project-CT patterns)

1. **CRUNCHTIME_LOCATION_TOKEN_TEST**
   - Endpoint: `/location/v1/getAllLocations`
   - Purpose: List active restaurants/locations
   - Usage: Populate location selector, filter by activeFlag

2. **CRUNCHTIME_HIERARCHY_TOKEN_TEST**
   - Endpoint: `/hierarchy/v1/*` (specific endpoint TBD)
   - Purpose: Define and link locations to vendor distribution centers
   - Usage: Build location → vendor → DC relationships

3. **CRUNCHTIME_VENDOR_TOKEN_TEST**
   - Endpoint: `/vendor/v1/*` (specific endpoint TBD)
   - Purpose: List active vendors and their details
   - Usage: Vendor selector, vendor information display

4. **CRUNCHTIME_VENDOR_LOCATION_TOKEN_TEST**
   - Endpoint: `/vendorlocation/v1/*` (specific endpoint TBD)
   - Purpose: 
     - Define location-vendor relationships
     - Retrieve standard delivery schedules (`vendorLocationScheduleDetail`)
     - Retrieve schedule overrides (`scheduleOverrideRowList`) for holiday periods
   - Usage: Primary data source for schedule display and management

### Phase 1 – Product & Purchase Order Endpoints (New)

The following Crunchtime API endpoints are required for Phase 1 batch purchase order functionality. Patterns and references may exist in **Project-CT**; they will be implemented or extended in this project.

1. **getAllCompanyProductsEnhancedV1** / **getCompanyProductsEnhancedByPage**
   - Purpose: Build the list of **products available in Crunchtime**; also used to build the local product catalogue in CTH (CompanyProduct, Concept, Department, UserDefinedCategories).
   - Usage: Populate product catalog / product definition list; for large datasets, **getCompanyProductsEnhancedByPage** (paginated) is recommended for catalogue build to avoid timeouts and memory issues.
   - Reference: [Crunchtime API – getAllCompanyProductsEnhancedV1](https://developer.crunchtime.com/reference/getallcompanyproductsenhancedv1usingget), [getCompanyProductsEnhancedByPage](https://developer.crunchtime.com/reference/getcompanyproductsenhancedbypagev1usingget).

2. **getAllCategories** (category/v1/getAllCategories)
   - Purpose: Build the **category catalogue** stored in `CTH.Categories` for product filters.
   - Token: `CRUNCHTIME_CATEGORY_TOKEN_TEST` (optional in .env).
   - Reference: [Crunchtime API – getAllCategories](https://developer.crunchtime.com/reference/getallcategoryv1usingget).

3. **getAllVendorProductPricing**
   - Purpose: Retrieve **vendor-specific data** (e.g. pricing, availability) for products from the `getAllCompanyProductsEnhancedV1` dataset.
   - Usage: Show vendor-specific product options and pricing when placing purchase orders for a given vendor/location.

4. **savePurchaseOrders**
   - Purpose: **Submit/place purchase orders** in Crunchtime.
   - Usage: Allow the SC team to place batch/bulk purchase orders (e.g. for the new sauce) so that orders are recorded in Crunchtime and can be fulfilled by the vendor for delivery to the restaurant/location by launch date.

### API Configuration (from Project-CT)

Reuse the existing configuration pattern:
- Environment variables: `.env` file with tokens
- Base URL: `https://webservices-test.net-chef.com` (test) or `https://webservices.net-chef.com` (prod)
- Headers: `authenticationtoken`, `sitename`, `userid`, `password`
- SSL: Windows truststore integration for corporate networks

## External API Integration

### Public Holidays API
- **Provider**: api-ninjas.com
- **Endpoint**: `https://api.api-ninjas.com/v1/publicholidays?country=AU`
- **Purpose**: Overlay public holidays on calendar view
- **Authentication**: API key (to be provided)
- **Usage**: Fetch holidays for current year, display on calendar, highlight affected delivery days

## Data Models

### Core Entities

1. **Location**
   - Code, Name, State, Active Flag
   - Linked to vendors via VendorLocation

2. **Vendor**
   - Code, Name, Details
   - Multiple Distribution Centers

3. **Distribution Center (DC)**
   - Code, Name, State (typically, but flexible)
   - Belongs to Vendor
   - Linked to Locations via Hierarchy

4. **VendorLocation**
   - Links Location to Vendor/DC
   - Contains standard schedule (`vendorLocationScheduleDetail`)
   - Contains schedule overrides (`scheduleOverrideRowList`)

5. **Schedule**
   - Standard delivery days/times
   - Ordering days/times
   - Override periods (holidays)

6. **Public Holiday**
   - Date, Name, Country
   - Used to identify override periods

7. **Product (New – Phase 1)**
   - Sourced from Crunchtime `getAllCompanyProductsEnhancedV1`
   - Product definitions available to order; used when compiling purchase order line items (e.g. new sauce).

8. **Vendor Product Pricing (New – Phase 1)**
   - Sourced from Crunchtime `getAllVendorProductPricing`
   - Vendor-specific product data (e.g. pricing, codes) for products from the company product list.

9. **Purchase Order (New – Phase 1)**
   - Created by the SC team; submitted via Crunchtime `savePurchaseOrders`.
   - Links location(s), vendor, product(s), quantities, and timing so that delivery aligns with product launch (e.g. sauce delivered by launch date).

## Phase 1 Requirements

### Core Functionality

1. **Location & Vendor Selection**
   - Multi-select location picker (filter by active)
   - Multi-select vendor picker
   - State filter (derived from locations)
   - DC filter (derived from hierarchy)

2. **Schedule Display**
   - Calendar view showing delivery schedules
   - Filter by delivery days of the week
   - Filter by ordering days of the week
   - Display standard schedules from `vendorLocationScheduleDetail`

3. **Filtering System**
   - Location (multi-select)
   - Vendor (multi-select)
   - State (multi-select)
   - Distribution Center (multi-select)
   - Delivery Days (checkboxes: Mon-Sun)
   - Ordering Days (checkboxes: Mon-Sun)

4. **Data Integration**
   - Fetch locations from Crunchtime
   - Fetch vendors from Crunchtime
   - Fetch vendor-location relationships
   - Fetch standard schedules
   - Cache data appropriately (consider 30min TTL like recipes in Project-CT)

5. **Phase 1 – Product & Purchase Order (New)**
   - **Product catalog:** Integrate `getAllCompanyProductsEnhancedV1` to build the list of product definitions available to order (e.g. for the new sauce).
   - **Vendor product pricing:** Integrate `getAllVendorProductPricing` to retrieve vendor-specific product data for the company product list.
   - **Purchase orders:** Integrate `savePurchaseOrders` so the SC team can place batch/bulk purchase orders (e.g. sauce) for locations/vendors, with delivery aligned to product launch timing.
   - Reuse existing location, vendor, DC, and schedule context when building and submitting purchase orders.

### UI/UX Considerations

- Efficient handling of 250+ locations
- Clear visualization of schedule conflicts or overlaps
- Responsive design for head office desktop use
- Fast filtering and search capabilities
- Export capabilities (future phase)

## Project Structure

```
Project SC/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py          # Environment config (reuse Project-CT pattern)
│   │   │   ├── crunchtime_api.py  # CT API client (reuse/extend Project-CT)
│   │   │   └── holidays_api.py    # Public holidays API client
│   │   ├── schedules/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py          # Schedule endpoints
│   │   │   └── schemas.py         # Pydantic models
│   │   ├── vendors/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py          # Vendor/DC endpoints
│   │   │   └── schemas.py
│   │   ├── locations/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py          # Location endpoints
│   │   │   └── schemas.py
│   │   ├── holidays/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py          # Public holidays endpoints
│   │   │   └── schemas.py
│   │   ├── products/              # Phase 1: product catalog & vendor pricing
│   │   │   ├── __init__.py
│   │   │   ├── routes.py          # getAllCompanyProductsEnhancedV1, getAllVendorProductPricing
│   │   │   └── schemas.py
│   │   ├── purchase_orders/       # Phase 1: place purchase orders
│   │   │   ├── __init__.py
│   │   │   ├── routes.py          # savePurchaseOrders
│   │   │   └── schemas.py
│   │   └── main.py                # FastAPI app
│   ├── .env                        # Environment variables
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js          # Axios client (reuse Project-CT pattern)
│   │   ├── components/
│   │   │   ├── ScheduleCalendar/
│   │   │   ├── FilterPanel/
│   │   │   ├── LocationSelector/
│   │   │   └── VendorSelector/
│   │   ├── pages/
│   │   │   └── Dashboard.jsx      # Main schedule view
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── Project_Brief.md               # This document
```

## Technology Stack

### Backend
- Python 3.11+
- FastAPI
- httpx (async HTTP client)
- pydantic (data validation)
- python-dotenv (environment management)
- truststore (Windows SSL support)
- apscheduler (scheduled PO submission job inside FastAPI)

### Frontend
- React 18+
- Vite
- Axios
- React Router (if multi-page needed)
- Calendar library (TBD: react-big-calendar, fullcalendar, or custom)
- UI component library (TBD: Material-UI, Ant Design, or custom)

## Environment Variables

### Backend (.env)
```
# Crunchtime Configuration (from Project-CT)
CT_ENV=test
CRUNCHTIME_LOCATION_TOKEN_TEST=<token>
CRUNCHTIME_HIERARCHY_TOKEN_TEST=<token>
CRUNCHTIME_VENDOR_TOKEN_TEST=<token>
CRUNCHTIME_VENDOR_LOCATION_TOKEN_TEST=<token>
CRUNCHTIME_COMPANY_PRODUCT_ENHANCED_TOKEN_TEST=<token>
CRUNCHTIME_CATEGORY_TOKEN_TEST=<token>
sitename=<site>
userid=<user>
password=<password>

# Public Holidays API
API_NINJAS_KEY=<key>

# PostgreSQL (Auto Allocation transaction store, database GYG-CT-Helper)
pgName=<postgres_username>
pgPassword=<postgres_password>
# Optional if not using defaults:
# pgHost=localhost
# pgPort=5432
# pgDatabase=GYG-CT-Helper
```

### Frontend (.env)
```
VITE_API_BASE_URL=http://localhost:8000
```

## Future Phases

### Parked (to resume later)
- **Order/delivery pairing:** Refinement of calendar pairing so that selecting an order event highlights the correct delivery event (e.g. order Friday → delivery following Monday when using Crunchtime 8–14 encoding). To be revisited later.

### Phase 2: Holiday Overlay & Override Management
- Display public holidays on calendar
- Show schedule overrides from `scheduleOverrideRowList`
- Visual indicators for modified schedules during holidays
- Edit/create override schedules

### Phase 3: Vendor Schedule Import
- Parse vendor-provided schedules in various formats
- Import and reconcile with Crunchtime data
- Conflict detection and resolution
- Bulk update capabilities

### Phase 4: Advanced Features
- Schedule conflict detection
- Automated schedule optimization suggestions
- Reporting and analytics
- Export to various formats
- Notification system for schedule changes

## Development Approach

1. **Setup**: Initialize project structure, configure environment
2. **Backend API Layer**: Implement Crunchtime API integrations
3. **Data Models**: Define schemas for locations, vendors, schedules
4. **Filtering Logic**: Implement backend filtering endpoints
5. **Frontend Components**: Build filter panel and calendar view
6. **Integration**: Connect frontend to backend APIs
7. **Testing**: Test with real Crunchtime data
8. **Refinement**: Iterate based on user feedback

## Key Considerations

- **Performance**: 250+ locations require efficient data loading and caching
- **Scalability**: Design for potential growth in locations/vendors
- **Data Consistency**: Ensure Crunchtime remains source of truth
- **User Experience**: Fast, intuitive filtering for head office users
- **Error Handling**: Graceful handling of API failures
- **Security**: Secure API key storage, proper authentication

## Dependencies on Project-CT

- Reuse Crunchtime API connection patterns
- Reuse configuration management approach
- Reuse SSL/truststore setup for corporate networks
- Reference existing API endpoint patterns
- Maintain consistency in code structure and style
- **Phase 1 (PO):** Some Crunchtime product/PO endpoints (e.g. `getAllCompanyProductsEnhancedV1`, `getAllVendorProductPricing`, `savePurchaseOrders`) may have existing references or usage in Project-CT; this project will implement or extend the required calls.

## Next Steps

1. Confirm exact Crunchtime API endpoint paths for hierarchy, vendor, and vendor-location
2. Obtain API credentials and keys
3. Set up development environment
4. Initialize project structure
5. Begin Phase 1 implementation (schedules)
6. **Phase 1 (PO):** Confirm Crunchtime paths and payloads for `getAllCompanyProductsEnhancedV1`, `getAllVendorProductPricing`, and `savePurchaseOrders` (reference Project-CT where applicable); then implement product catalog and purchase order endpoints in this project
