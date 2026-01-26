# Project SC - Ordering & Delivery Schedule Administration Framework

## Project Overview

Project SC is a new web application designed to enable corporate head office staff to efficiently administer ordering and delivery schedules for over 250+ restaurants across 10+ vendors. The application will integrate with existing Crunchtime systems and provide a unified interface for managing complex vendor-location-distribution center relationships.

## Objectives

- Centralize ordering and delivery schedule management for 250+ restaurant locations
- Support 10+ vendors with multiple distribution centers (typically state-based, but flexible)
- Integrate with existing Crunchtime API infrastructure from Project-CT
- Provide calendar-based visualization with public holiday overlays
- Enable efficient filtering and viewing of schedules by location, vendor, state, DC, and delivery days
- Future: Support vendor schedule imports in various formats

## Technical Architecture

### Backend (FastAPI)
- **Framework**: FastAPI (Python) - consistent with Project-CT
- **API Integration**: 
  - Crunchtime API endpoints (reuse connection patterns from Project-CT)
  - Public Holidays API (api-ninjas.com)
- **Structure**: 
  - `/backend/app/core/` - Configuration and API clients
  - `/backend/app/schedules/` - Schedule management routes
  - `/backend/app/vendors/` - Vendor and DC management
  - `/backend/app/locations/` - Location management
  - `/backend/app/holidays/` - Public holiday integration

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
sitename=<site>
userid=<user>
password=<password>

# Public Holidays API
API_NINJAS_KEY=<key>
```

### Frontend (.env)
```
VITE_API_BASE_URL=http://localhost:8000
```

## Future Phases

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

## Next Steps

1. Confirm exact Crunchtime API endpoint paths for hierarchy, vendor, and vendor-location
2. Obtain API credentials and keys
3. Set up development environment
4. Initialize project structure
5. Begin Phase 1 implementation
