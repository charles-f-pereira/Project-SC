import os
from dotenv import load_dotenv

# Use Windows (OS) trust store for TLS – fixes SSL issues on corp networks
import truststore

truststore.inject_into_ssl()

# Load environment: production loads .env.production first, then .env; else .env only
if os.getenv("APP_ENV") == "production":
    load_dotenv(".env.production")
load_dotenv()

# Environment selection (test|prod). Do not set CT_ENV to the URL – use "test" or "prod".
# Base URLs: test = webservices-test.net-chef.com, prod = webservices.net-chef.com
CT_ENV = os.getenv("CT_ENV", "test").lower().strip()
if CT_ENV not in ("test", "prod"):
    CT_ENV = (
        "prod" if "prod" in CT_ENV or (os.getenv("APP_ENV") == "production") else "test"
    )
_CT_SUFFIX = "PROD" if CT_ENV == "prod" else "TEST"

BASE_URL = (
    "https://webservices-test.net-chef.com"  # Crunchtime TEST
    if CT_ENV == "test"
    else "https://webservices.net-chef.com"  # Crunchtime PROD
)

# Required credentials (per-env: sitename_TEST/userid_TEST/password_TEST or _PROD)
SITE_NAME = os.getenv(f"sitename_{_CT_SUFFIX}") or os.getenv("sitename")
USER_ID = os.getenv(f"userid_{_CT_SUFFIX}") or os.getenv("userid")
PASSWORD = os.getenv(f"password_{_CT_SUFFIX}") or os.getenv("password")

# Crunchtime tokens (per-env: CRUNCHTIME_*_TEST or CRUNCHTIME_*_PROD)
AUTH_TOKEN = os.getenv(f"CRUNCHTIME_LOCATION_TOKEN_{_CT_SUFFIX}")
HIERARCHY_TOKEN = os.getenv(f"CRUNCHTIME_HIERARCHY_TOKEN_{_CT_SUFFIX}")
VENDOR_TOKEN = os.getenv(f"CRUNCHTIME_VENDOR_TOKEN_{_CT_SUFFIX}")
VENDOR_LOCATION_TOKEN = os.getenv(f"CRUNCHTIME_VENDOR_LOCATION_TOKEN_{_CT_SUFFIX}")
COMPANY_PRODUCT_ENHANCED_TOKEN = os.getenv(
    f"CRUNCHTIME_COMPANY_PRODUCT_ENHANCED_TOKEN_{_CT_SUFFIX}"
)
VENDOR_PRODUCT_PRICING_TOKEN = os.getenv(
    f"CRUNCHTIME_VENDOR_PRODUCT_PRICING_TOKEN_{_CT_SUFFIX}"
)
PURCHASE_ORDERS_TOKEN = os.getenv(f"CRUNCHTIME_PURCHASE_ORDERS_TOKEN_{_CT_SUFFIX}")
# Confirm Receipt Standard API (getAllConfirmReceiptsStandard); separate from purchase order save token.
CONFIRM_RECEIPT_STANDARD_TOKEN = os.getenv(
    f"CRUNCHTIME_CONFIRM_RECEIPT_STANDARD_TOKEN_{_CT_SUFFIX}"
)
LOCATION_PRODUCT_PRICING_TOKEN = os.getenv(
    f"CRUNCHTIME_LOCATION_PRODUCT_PRICING_TOKEN_{_CT_SUFFIX}"
)
CRUNCHTIME_CATEGORY_TOKEN = os.getenv(f"CRUNCHTIME_CATEGORY_TOKEN_{_CT_SUFFIX}")

# Public Holidays API
API_NINJAS_KEY = os.getenv("API_NINJAS_KEY")

# PostgreSQL (Auto Allocation transaction store, database GYG-CT-Helper)
# Accept pgName or PG_NAME etc. so either .env style works
PG_NAME = os.getenv("pgName") or os.getenv("PG_NAME")
PG_PASSWORD = os.getenv("pgPassword") or os.getenv("PG_PASSWORD")
PG_HOST = os.getenv("pgHost") or os.getenv("PG_HOST") or "localhost"
PG_PORT = int(os.getenv("pgPort") or os.getenv("PG_PORT") or "5432")
PG_DATABASE = os.getenv("pgDatabase") or os.getenv("PG_DATABASE") or "GYG-CT-Helper"

_missing = [
    k
    for k, v in {
        "AUTH_TOKEN (CRUNCHTIME_LOCATION_TOKEN_*)": AUTH_TOKEN,
        "SITE_NAME (sitename_*)": SITE_NAME,
        "USER_ID (userid_*)": USER_ID,
        "PASSWORD (password_*)": PASSWORD,
    }.items()
    if not v
]
if _missing:
    raise RuntimeError(
        f"Missing required .env values for {CT_ENV}: {', '.join(_missing)}"
    )
