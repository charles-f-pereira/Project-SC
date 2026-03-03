-- Migration: Temp activate VO mode for product (saveLocationProductPricing before/after savePurchaseOrders)
-- Run against database GYG-CT-Helper_TEST (test) or GYG-CT-Helper_PROD (prod), schema CTH.
-- Adds: TempActivateVO on autoAllocationTransDtl.

ALTER TABLE "CTH"."autoAllocationTransDtl"
  ADD COLUMN IF NOT EXISTS "TempActivateVO" VARCHAR(1) NULL DEFAULT 'N';

COMMENT ON COLUMN "CTH"."autoAllocationTransDtl"."TempActivateVO" IS 'Y=product needs saveLocationProductPricing activate before PO, then deactivate after; N=no.';
