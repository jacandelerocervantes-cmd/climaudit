---
name: double-counting-guard
description: >
  Designs and tests the anti-double-counting rule: exact dedup key plus H3
  cell-set spatial overlap, period overlap detection, the batch states that
  hold a period, and release on rejection. Use when asked about "double
  counting", "prevent crediting twice", "period overlap", "unique batch key"
  or "overlapping parcels".
---

# Anti-double-counting guard

Read `RULES.md` and `SCHEMA.md` (sections 2, 3 and 6). State names and finding/error codes must match `SCHEMA.md` exactly.

## Process
1. **Layer 1, exact key:** `dedup_key = SHA-256(canonical({parcel_key, activity, methodology_id}))`. `parcel_key` is a generalized identifier; document the resolution and why. Two batches with the same `dedup_key` must not have overlapping `[start, end)` periods (finding `PERIOD_OVERLAP_DETECTED`).
2. **Layer 2, spatial overlap:** the permissioned record stores the parcel footprint as a set of H3 cells at one fixed resolution. Two batches whose cell sets intersect and whose periods overlap are in conflict even with different keys (finding `PARCEL_CELL_OVERLAP`). Only `cell_set_hash`, a coarse region id and the period are public; coordinates and cell lists never go on-chain.
3. **Period:** interval `[start, end)` in UTC; contiguous periods (end equals the next start) do not overlap.
4. **States that hold a period:** SUBMITTED, UNDER_REVIEW, NEEDS_INFO, BLOCKED, VERIFIED, ISSUED, PARTIALLY_RETIRED, RETIRED. DRAFT does not hold a period; REJECTED releases it.
5. **API error:** `BATCH_PERIOD_OVERLAP` with `params.reason` equal to `exact_key` or `cell_overlap`.
6. **Retirement:** a retired credit is neither transferred nor retired again; the event is recorded in the audit log.
7. **Tests:** total overlap, partial overlap, contiguous (no overlap), same period with another parcel, rejection that releases, resubmission with the same idempotency key, overlapping cell sets with different `parcel_key`, adjacent cell sets (no overlap), a shifted parcel that still intersects, a BLOCKED batch that still holds its period.
8. **Honest limit:** the guard detects double counting within this registry; it does not detect the same credit in other external registries `[VERIFY scope]`. Cell resolution sets the spatial tolerance and must be documented.

## Fails if…
- The key depends on free text.
- Only exact-key matching is implemented, so shifted or partly overlapping parcels pass.
- The contiguous, adjacent-cell and release-on-rejection cases are not tested.
- Detecting double counting across different registries is promised without evidence.

## Expected output
Key and state specification, table of test cases and statement of limits.

## For your review
H3 resolution and tolerance, definition of contiguous periods, real scope of the guarantee.
