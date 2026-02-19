from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.core import CT_ENV, BASE_URL
from app.locations.routes import router as locations_router
from app.vendors.routes import router as vendors_router
from app.schedules.routes import router as schedules_router
from app.holidays.routes import router as holidays_router
from app.purchase_orders.routes import router as purchase_orders_router
from app.products.routes import router as products_router

app = FastAPI(
    title="Project SC API",
    description="Ordering & Delivery Schedule Administration"
)

# Allow the Vite dev server to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://192.168.1.247:5173",
        "http://192.168.1.247:5174",
        "http://192.168.1.247:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _startup_banner():
    print(f"[startup] Project SC API starting (env: {CT_ENV}, base: {BASE_URL})")
    print("[startup] Routers: locations, vendors, schedules, holidays, purchase_orders, products")

# Health check
@app.get("/api/health")
def health():
    return {"ok": True, "env": CT_ENV, "service": "Project SC API"}

# Mount routers
app.include_router(locations_router, prefix="/api/locations", tags=["locations"])
app.include_router(vendors_router, prefix="/api/vendors", tags=["vendors"])
app.include_router(schedules_router, prefix="/api/schedules", tags=["schedules"])
app.include_router(holidays_router, prefix="/api/holidays", tags=["holidays"])
app.include_router(purchase_orders_router, prefix="/api/purchase-orders", tags=["purchase_orders"])
app.include_router(products_router, prefix="/api/products", tags=["products"])
