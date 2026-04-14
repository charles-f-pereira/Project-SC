-- Migration: Submit batch idempotency + PENDING_CT status for immediate submit (DB before CrunchTime).
-- Run against GYG-CT-Helper_TEST / PROD (schema CTH). Scheduler only selects status='SCHEDULED'; PENDING_CT is never picked by the scheduler.
-- Keep in sync with cth_auto_allocation_tables.sql (greenfield).

CREATE TABLE IF NOT EXISTS "CTH"."autoAllocationSubmitBatch" (
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

ALTER TABLE "CTH"."autoAllocationTransHdr"
  ADD COLUMN IF NOT EXISTS "batch_id" UUID NULL;

COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."batch_id" IS 'FK to autoAllocationSubmitBatch for immediate submits; NULL for legacy and scheduled-only rows.';

DO $$
BEGIN
  BEGIN
    ALTER TABLE "CTH"."autoAllocationTransHdr"
      ADD CONSTRAINT "autoAllocationTransHdr_batch_id_fkey"
      FOREIGN KEY ("batch_id") REFERENCES "CTH"."autoAllocationSubmitBatch"("id")
      ON DELETE SET NULL;
  EXCEPTION
    WHEN duplicate_object THEN NULL;
  END;
END $$;

CREATE INDEX IF NOT EXISTS idx_autoAllocationTransHdr_batch_id
  ON "CTH"."autoAllocationTransHdr" ("batch_id");

COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."status" IS 'SCHEDULED=scheduler will submit; PENDING_CT=immediate submit persisted, awaiting CrunchTime; SUBMITTED=sent to Crunchtime; FAILED=failure or partial CT failure.';
