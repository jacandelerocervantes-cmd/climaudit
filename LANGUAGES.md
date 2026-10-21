# LANGUAGES — ClimAudit multi-language coverage

User criterion: cover the **official languages of the G20 countries plus China**. User design decision: **the backend is 100% English; multi-language support is the frontend's responsibility.** Documentation only, no code.

> Official language lists change and have legal nuances. Everything marked `[VERIFY]` is checked against the official source before it is asserted.

## 1. G20 members and their official languages

| Member | Official languages (summary) | Codes |
|---|---|---|
| Argentina | Spanish (de facto) | es |
| Australia | English (de facto) | en |
| Brazil | Portuguese | pt-BR |
| Canada | English, French | en, fr |
| China | Mandarin Chinese (simplified script) | zh-Hans |
| France | French | fr |
| Germany | German | de |
| India | Hindi and English at the federal level; 22 languages in the constitutional list `[VERIFY]` | hi, en, bn, te, mr, ta, ur, gu, kn, ml, or, pa, as and others |
| Indonesia | Indonesian | id |
| Italy | Italian | it |
| Japan | Japanese (de facto) | ja |
| Mexico | Spanish (de facto) and 68 national indigenous languages `[VERIFY]` | es-MX |
| Russia | Russian (plus regional co-official languages) | ru |
| Saudi Arabia | Arabic | ar |
| South Africa | 12 official `[VERIFY]`: English, Afrikaans, Zulu, Xhosa, Sepedi, Setswana, Sesotho, Xitsonga, siSwati, Tshivenda, isiNdebele and sign language | en, af, zu, xh, nso, tn, st, ts, ss, ve, nr |
| South Korea | Korean | ko |
| Turkey | Turkish | tr |
| United Kingdom | English (de facto) | en |
| United States | English (de facto at the federal level) | en |
| European Union | 24 official languages `[VERIFY]` | bg, hr, cs, da, nl, en, et, fi, fr, de, el, hu, ga, it, lv, lt, mt, pl, pt, ro, sk, sl, es, sv |
| African Union | Working languages include Arabic, English, French, Portuguese, Spanish and Swahili `[VERIFY]` | ar, en, fr, pt, es, sw |

Turkish carries weight because this is the IEEE Blockchain Türkiye hackathon. Sign languages are not text and are left as future work.

## 2. Coverage tiers

| Tier | Languages | Status |
|---|---|---|
| **1, core** | en, es (es-MX and es-ES), zh-Hans, hi, ar, fr, pt (pt-BR and pt-PT), ru, de, ja, ko, id, it, tr | Full catalog; priority human review |
| **2, remaining EU** | bg, hr, cs, da, nl, et, fi, el, hu, ga, lv, lt, mt, pl, ro, sk, sl, sv | Model-generated catalog, marked unreviewed |
| **3, India** | bn, te, mr, ta, ur, gu, kn, ml, or, pa, as | Same |
| **4, South Africa** | af, zu, xh, nso, tn, st, ts, ss, ve, nr | Same; quality in low-resource languages `[VERIFY]` |
| **5, optional** | sw, zh-Hant, Mexican indigenous languages, Russian co-official languages | Future |

**User decision: there are no human reviewers; auditing is done with specialized agents.** Each catalog has a status: `source`, `machine-drafted` or `agent-audited`. The `human-reviewed` status would only exist if a native speaker reviewed it in the future. The interface shows "machine-translated, agent-audited" and never "human-reviewed". An agent audit is not equivalent to a native speaker, and this is stated in the submission.

### Audit agents (in `agents/`)
| Agent | What it audits |
|---|---|
| `i18n-catalog-auditor` | Keys, parameters, plurals, numbers, glossary, legal notices |
| `translation-fidelity-auditor` | Fidelity through independent back-translation; added or lost claims |
| `script-rtl-ui-auditor` | Fonts, RTL, overflows and accessibility in the built-in browser |
| `glossary-terminology-auditor` | Carbon-term glossary per language |

