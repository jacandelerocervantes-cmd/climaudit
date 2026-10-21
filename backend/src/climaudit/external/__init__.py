"""Advisory cross-checks against public data (BACKEND-SPEC.md section 20, DECISIONS-LEDGER.md D-170 to D-178).

Everything here is advisory: a check can add findings for the human verifier, but it never blocks calculation or
verification, never changes a number, and fails soft (an `EXTERNAL_CHECK_UNAVAILABLE` info finding) when its data is
missing or the network is down. The data providers are injected, so tests and offline demos need no network.
"""
