-- Migration: Remove vendorCode from autoAllocationTransDtl (vendor is on header only).
-- Run this if the table was created with vendorCode before the schema update.
-- Database: GYG-CT-Helper, Schema: CTH

ALTER TABLE "CTH"."autoAllocationTransDtl" DROP COLUMN IF EXISTS "vendorCode";