Audit process rules:
- The agent that translates does **not** audit its own translation; each auditor runs in a separate context.
- For each language, two auditors of different types must give `pass` before it is marked `agent-audited`.
- Low-resource languages (tiers 3 and 4) with low confidence remain `machine-drafted`.
- Audit results are saved as `.md` files and back the claims in the video.

## 3. Design: English backend, localization in the frontend

```
Backend (English)                          Frontend (multi-language)
─────────────────                          ─────────────────────────
structured data                      ──►   message catalog per language
finding code + parameters                  (stable key + ICU template)
error code + parameters                    date, number, unit format
narrative report in English          ──►   shown in English, with
(verified in English)                       optional, labeled "translate"
```

### 3.1 API contract
- Every response carries **stable codes** (`finding.code`, `error.code`) and **parameters** (`{field, expected, found, unit}`), not sentences.
- The codes are part of the versioned contract; a code never changes meaning.
- The backend generates no user-facing text except the narrative report in English, and that travels separately, with its figure verification.
- Errors, findings and notices are **catalog keys** (see `ARCHITECTURE.md` section 2 and `SCHEMA.md` section 4); the server never sends user-facing sentences.

### 3.2 Frontend
- Internationalization library with ICU-style templates for plurals and genders `[VERIFY library and version]`.
- One catalog file per language; missing keys fall back to English and are logged.
- Dates and times from UTC with the user's time zone; per-language formats.
- **Carbon numbers and figures:** shown with ASCII digits and a decimal point in all languages, so a figure reads the same everywhere; the unit is a symbol, not a translation.
- Language detection and switching, preference stored in the browser with a fallback if unavailable.
- Scripts: fonts covering CJK, Devanagari, Arabic, Bengali, Tamil, etc., by subsets so as not to bloat the page `[VERIFY license]`.
- Right-to-left (Arabic, Urdu): `dir` attribute, logical CSS properties, mirroring of directional icons, numbers isolated with interface markup.
- Visual tests for RTL, CJK and Indic scripts.

### 3.3 AI narrative report
- Generated and verified **in English** (figure verification, no links or markup, no instruction leakage).
- The interface offers an **optional, on-demand** "translate": a constrained call that receives only the already-validated English, with language-neutral checks (identical numbers, no links, per-language length). It is labeled "machine-translated, unreviewed" and the original is shown.
- If that translation is not implemented, the report stays in English and the rest of the interface is localized. This is acceptable and safer.
- Adjustments if implemented: per-language length limits (Chinese and Japanese are shorter in characters) and character n-grams to detect instruction leakage in languages without spaces.

### 3.4 Input in other languages
- Evidence documents may come in any language. The LLM reads them and extracts the fields into an **English schema**; the original text is kept and linked.
- Proper names, codes and units are not translated.

## 4. What is simplified compared to the previous version
- A second model is no longer needed to translate errors and findings: they are catalog keys.
- There is no longer a per-language list of forbidden terms in the backend.
- Figure verification happens only once, in English.
- The risk of a translation changing a number is confined to the optional narrative text.

## 5. Tests
- Every finding code and error code has an entry in the catalog of all tier 1 languages; a test fails if a key is missing.
- The same case shows the same figures in all languages.
- Visual tests of RTL and long scripts.
- If optional translation exists: cases with an altered number, an inserted link and a leaked instruction.

## 6. For your review
- Scope note: tier 3 lists 11 of India's 22 constitutional languages (not sa, ks, ne, sd, doi, mai, kok, mni, brx, sat, ...); the rest are an extension. This is a declared limit against the "official languages" criterion.
- ~~Confirm that the agent audit replaces human review and that it is declared as such in the submission.~~ **Confirmed by the user.** The submission will say "machine-translated, agent-audited".
- Whether tiers 3 and 4 are part of the submission or declared as an extension.
- Whether the optional report translation is implemented or the report stays in English.
- Verify the official G20 language list and model quality in low-resource languages `[VERIFY]`.
