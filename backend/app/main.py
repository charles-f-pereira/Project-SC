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
from app.purchase_orders.confirm_receipt_sync import run_po_confirm_receipt_sync
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


PURCHASE_ORDERS_LOG_BACKUP_DAYS = 30


def _setup_purchase_orders_logging():
    """Rotating JSON-line log for immediate PO submit (see purchase_order_logging.po_submit_log)."""
    SCHEDULER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = SCHEDULER_LOG_DIR / "purchase_orders.log"
    handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=PURCHASE_ORDERS_LOG_BACKUP_DAYS,
        encoding="utf-8",
    )
    handler.suffix = "%Y-%m-%d"
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    po_logger = logging.getLogger("app.purchase_orders")
    po_logger.handlers.clear()
    po_logger.addHandler(handler)
    po_logger.setLevel(logging.INFO)
    po_logger.propagate = False


app = FastAPI(
    title="Project SC API", description="Ordering & Delivery Schedule Administration"
)

_scheduler = BackgroundScheduler()
_scheduler.add_job(run_scheduled_po_job, "interval", minutes=1, id="scheduled_po")
_scheduler.add_job(
    run_po_confirm_receipt_sync, "interval", hours=1, id="po_confirm_receipt"
)

# Allow the Vite dev server to call us (localhost and 127.0.0.1 are different origins to the browser)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
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
    _setup_purchase_orders_logging()
    _scheduler.start()
    print(
        "[startup] APScheduler started (scheduled PO job every 1 min; PO confirm-receipt sync every 1 h)"
    )
    print(
        "[startup] API ready at http://localhost:8000 — open the frontend (run start_test_frontend.bat) and refresh if you see 'Cannot reach the API'."
    )


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
