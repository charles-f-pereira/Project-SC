# Product catalogue sync – design

## Overview

- **Source:** Crunchtime **getCompanyProductsEnhancedByPage** (paginated), with **pageSize=100**. Loop over pages until no more results.
- **Later:** Use **minutesSinceUpdate** (or equivalent) to fetch only records changed since the last run (delta sync). Sync frequency (e.g. every N minutes) will be configured separately.
- **Change handling:** No separate “change detection”. We **upsert** by business key and **replace** junction link sets; see below.

## Change handling – current logic

We do **not** compute a “change set” or compare hashes. We treat each record from the API as the current truth and apply it.

### CompanyProduct

- **Key:** `number` (product number) is the business key (UNIQUE in the table).
- **New record:** No row with this `number` → **INSERT**.
- **Changed record:** A row with this `number` already exists → **UPDATE** that row with the new values from the API (overwrite columns with the latest payload). So “change” = same `number`, updated fields; we always replace with the current API data.
- **Implementation:** Use PostgreSQL **upsert**: `INSERT INTO "CTH"."CompanyProduct" (...) VALUES (...) ON CONFLICT (number) DO UPDATE SET name = EXCLUDED.name, active_flag = EXCLUDED.active_flag, ... updated_at = EXCLUDED.updated_at` (and all other columns). Set `updated_at = now_utc` on both insert and update so we know when the row was last synced.

### Concept, Department, UserDefinedCategories

- **Key:** `code` (primary key).
- **Logic:** Upsert by `code`. If the code exists, update (e.g. `active_flag`); otherwise insert. No need to “detect” change – overwrite with API values.

### Junction tables (CompanyProductConcept, CompanyProductDepartment, CompanyProductUserDefinedCategory)

- **Change = replace links for that product.** For each product we sync:
  1. Resolve or insert the product (upsert CompanyProduct) and get its `id`.
  2. **Delete** all existing rows for that `company_product_id` in each junction table (Concept, Department, UserDefinedCategory).
  3. **Insert** the current set of links from the API (concept codes, department codes, UDC codes). Insert only if the referenced code exists in Concept/Department/UserDefinedCategories (those are upserted first when we process the product).

So we do not “update in place” or detect which links added/removed; we **replace** the product’s links with the current API set each time we see that product.

### Deletes (products removed in Crunchtime)

- **Delta sync (minutesSinceUpdate):** The API typically returns only modified/added records. We do **not** receive an explicit list of deleted product numbers, so we do not remove or mark deleted products in our DB during a delta run.
- **Full sync (no minutesSinceUpdate, all pages):** Optionally, after a full sync we could mark or delete rows in `CTH.CompanyProduct` that were not seen in the response (e.g. set `active_flag = 'N'` or a `deleted_at` column). This is **not** implemented yet; define when implementing full sync.

## Summary

| Case | Action |
|------|--------|
| New product (number not in DB) | INSERT into CompanyProduct; INSERT into Concept/Department/UDC if new codes; INSERT junction rows. |
| Existing product (same number) | UPDATE CompanyProduct row; DELETE existing junction rows for that product; INSERT current junction rows from API. |
| New concept/department/UDC code | INSERT into Concept/Department/UserDefinedCategories. |
| Existing code | UPDATE (e.g. active_flag) on Concept/Department/UserDefinedCategories. |
| Product removed in Crunchtime | Not handled in delta sync; optional “mark missing” or delete in full sync (TBD). |

No separate “change detection” step: we always apply the API payload (upsert by key, replace junction sets).
