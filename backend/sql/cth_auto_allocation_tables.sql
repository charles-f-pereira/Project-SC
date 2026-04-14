-- Project SC: Auto Allocation transaction tables
-- Schema: CTH
-- Run this script against the PostgreSQL database to create the schema and tables.
-- Intended databases: GYG-CT-Helper_TEST (test) or GYG-CT-Helper_PROD (prod).

CREATE SCHEMA IF NOT EXISTS "CTH";

-- Batch: one row per immediate submit; idempotency_key is UNIQUE so duplicate HTTP requests do not double-call CrunchTime.
-- Scheduler does NOT select PENDING_CT or rows linked here—only status=SCHEDULED.
CREATE TABLE "CTH"."autoAllocationSubmitBatch" (
    "id"                  UUID PRIMARY KEY,
    "idempotency_key"     VARCHAR(128) NOT NULL,
    "status"              VARCHAR(20) NOT NULL,
    "location_count"      INTEGER NOT NULL,
    "createDateTime"      TIMESTAMPTZ NOT NULL,
    "completed_at"        TIMESTAMPTZ NULL,
    "failure_reason"      TEXT NULL,
    CONSTRAINT uq_autoAllocationSubmitBatch_idempotency UNIQUE ("idempotency_key")
);

COMMENT ON TABLE "CTH"."autoAllocationSubmitBatch" IS 'One row per immediate submit attempt; idempotency_key prevents duplicate CrunchTime waves.';
COMMENT ON COLUMN "CTH"."autoAllocationSubmitBatch"."status" IS 'PENDING_CT=rows written, awaiting savePurchaseOrders; SUBMITTED=all locations succeeded; FAILED=activate/CT failure or partial failure.';

-- Header: one row per location (Crunchtime savePurchaseOrders is called per location; each location gets a unique autoAllocateTransID)
-- status: SCHEDULED=awaiting trigger; SUBMITTED=sent to Crunchtime; FAILED=final failure after retries.
-- Columns without NOT NULL allow NULL. Future-use columns (submitUserId, vendorEdiFlag, confirmRecievedDateTime) and distributionCenter allow NULL.
CREATE TABLE "CTH"."autoAllocationTransHdr" (
    "autoAllocateTransID"   BIGSERIAL PRIMARY KEY,
    country                 VARCHAR(100) NULL,
    state                   VARCHAR(100) NULL,
    "locationCode"          VARCHAR(500) NULL,
    "locationName"          VARCHAR(500) NULL,
    market                  VARCHAR(100) NULL,
    "vendorCode"            VARCHAR(100) NULL,
    "vendorName"            VARCHAR(255) NULL,
    "distributionCenter"    VARCHAR(255) NULL,
    "createDateTime"        TIMESTAMPTZ NOT NULL,
    "setOrderDateTme"       TIMESTAMPTZ NOT NULL,
    "setExpectedDeliveryDate" DATE NOT NULL,
    "setExpectedDeliveryDOW"  VARCHAR(3) NULL,
    "submittedDateTime"     TIMESTAMPTZ NULL,
    "transactionNo"         VARCHAR(100) NULL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED',
    "submission_attempts"   INTEGER NOT NULL DEFAULT 0,
    "last_attempt_at"       TIMESTAMPTZ NULL,
    "failure_reason"        TEXT NULL,
    "alert_sent_at"         TIMESTAMPTZ NULL,
    "submitUserId"          VARCHAR(100) NULL,
    "vendorEdiFlag"         VARCHAR(10) NULL,
    "confirmReceivedStatus" BOOLEAN NULL,
    "confirmRecievedDateTime" TIMESTAMPTZ NULL,
    "batch_id"              UUID NULL,
    CONSTRAINT "autoAllocationTransHdr_batch_id_fkey" FOREIGN KEY ("batch_id")
        REFERENCES "CTH"."autoAllocationSubmitBatch"("id") ON DELETE SET NULL
);

