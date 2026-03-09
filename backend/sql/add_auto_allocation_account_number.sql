-- Add accountNumber to Auto Allocation transaction header (from Crunchtime getAllVendorLocation vendorLocationTransmissionDetail.accountNumber).
-- Run against the same database as cth_auto_allocation_tables.sql (e.g. GYG-CT-Helper_TEST / GYG-CT-Helper_PROD).

ALTER TABLE "CTH"."autoAllocationTransHdr"
  ADD COLUMN IF NOT EXISTS "accountNumber" VARCHAR(100) NULL;

COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."accountNumber" IS 'Vendor location account number from Crunchtime getAllVendorLocation vendorLocationTransmissionDetail.accountNumber (stored at submit time).';
