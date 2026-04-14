"""Poll Crunchtime confirm-receipt for recent SUBMITTED auto-allocation POs."""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import (
    BASE_URL,
    PG_DATABASE,
    PG_HOST,
    PG_NAME,
    PG_PASSWORD,
    PG_PORT,
)
from app.purchase_orders.confirm_receipt_ct import (
    ConfirmReceiptLookupResult,
    fetch_confirm_receipt_for_po_sync,
)

logger = logging.getLogger("app.scheduler")

JOB_KEY_PO_CONFIRM_RECEIPT = "crunchtime_po_confirm_receipt"


def _get_connection():
    if not (PG_NAME and PG_PASSWORD):
        return None
    try:
        import psycopg2

        return psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DATABASE,
            user=PG_NAME,
            password=PG_PASSWORD,
        )
    except Exception:
        return None


def _max_workers() -> int:
    raw = (os.getenv("PO_CONFIRM_RECEIPT_MAX_WORKERS") or "8").strip()
    try:
        n = int(raw)
    except ValueError:
        return 8
    return max(1, min(n, 32))


def _lookback_days() -> int:
    """How far back submittedDateTime may be for confirm-receipt polling (plan default: 7)."""
    raw = (os.getenv("PO_CONFIRM_RECEIPT_LOOKBACK_DAYS") or "7").strip()
    try:
        n = int(raw)
    except ValueError:
        return 7
    return max(1, min(n, 90))


def _fetch_one(
    row: tuple[int, str],
) -> tuple[int, str, ConfirmReceiptLookupResult]:
    """Thread worker: one httpx client per task (client is not shared across threads)."""
    hid, po = row
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        result = fetch_confirm_receipt_for_po_sync(client, po)
    return (hid, po, result)


def run_po_confirm_receipt_sync() -> dict:
    """
    SELECT SUBMITTED rows (last 7 days, no confirm yet); parallel GET to CT;
    batch UPDATE headers; upsert DataLoadStatus.

    Returns summary dict for API responses / logging.
    """
    now_utc = datetime.now(timezone.utc)
    lookback_days = _lookback_days()
    submitted_since = now_utc - timedelta(days=lookback_days)
    summary = {
        "candidates": 0,
        "updated": 0,
        "not_found": 0,
        "http_errors": 0,
        "skipped": False,
        "reason": "",
        "lookback_days": lookback_days,
        "submitted_since_utc": submitted_since.isoformat(),
        "crunchtime_base": BASE_URL,
    }
    conn = _get_connection()
    if not conn:
        summary["skipped"] = True
        summary["reason"] = "no_db"
        logger.warning("po_confirm_receipt_sync: no DB connection")
        return summary

    logger.info(
        "po_confirm_receipt_sync: start crunchtime_base=%s lookback_days=%s submitted_since_utc=%s",
        BASE_URL,
        lookback_days,
        submitted_since.isoformat(),
    )
    candidates: list[tuple[int, str]] = []
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT "autoAllocateTransID", trim("transactionNo")
            FROM "CTH"."autoAllocationTransHdr"
            WHERE status = 'SUBMITTED'
              AND "transactionNo" IS NOT NULL
              AND trim("transactionNo") <> ''
              AND "submittedDateTime" IS NOT NULL
              AND "submittedDateTime" >= %s
              AND ("confirmReceivedStatus" IS NULL OR "confirmReceivedStatus" IS NOT TRUE)
            ORDER BY "submittedDateTime" NULLS LAST
            """,
            (submitted_since,),
        )
        candidates = [(int(r[0]), str(r[1])) for r in cur.fetchall()]
        cur.close()
    except Exception as e:
        logger.exception("po_confirm_receipt_sync: SELECT failed: %s", e)
        summary["skipped"] = True
        summary["reason"] = "select_failed"
        conn.close()
        return summary

    summary["candidates"] = len(candidates)
    if not candidates:
        try:
            _upsert_dataload_status(
                conn,
                now_utc,
                success=True,
                metadata={
                    "candidates": 0,
                    "updated": 0,
                    "not_found": 0,
                    "http_errors": 0,
                },
            )
            conn.commit()
        except Exception as e:
            logger.exception("po_confirm_receipt_sync: DataLoadStatus empty run: %s", e)
            conn.rollback()
        finally:
            conn.close()
        return summary

    updates: list[tuple[int, datetime]] = []
    not_found = 0
    http_errors = 0
    workers = _max_workers()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_fetch_one, row): row for row in candidates}
        for fut in as_completed(futures):
            try:
                hid, po, result = fut.result()
            except Exception as e:
                logger.exception("po_confirm_receipt_sync: worker failed: %s", e)
                http_errors += 1
                continue
            if result.confirmed and result.confirm_receipt_utc is not None:
                updates.append((hid, result.confirm_receipt_utc))
            elif result.http_status in (404, 200) and not result.confirmed:
                not_found += 1
            else:
                http_errors += 1

    summary["updated"] = len(updates)
    summary["not_found"] = not_found
    summary["http_errors"] = http_errors

    metadata = {
        "candidates": summary["candidates"],
        "updated": summary["updated"],
        "not_found": summary["not_found"],
        "http_errors": summary["http_errors"],
    }

    try:
        cur = conn.cursor()
        for hid, dt in updates:
            cur.execute(
                """
                UPDATE "CTH"."autoAllocationTransHdr"
                SET "confirmReceivedStatus" = TRUE,
                    "confirmRecievedDateTime" = %s
                WHERE "autoAllocateTransID" = %s
                  AND ("confirmReceivedStatus" IS NULL OR "confirmReceivedStatus" IS NOT TRUE)
                """,
                (dt, hid),
            )
        cur.close()
        _upsert_dataload_status(conn, now_utc, success=True, metadata=metadata)
        conn.commit()
    except Exception as e:
        logger.exception("po_confirm_receipt_sync: UPDATE/DataLoadStatus failed: %s", e)
        conn.rollback()
        summary["skipped"] = True
        summary["reason"] = "commit_failed"
    finally:
        conn.close()

    logger.info(
        "po_confirm_receipt_sync: candidates=%s updated=%s not_found_or_empty=%s http_errors=%s workers=%s",
        summary["candidates"],
        summary["updated"],
        summary["not_found"],
        summary["http_errors"],
        workers,
    )
    return summary


def _upsert_dataload_status(
    conn,
    run_at: datetime,
    *,
    success: bool,
    metadata: dict,
) -> None:
    cur = conn.cursor()
    meta_json = json.dumps(metadata)
    last_success = run_at if success else None
    cur.execute(
        """
        INSERT INTO "CTH"."DataLoadStatus" AS dls (
            job_key, last_run_at, last_success_at, metadata, updated_at
        )
        VALUES (%s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (job_key) DO UPDATE SET
            last_run_at = EXCLUDED.last_run_at,
            last_success_at = COALESCE(EXCLUDED.last_success_at, dls.last_success_at),
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        """,
        (JOB_KEY_PO_CONFIRM_RECEIPT, run_at, last_success, meta_json),
    )
    cur.close()
