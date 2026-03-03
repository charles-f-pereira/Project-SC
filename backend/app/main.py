import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apscheduler.schedulers.background import BackgroundScheduler

from app.core import CT_ENV, BASE_URL
from app.locations.routes import router as locations_router
from app.vendors.routes import router as vendors_router
from app.schedules.routes import router as schedules_router
from app.holidays.routes import router as holidays_router
from app.purchase_orders.routes import router as purchase_orders_router
from app.products.routes import router as products_router
from app.scheduler import run_scheduled_po_job

# Scheduler log: daily rotation, keep 30 days
SCHEDULER_LOG_BACKUP_DAYS = 30
SCHEDULER_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def _setup_scheduler_logging():
    """Configure dedicated file logging for the scheduler (rotation + 30-day retention)."""
    SCHEDULER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = SCHEDULER_LOG_DIR / "scheduler.log"
    handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=SCHEDULER_LOG_BACKUP_DAYS,
        encoding="utf-8",
    )
    handler.suffix = "%Y-%m-%d"
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    scheduler_logger = logging.getLogger("app.scheduler")
    scheduler_logger.addHandler(handler)
    scheduler_logger.setLevel(logging.INFO)


app = FastAPI(
    title="Project SC API", description="Ordering & Delivery Schedule Administration"
)

_scheduler = BackgroundScheduler()
_scheduler.add_job(run_scheduled_po_job, "interval", minutes=1, id="scheduled_po")

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
    print(
        "[startup] Routers: locations, vendors, schedules, holidays, purchase_orders, products"
    )
    _setup_scheduler_logging()
    _scheduler.start()
    print("[startup] APScheduler started (scheduled PO job every 1 min)")


@app.on_event("shutdown")
def _shutdown_scheduler():
    _scheduler.shutdown(wait=False)
    print("[shutdown] APScheduler stopped")


# Root: point to docs and health
@app.get("/")
def root():
    return {
        "service": "Project SC API",
        "env": CT_ENV,
        "docs": "/docs",
        "health": "/api/health",
    }


# Health check
@app.get("/api/health")
def health():
    return {"ok": True, "env": CT_ENV, "service": "Project SC API"}


# Mount routers
app.include_router(locations_router, prefix="/api/locations", tags=["locations"])
app.include_router(vendors_router, prefix="/api/vendors", tags=["vendors"])
app.include_router(schedules_router, prefix="/api/schedules", tags=["schedules"])
app.include_router(holidays_router, prefix="/api/holidays", tags=["holidays"])
app.include_router(
    purchase_orders_router, prefix="/api/purchase-orders", tags=["purchase_orders"]
)
app.include_router(products_router, prefix="/api/products", tags=["products"])
