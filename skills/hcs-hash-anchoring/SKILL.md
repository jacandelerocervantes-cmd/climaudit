---
name: hcs-hash-anchoring
description: >
  Anchors evidence on the Hedera Consensus Service: canonical JSON serialization,
  SHA-256 hash of each package, chaining with the previous hash, test vectors
  and an independent verifier. Adapted from hash-chain-evidence-ledger.
  Use when asked to "anchor evidence", "immutable record", "package hash"
  or "audit on HCS". The hash proves integrity, not truthfulness.
---

# Hash anchoring on HCS

Read `RULES.md`. Adapted from `civico-legal/hash-chain-evidence-ledger` (00_plataforma-ia).

## Process
1. **Input:** `seq`, `ts` (UTC ISO 8601), `payload` (JSON), `prev_hash`; `hash` = SHA-256 of the canonical serialization.
2. **Canonical serialization:** JSON with sorted keys, no whitespace, UTF-8; no floats or local dates in the payload.
3. **Genesis:** `prev_hash` of 64 zeros, documented.
4. **HCS message:** publish only the hash and minimal metadata; the full package stays off-chain (own storage or IPFS `[VERIFY]`). Never personal data or fine-grained coordinates on-chain.
5. **Test vectors:** expected canonical JSON and hex, so another implementation reproduces the same bytes.
6. **Independent verifier:** a separate process that walks the HCS topic (for example via mirror node `[VERIFY API]`), recomputes, and returns the first broken `seq`.
7. **Corrections:** never rewrite; add a correction entry.
8. Show in the interface the explorer link (HashScan testnet) of each message.

## Fails if…
- It is claimed that the hash proves the measurement is true.
- Sensitive data is published on the topic.
- Only the writer exists and there is no separate verifier.

## Expected output
Format specification, test vectors and verifier plan.

## For your review
What goes inside the payload, where the full package is stored, mirror node API `[VERIFY]`.
