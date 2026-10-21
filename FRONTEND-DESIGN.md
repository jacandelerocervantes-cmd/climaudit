# FRONTEND DESIGN — Visual language and principles (not screens)

Refers to **design per se**: visual system, tokens, base components and interactions. Screens are defined later, once the backend is 100% done. Reusable source: `OneAquaHealth-clean/web` (`globals.css`, `docs/web_app_design.md`), read-only. Documentation only.

## 1. What is reused from the AquaLedger design

| Element | What it is in AquaLedger | Use in ClimAudit |
|---|---|---|
| **Semantic color tokens** | CSS variables: canvas, surface, sidebar, ink, muted, line, accent and background/ink pairs for warning, error, success, simulated and verified; redefined for dark mode | Same mechanism; **new palette** |
| **Dark mode by system preference** | `prefers-color-scheme` | Same, plus a manual option |
| **Color by provenance** | Color dot according to real data, external modeled or synthetic | Same: `measured`, `modeled`, `synthetic`; it is the core honesty signal |
| **"Sources and method" block inside each response** | Filled from API metadata, never written by the model | Block for evidence, method, versioned factors and uncertainty |
| **Fixed notice at the bottom** | "Screening, not compliance" | "Recommendation, not a ruling" |
| **Visible focus** | `:focus-visible` with accent outline | Same |
| **No numbers in the sidebar** | Avoids suggesting precision | Kept |
| **Model text as plain text** | Never HTML | Same |
| **Origin label and translation status** | Visible in each response | Language status: `machine-drafted` or `agent-audited` |

## 2. What changes

- **Palette (decided 2026-10-17, D-188):** palette A, "ledger teal", tokens in `web/src/app/globals.css`, contrast checked by `web/scripts/check-contrast.mjs`. (Earlier note: AquaLedger's is water blue. ClimAudit uses its own identity (earth, green, warm neutrals) with contrast pairs verified in light and dark. Final colors to be decided; validated with automatic contrast checking.
- **Typography:** AquaLedger's system stack is not enough for CJK, Indic or Arabic. One stack per script is defined (Noto family or another licensed one `[VERIFY]`), loaded by subsets.
- **Direction:** logical CSS properties from the start for Arabic and Urdu; directional icons mirrored.
- **Batch status colors:** one color and one icon per status (DRAFT through RETIRED and BLOCKED), never color alone.
- **Figures:** ASCII digits and decimal point in all languages; uncertainty is shown as a visual and numeric range.
- **Hashes and chain links:** own "anchored evidence" component with abbreviated hash, copy and link to HashScan.

## 3. Design principles

1. **Visible honesty:** provenance, uncertainty and language status always in view; nothing is presented as more precise than it is.
2. **Recommendation, not verdict:** the visual language does not use "approved" or "fraud" badges; it uses "consistent evidence" and "requires review".
3. **Accessibility first:** contrast, keyboard, `lang` per fragment, screen readers, reduced motion.
4. **Calm density:** technical information available in levels (summary, detail, audit) without overwhelming.
5. **Single source of truth:** tokens in a single file; components do not define their own colors.
6. **Text outside the code:** every visible string comes from the language catalog.

## 4. Minimum design system to define (before the screens)

- Tokens: color, typography per script, spacing, radius, shadow, motion, touch sizes.
- Base components: button, field, language selector, provenance label, status badge, finding card, uncertainty range, anchored evidence block, table, fixed notice, batch status timeline.
- Patterns: loading and error with the catalog codes, empty, offline, language without catalog (fallback to English with a notice).
- Content rules: tone, length, use of units and symbols.

## 5. Design audit

With agents (no human review, see `LANGUAGES.md`): `script-rtl-ui-auditor` for scripts, direction, overflows and accessibility; automatic contrast checking in light and dark; review by the `climatechain-judge-simulator` on the clarity of the demo.

## 6. For your review
- Visual identity (name, palette, tone) of ClimAudit.
- Whether the visual language should resemble AquaLedger's or be distinct.
- Font licenses and maximum page size `[VERIFY]`.
