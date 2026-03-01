import os
from dotenv import load_dotenv

# Use Windows (OS) trust store for TLS – fixes SSL issues on corp networks
import truststore

truststore.inject_into_ssl()

# Load environment from a local .env if present
load_dotenv()

# Environment selection (test|prod)
CT_ENV = os.getenv("CT_ENV", "test").lower()
BASE_URL = (
    "https://webservices-test.net-chef.com"
    if CT_ENV == "test"
    else "https://webservices.net-chef.com"
)

# Required credentials (kept identical to existing env names)
AUTH_TOKEN = os.getenv("CRUNCHTIME_LOCATION_TOKEN_TEST")
SITE_NAME = os.getenv("sitename")
USER_ID = os.getenv("userid")
PASSWORD = os.getenv("password")

# Additional Crunchtime tokens
HIERARCHY_TOKEN = os.getenv("CRUNCHTIME_HIERARCHY_TOKEN_TEST")
VENDOR_TOKEN = os.getenv("CRUNCHTIME_VENDOR_TOKEN_TEST")
VENDOR_LOCATION_TOKEN = os.getenv("CRUNCHTIME_VENDOR_LOCATION_TOKEN_TEST")
COMPANY_PRODUCT_ENHANCED_TOKEN = os.getenv(
    "CRUNCHTIME_COMPANY_PRODUCT_ENHANCED_TOKEN_TEST"
)
VENDOR_PRODUCT_PRICING_TOKEN = os.getenv("CRUNCHTIME_VENDOR_PRODUCT_PRICING_TOKEN_TEST")
PURCHASE_ORDERS_TOKEN = os.getenv("CRUNCHTIME_PURCHASE_ORDERS_TOKEN_TEST")
LOCATION_PRODUCT_PRICING_TOKEN = os.getenv(
    "CRUNCHTIME_LOCATION_PRODUCT_PRICING_TOKEN_TEST"
)
CRUNCHTIME_CATEGORY_TOKEN_TEST = os.getenv("CRUNCHTIME_CATEGORY_TOKEN_TEST")

# Public Holidays API
API_NINJAS_KEY = os.getenv("API_NINJAS_KEY")

# PostgreSQL (Auto Allocation transaction store, database GYG-CT-Helper)
PG_NAME = os.getenv("pgName")
PG_PASSWORD = os.getenv("pgPassword")
PG_HOST = os.getenv("pgHost", "localhost")
PG_PORT = int(os.getenv("pgPort", "5432"))
PG_DATABASE = os.getenv("pgDatabase", "GYG-CT-Helper")

_missing = [
    k
    for k, v in {
        "CRUNCHTIME_LOCATION_TOKEN_TEST": AUTH_TOKEN,
        "sitename": SITE_NAME,
        "userid": USER_ID,
        "password": PASSWORD,
    }.items()
    if not v
]
if _missing:
    raise RuntimeError(f"Missing required .env values: {', '.join(_missing)}")
