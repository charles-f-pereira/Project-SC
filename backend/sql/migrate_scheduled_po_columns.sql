-- Migration: Scheduled PO workflow and replay data
-- Run against GYG-CT-Helper, schema CTH.
-- Adds: status, submission_attempts, last_attempt_at, failure_reason, alert_sent_at (header);
--       vendorProductNumber (detail).

-- Header: workflow and alerting columns (existing rows get status SUBMITTED via default)
ALTER TABLE "CTH"."autoAllocationTransHdr"
  ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'SUBMITTED',
  ADD COLUMN IF NOT EXISTS "submission_attempts" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS "last_attempt_at" TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS "failure_reason" TEXT NULL,
  ADD COLUMN IF NOT EXISTS "alert_sent_at" TIMESTAMPTZ NULL;

-- Ensure any row that was already submitted has status SUBMITTED
UPDATE "CTH"."autoAllocationTransHdr"
SET status = 'SUBMITTED'
WHERE "submittedDateTime" IS NOT NULL;

-- Detail: required for Crunchtime replay
ALTER TABLE "CTH"."autoAllocationTransDtl"
  ADD COLUMN IF NOT EXISTS "vendorProductNumber" VARCHAR(100) NULL;

COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."status" IS 'SCHEDULED=waiting for trigger; SUBMITTED=sent to Crunchtime; FAILED=final failure after retries.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."submission_attempts" IS 'Number of Crunchtime submission attempts.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."last_attempt_at" IS 'UTC timestamp of last submission attempt.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."failure_reason" IS 'Last error message when status=FAILED.';
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."alert_sent_at" IS 'When a failure alert was sent (future use).';
COMMENT ON COLUMN "CTH"."autoAllocationTransDtl"."vendorProductNumber" IS 'Vendor product number for Crunchtime savePurchaseOrders replay.';

CREATE INDEX IF NOT EXISTS idx_autoAllocationTransHdr_status_setOrderDateTme
  ON "CTH"."autoAllocationTransHdr"(status, "setOrderDateTme")
  WHERE status = 'SCHEDULED';
