-- Demo: Update PO numbers to PO970420 through PO970457 and set confirmed received
-- for showcasing the review screen with orders marked as confirmed received.
-- Run against GYG-CT-Helper, schema CTH.
-- Assigns sequential PO numbers (PO970420, PO970421, ... PO970457) to existing
-- SUBMITTED rows and sets confirmReceivedStatus + confirmRecievedDateTime.

WITH ordered AS (
  SELECT "autoAllocateTransID",
         ROW_NUMBER() OVER (ORDER BY "autoAllocateTransID") AS rn
  FROM "CTH"."autoAllocationTransHdr"
  WHERE status = 'SUBMITTED'
  LIMIT 38
)
UPDATE "CTH"."autoAllocationTransHdr" h
SET
  "transactionNo"       = 'PO' || (970419 + o.rn),
  "confirmReceivedStatus" = 'Received',
  "confirmRecievedDateTime" = now()
FROM ordered o
WHERE h."autoAllocateTransID" = o."autoAllocateTransID";
