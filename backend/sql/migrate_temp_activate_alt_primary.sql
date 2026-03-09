-- Migration: Temporarily activate Alternate Primary for product (saveLocationProductPricing alternatePrimaryFlag before/after savePurchaseOrders)
-- Run against database GYG-CT-Helper_TEST (test) or GYG-CT-Helper_PROD (prod), schema CTH.

ALTER TABLE "CTH"."autoAllocationTransDtl"
  ADD COLUMN IF NOT EXISTS "TempActivateAltPrimary" VARCHAR(1) NULL DEFAULT 'N';

COMMENT ON COLUMN "CTH"."autoAllocationTransDtl"."TempActivateAltPrimary" IS 'Y=product needs saveLocationProductPricing alternatePrimaryFlag activate before PO, then deactivate after; N=no.';