COMMENT ON TABLE "CTH"."autoAllocationTransHdr" IS 'Auto Allocation transaction header: one row per location (savePurchaseOrders called per location). Timestamps in UTC.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."createDateTime" IS 'When the record was saved in the app (UTC).';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."setOrderDateTme" IS 'Order date/time selected for the PO; stored in UTC (front end displays AEST/AEDT).';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."setExpectedDeliveryDOW" IS 'Expected delivery day of week derived from setExpectedDeliveryDate (e.g. Mon, Tue, Wed).';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."submittedDateTime" IS 'When the system successfully submitted the PO (UTC).';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."transactionNo" IS 'From Crunchtime orderNumber after savePurchaseOrders.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."submitUserId" IS 'Reserved: userid of the user that submitted the PO.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."vendorEdiFlag" IS 'Reserved: EDI workflow control.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."confirmReceivedStatus" IS 'TRUE when vendor confirm receipt received from Crunchtime; NULL if not yet confirmed.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."confirmRecievedDateTime" IS 'Reserved: status change timestamp (UTC).';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."status" IS 'SCHEDULED=waiting for scheduler trigger; CANCELLED=user-cancelled scheduled order (scheduler ignores); PENDING_CT=immediate submit persisted, awaiting CrunchTime; SUBMITTED=sent to Crunchtime; FAILED=failure or partial CT failure.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."batch_id" IS 'FK to autoAllocationSubmitBatch for immediate submits; NULL for scheduled-only rows.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."submission_attempts" IS 'Number of Crunchtime submission attempts.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."last_attempt_at" IS 'UTC timestamp of last submission attempt.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."failure_reason" IS 'Last error message when status=FAILED.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."alert_sent_at" IS 'When a failure alert was sent (future use).';

-- Detail: line items (products) per header; productNumber, productName, vendorUnit, vendorProductNumber allow NULL (vendor is on header)
CREATE TABLE "CTH"."autoAllocationTransDtl" (
    "autoAllocateItmTransID" BIGSERIAL PRIMARY KEY,
    "autoAllocateTransID"    BIGINT NOT NULL REFERENCES "CTH"."autoAllocationTransHdr"("autoAllocateTransID") ON DELETE CASCADE,
    "productNumber"         VARCHAR(100) NULL,
    "productName"           VARCHAR(255) NULL,
    "vendorProductNumber"   VARCHAR(100) NULL,
    "vendorUnit"            VARCHAR(100) NULL,
    "orderQuantity"         INTEGER NOT NULL,
    "TempActivateVO"        VARCHAR(1) NULL DEFAULT 'N'
);

-- If the table already exists with vendorCode, run this to drop it:
-- ALTER TABLE "CTH"."autoAllocationTransDtl" DROP COLUMN IF EXISTS "vendorCode";

COMMENT ON TABLE "CTH"."autoAllocationTransDtl" IS 'Auto Allocation transaction detail: product lines per header.';
COMMENT ON COLUMN "CTH"."autoAllocationTransDtl"."autoAllocateTransID" IS 'FK to autoAllocationTransHdr.';
COMMENT ON COLUMN "CTH"."autoAllocationTransDtl"."vendorProductNumber" IS 'Vendor product number for Crunchtime savePurchaseOrders replay.';
COMMENT ON COLUMN "CTH"."autoAllocationTransDtl"."TempActivateVO" IS 'Y=product needs saveLocationProductPricing activate before PO, then deactivate after; N=no.';

CREATE INDEX idx_autoAllocationTransDtl_autoAllocateTransID
    ON "CTH"."autoAllocationTransDtl"("autoAllocateTransID");

CREATE INDEX idx_autoAllocationTransHdr_status_setOrderDateTme
    ON "CTH"."autoAllocationTransHdr"(status, "setOrderDateTme")
    WHERE status = 'SCHEDULED';

CREATE INDEX idx_autoAllocationTransHdr_batch_id
    ON "CTH"."autoAllocationTransHdr" ("batch_id");

CREATE INDEX idx_autoAllocationTransHdr_confirm_poll
    ON "CTH"."autoAllocationTransHdr" ("submittedDateTime", "autoAllocateTransID")
    WHERE status = 'SUBMITTED'
      AND ("confirmReceivedStatus" IS NULL OR "confirmReceivedStatus" IS NOT TRUE)
      AND "transactionNo" IS NOT NULL
      AND trim("transactionNo") <> '';

-- Generic ETL / job watermarks (optional; also in migrate_dataloadstatus_and_confirm_receipt.sql).
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
COMMENT ON COLUMN "CTH"."DataLoadStatus".updated_at IS 'Row last update time.';
