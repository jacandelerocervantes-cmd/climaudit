---
name: carbon-credit-evidence-verification
description: >
  Verifies the evidence package of a batch of agri carbon credits:
  units, ranges, dates, CO2e tonnes calculation with cited factors,
  measured / modeled / synthetic labels, and consistency. Use when asked
  "verify this batch", "review the evidence", "calculate the batch CO2e" or
  "audit the biochar project". It does not approve credits.
---

# Carbon credit evidence verification

Read `RULES.md`. Adapted from the environmental rules of 00_plataforma-ia and the figure-verification pattern of AquaLedger.

## Process
1. List the package fields: parcel (generalized key), period, activity, quantities, method, source of each datum.
2. Label each datum as **measured / modeled / synthetic**.
3. Validate units, plausible ranges and dates in UTC; flag anything impossible.
4. Recalculate CO2e tonnes with executed code; each factor carries its source, version and date, or stays `[VERIFY]`.
5. Report the result as a range or with assumptions, not as an exact figure without uncertainty.
6. Check that every number in the report matches the evidence (see `grounded-report-check`).
7. Apply `double-counting-guard` before recommending.

## Fails if…
- An emission factor is used from memory.
- Synthetic data is mixed with measured data without a label.
- The report approves instead of recommending.

## Expected output
Table of findings, reproducible calculation and recommendation `human review / return / reject`.

## For your review
Applicable factors and methodology `[VERIFY]`, declared assumptions, missing data.
