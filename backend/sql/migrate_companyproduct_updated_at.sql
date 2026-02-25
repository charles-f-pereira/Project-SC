-- Migration: Add updated_at to CTH.CompanyProduct for sync audit
-- Run if cth_product_catalogue_tables.sql was run before updated_at was added.

ALTER TABLE "CTH"."CompanyProduct"
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NULL;

COMMENT ON COLUMN "CTH"."CompanyProduct".updated_at IS 'When this row was last upserted by the product catalogue sync (UTC).';
