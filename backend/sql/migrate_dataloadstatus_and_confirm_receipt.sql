-- Migration: CTH."DataLoadStatus" (generic ETL / job watermarks) + confirm-receipt polling support.
-- Run against GYG-CT-Helper_TEST / PROD (schema CTH).

-- Generic job status / last-run tracking for ETL and Crunchtime sync jobs.
CREATE TABLE IF NOT EXISTS "CTH"."DataLoadStatus" (
    job_key          TEXT PRIMARY KEY,
    last_run_at      TIMESTAMPTZ NOT NULL,
    last_success_at  TIMESTAMPTZ NULL,
    metadata         JSONB NULL,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE "CTH"."DataLoadStatus" IS 'Per-job ETL/sync watermarks: last run, last success, optional JSON metadata.';
COMMENT ON COLUMN "CTH"."DataLoadStatus".job_key IS 'Stable job identifier, e.g. crunchtime_po_confirm_receipt.';
COMMENT ON COLUMN "CTH"."DataLoadStatus".last_run_at IS 'UTC timestamp when the job last finished (success or failure).';
COMMENT ON COLUMN "CTH"."DataLoadStatus".last_success_at IS 'UTC timestamp when the job last completed without fatal error.';
COMMENT ON COLUMN "CTH"."DataLoadStatus".metadata IS 'Optional JSON: counts, cursors, batch ids for future ETL.';
COMMENT ON COLUMN "CTH"."DataLoadStatus".updated_at IS 'Row last update time (UTC).';

-- confirmReceivedStatus: VARCHAR legacy -> BOOLEAN (TRUE only for legacy 'Received').
ALTER TABLE "CTH"."autoAllocationTransHdr"
    ALTER COLUMN "confirmReceivedStatus" DROP DEFAULT;

ALTER TABLE "CTH"."autoAllocationTransHdr"
    ALTER COLUMN "confirmReceivedStatus" TYPE boolean
    USING (
        CASE
            WHEN "confirmReceivedStatus" IS NULL THEN NULL
            WHEN lower(trim("confirmReceivedStatus"::text)) = 'received' THEN TRUE
            ELSE NULL
        END
    );

COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."confirmReceivedStatus" IS 'TRUE when vendor confirm receipt received from Crunchtime; NULL if not yet confirmed.';

-- Partial index (after boolean migration; predicate uses boolean semantics).
CREATE INDEX IF NOT EXISTS idx_autoAllocationTransHdr_confirm_poll
    ON "CTH"."autoAllocationTransHdr" ("submittedDateTime", "autoAllocateTransID")
    WHERE status = 'SUBMITTED'
      AND ("confirmReceivedStatus" IS NULL OR "confirmReceivedStatus" IS NOT TRUE)
      AND "transactionNo" IS NOT NULL
      AND trim("transactionNo") <> '';
