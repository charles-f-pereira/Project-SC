# Project SC - Ordering & Delivery Schedule Administration

A web application for corporate head office staff to administer ordering and delivery schedules for 250+ restaurants across 10+ vendors.

## Project Structure

```
Project SC/
├── backend/          # FastAPI backend
├── frontend/         # React + Vite frontend
└── Project_Brief.md  # Detailed project documentation
```

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your Crunchtime API credentials and tokens
   - Add your API Ninjas key for public holidays

5. Run the backend server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Configure environment variables (optional):
   - Copy `.env.example` to `.env`
   - Adjust `VITE_API_BASE_URL` if your backend runs on a different port

4. Start the development server:
   ```bash
   npm run dev
   ```

The frontend will be available at `http://localhost:5175`

## Environment Variables

### Backend (.env)

Required Crunchtime credentials:
- `CT_ENV` - Environment (test/prod)
- `CRUNCHTIME_LOCATION_TOKEN_TEST` - Location service token
- `CRUNCHTIME_HIERARCHY_TOKEN_TEST` - Hierarchy service token
- `CRUNCHTIME_VENDOR_TOKEN_TEST` - Vendor service token
- `CRUNCHTIME_VENDOR_LOCATION_TOKEN_TEST` - Vendor location service token
- `sitename` - Crunchtime site name
- `userid` - Crunchtime user ID
- `password` - Crunchtime password
- `API_NINJAS_KEY` - API Ninjas key for public holidays

### Frontend (.env)

- `VITE_API_BASE_URL` - Backend API URL (default: http://localhost:8000)

## API Endpoints

### Locations
- `GET /api/locations/` - Get all locations
- Query params: `activeFlag` (optional)

### Vendors
- `GET /api/vendors/` - Get all vendors
- `GET /api/vendors/hierarchy` - Get hierarchy data

### Schedules
- `GET /api/schedules/vendor-locations` - Get vendor-location schedules
- `POST /api/schedules/filtered` - Get filtered schedules

### Holidays
- `GET /api/holidays/` - Get public holidays
- Query params: `country` (default: AU), `year` (optional)

## Features

### Phase 1 (Current)
- ✅ Location and vendor selection with multi-select filters
- ✅ State and distribution center filtering
- ✅ Delivery and ordering day filters
- ✅ Calendar view with schedule visualization
- ✅ Public holiday overlay on calendar
- ✅ Search functionality for locations and vendors

### Future Phases
- Phase 2: Holiday overlay & override management
- Phase 3: Vendor schedule import
- Phase 4: Advanced features (conflict detection, reporting, etc.)

## Development Notes

- The backend uses FastAPI with async/await patterns
- The frontend uses React with functional components and hooks
- Calendar component uses react-big-calendar with moment.js
- API endpoints may need adjustment based on actual Crunchtime API structure
- Some endpoint paths are placeholders and may need confirmation

## Troubleshooting

### Backend Issues
- Ensure all environment variables are set in `.env`
- Check that Crunchtime API credentials are correct
- Verify SSL/truststore setup for corporate networks
- Check API endpoint paths match actual Crunchtime API

### Frontend Issues
- Ensure backend is running on the configured port
- Check browser console for API errors
- Verify CORS settings if accessing from different origin
- Clear browser cache if seeing stale data

## Dependencies

### Backend
- FastAPI
- httpx (async HTTP client)
- pydantic (data validation)
- python-dotenv
- truststore (Windows SSL support)

### Frontend
- React 18
- Vite
- Axios
- react-big-calendar
- moment.js
