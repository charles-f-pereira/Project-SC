"""
Test PostgreSQL connectivity and verify CTH schema / autoAllocationTransHdr / autoAllocationTransDtl structure.
Run from backend directory: python scripts/test_pg_connectivity.py
Or from project root: python backend/scripts/test_pg_connectivity.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend directory (and cwd as fallback)
_backend_dir = Path(__file__).resolve().parent.parent
_env_file = _backend_dir / ".env"

if _env_file.exists():
    load_dotenv(_env_file)

load_dotenv()  # cwd .env as fallback

sys.path.insert(0, str(_backend_dir))

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

PG_HOST = os.getenv("pgHost") or os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("pgPort") or os.getenv("PG_PORT", "5432"))
PG_DATABASE = os.getenv("pgDatabase") or os.getenv("PG_DATABASE", "GYG-CT-Helper")
PG_NAME = os.getenv("pgName") or os.getenv("PG_NAME")
PG_PASSWORD = os.getenv("pgPassword") or os.getenv("PG_PASSWORD")


def main():
    print("PostgreSQL connectivity and structure test")
    print("Env loaded from:", _env_file if _env_file.exists() else "cwd")
    print(
        "Database:",
        PG_DATABASE,
        "Host:",
        PG_HOST,
        "Port:",
        PG_PORT,
        "User:",
        PG_NAME or "(not set)",
    )
    print()

    if not PG_NAME or not PG_PASSWORD:
        print("ERROR: Set pgName and pgPassword in .env (in backend directory)")
        sys.exit(1)

    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DATABASE,
            user=PG_NAME,
            password=PG_PASSWORD,
            connect_timeout=5,
        )
    except Exception as e:
        print("CONNECTIVITY: FAIL")
        print("Error:", e)
        sys.exit(1)

    print("CONNECTIVITY: OK")
    print()

    cur = conn.cursor()

    # Check schema CTH exists
    cur.execute(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
        ("CTH",),
    )
    if not cur.fetchone():
        print("STRUCTURE: FAIL - Schema CTH does not exist")
        conn.close()
        sys.exit(1)
    print("Schema CTH: OK")

    # Check tables
    for table in ("autoAllocationTransHdr", "autoAllocationTransDtl"):
        cur.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'CTH' AND table_name = %s
            """,
            (table,),
        )
        if not cur.fetchone():
            print(f"STRUCTURE: FAIL - Table CTH.{table} does not exist")
            conn.close()
            sys.exit(1)
        print(f"Table CTH.{table}: OK")

        # List columns
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'CTH' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        rows = cur.fetchall()
        for r in rows:
            print(f"  - {r[0]}: {r[1]} (nullable={r[2]})")

    # FK check: detail references header
    cur.execute(
        """
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
        WHERE tc.table_schema = 'CTH' AND tc.table_name = 'autoAllocationTransDtl'
          AND tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'autoAllocationTransHdr'
        """
    )
    if cur.fetchone():
        print("FK autoAllocationTransDtl -> autoAllocationTransHdr: OK")
    else:
        print(
            "FK autoAllocationTransDtl -> autoAllocationTransHdr: not found (optional check)"
        )

    conn.close()
    print()
    print("STRUCTURE: OK - Schema and tables match expected design.")


if __name__ == "__main__":
    main()
