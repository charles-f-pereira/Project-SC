-- Optional: document CANCELLED status on existing DBs (no schema change).
COMMENT ON COLUMN "CTH"."autoAllocationTransHdr"."status" IS 'SCHEDULED=waiting for scheduler trigger; CANCELLED=user-cancelled scheduled order (scheduler ignores); PENDING_CT=immediate submit persisted, awaiting CrunchTime; SUBMITTED=sent to Crunchtime; FAILED=failure or partial CT failure.';
