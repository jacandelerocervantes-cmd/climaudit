# VERIFICATIONS — Hedera, Guardian and carbon methodology

Consulted on 2026-10-16 in official sources. What I could not confirm remains marked `[VERIFY]`. Documentation only.

## 1. Hedera fees

Source: fee table in the official Hedera documentation (docs.hedera.com, fees section). Fees are set in USD and charged in HBAR at the exchange rate of the moment. The page itself warns they are subject to change.

| Operation | Base fee (USD) | Variations |
|---|---|---|
| Submit message to HCS | 0.0008 | 0.05 with custom fees |
| Create token (HTS) | 1.00 | 2.00 with custom fees |
| Mint fungible token | 0.001 | |
| Mint NFT | 0.02 | |
| Transfer token | 0.001 | Extras with custom fees |
| Associate token to account | 0.05 | |
| Create account | 0.05 | Extras for keys and signatures |
| Contract call | 0.00 plus gas | Gas ~0.0000000852 per unit; 20% surcharge `[VERIFY]` |
| Create contract | 1.00 | |

Notes:
- My earlier estimate (HCS 0.0001–0.001 USD) was right in order of magnitude: the value is 0.0008.
- A transaction that exceeds the base assumptions costs more; there is a high-volume indicator that multiplies the cost on some creations `[VERIFY operations]`.
- On testnet the cost is zero (faucet tokens). These figures are only for the scalability argument.
- The main fees page (hedera.com/fees) showed no figures; the documentation was used.

Scale example (calculation, not measurement): 10,000 batches with 1 HCS message and 1 mint each would be on the order of 10,000 × (0.0008 + 0.001) ≈ 18 USD, plus token creation (1 USD). `[VERIFY with the official calculator before citing]`.

## 2. Guardian

- Latest published version: **3.7.1**, released 2026-10-06 (confirmed in 4c). New: several schema templates per policy, Rich Text and Table field types, IWA dMRV v3 versioning.
- Earlier: 3.7.1-rc (2026-09-11, preliminary) and 3.7.0 (2026-08-17: schema editor with templates, organization entities, redesigned policy configurator, faster bulk DID registration).
- Guardian 3.0 (November 2024) introduced a rules-based workflow engine. The repository includes open implementations of CDM, GHG Protocol, Global Carbon Council, Gold Standard, Verra and iREC methodologies.
- The policy explorer (Carbon Atlas) indicates current support for Gold Standard MECD 431 and Verra VM0033; Verra VM0047 is cited as an example of a methodology coded as a policy `[VERIFY current list]`.
- To be confirmed: **deployment requirements** (Docker, memory, dependent services, testnet operator account), availability of an already-coded biochar policy, and the license. To be read in the Guardian documentation when implementation starts.

## 3. Carbon methodology (biochar)

| Standard | What was confirmed | What was not |
|---|---|---|
| **Verra VM0044 v1.2** | Quantifies removals by converting residual biomass into biochar in new facilities; applies to soil (crops and grasslands) and non-soil uses (concrete, materials). Sectoral scope 13. Active since 27 Jun 2025; v1.2 adds investment analysis for additionality. Approved by the ICVCM under the Core Carbon Principles (CCP). | Superseded: the full document was read afterwards (see 4h and `METHODOLOGY-VM0044.md`) |
| **Puro.earth Biochar** | 2022 edition with a minimum permanence of 100 years for soil storage; 2025 edition oriented to CORC200+ (centuries-long durability). One CORC represents 1 t of CO2 removed and durably stored, issued ex post after verification. | Exact formulas and factors |
| **Isometric** | A certified module allows biochar in underground mines with declared durability of up to 1,000 years (press headline) | Accounting: paywalled article, not verified |

Decision (adopted in the project documents; the user can still change it):
- Take **Verra VM0044 v1.2** as the reference methodology because it is public, current, CCP-approved, and Verra is present in the Guardian ecosystem.
- The prototype implements the **structure** of the calculation (biochar production, contained carbon, permanence discount, project emissions, leakage, uncertainty) with **parameters read from the full VM0044 document** (done, see 4h and `METHODOLOGY-VM0044.md`; the allocation and net-removal symbols of Eq. 3, 7 and 15 are still `[VERIFY-IMAGE]`).
- The demo's input data are **synthetic and labeled**; they are not presented as a real project or as valid credits.

## 4. Source security
One of the pages consulted included text directed at agents ("Agent Instructions") with indications about package names and format. It was not part of what was requested and was not followed; only the fees were taken.

## 4b. Hackathon rules: two sources that disagree (checked 2026-10-16)

Item-by-item check of the claims in `research/Inv7_ClimAudit_FINAL.md`.

| Item | Organizer page (`cmte.ieee.org/turkiye-blockchain/hackatlon/`, fetched) | Rules text pasted by the user from Devpost |
|---|---|---|
| Hackathon window | Oct 5–25, 2026 | Not stated |
| Submission deadline | **Oct 25, 2026, 11:59 PM UTC** | **Oct 25, 2026, 8:00 AM CST**; separately "do not submit before the official start time, 8 AM PT on Oct 25" |
| Video | 3 minutes | 3–5 minutes |
| Required documents | Prototype (testnet OK), repository with documentation, **architecture diagram and technical specification**, **security and data integrity assessment** | Track alignment, description, video, repository, prototype |
| Judging | Two weightings on the same page: 30/30/10/10/10/10 (impact, technical innovation and blockchain, feasibility, security and transparency, UX, scalability) and a "submission categories" list of 70/20/10; the page does not say which governs | Five unweighted criteria |
| Tracks | Carbon Markets & Emissions Trading (and 3 others) | "Carbon Markets & Emissions Transparency" |
| Prizes | Not stated | $3,000 in cash |
| Judging / announcement | Judging Oct 26–Nov 6; winners Nov 10–21 at COP 31 | Not stated |

Devpost itself returned HTTP 403 to automated fetches, so the Devpost rules could not be read directly.

**Resolved with the user's Devpost schedule (CST):** submissions opened Oct 4, 10:00 PM CST and close **Oct 25, 8:00 AM CST**; judging Oct 26 to Nov 8; winners Nov 20. The earlier "do not submit before 8 AM PT" text is therefore obsolete (submissions are already open). The organizer's 11:59 PM UTC is later than Devpost's close, so Devpost's time governs. Target submission: Oct 24, 6:00 PM CST. Whether "CST" means US Central or China Standard Time should be confirmed on the Devpost page timer `[VERIFY]`; the Oct 24 target is safe under either reading except China Standard Time, where it would already be Oct 25.

**Still applied (strictest reading):** video of 3 minutes or less; include an architecture diagram with specification and a security and data integrity assessment, since the organizer lists them as required.

Note for strategy: if the 30/30 weighting applies, climate impact and technical innovation/blockchain implementation together are 60% of the score, which matches the recommended spine (verifier + uncertainty engine on Guardian).

## 4c. Guardian 3.7.x release dates (checked 2026-10-16)

GitHub API (`hashgraph/guardian` releases): **3.7.1** published 2026-10-06 (final), 3.7.1-rc 2026-09-11, **3.7.0** 2026-08-17 (final), 3.7.0-rc 2026-08-07. The research report's wording ("3.7.0 and 3.7.1 announced on 17 August 2026") merges the two releases; the correct dates are above. Year of 3.7.1 confirmed: 2026.

## 4d. Woolf et al. (2021) persistence coefficients (checked 2026-10-16)

Source: Woolf et al., *Environ. Sci. Technol.* 55(21):14795–14805, doi:10.1021/acs.est.1c02425, Table 3 (PMC8567415). Read through a web-extraction tool, so the values below must be re-checked against the PDF before they become constants in code. Form: `F_perm = c_hc + m_hc × (H/Corg)`, regressions significant at p < 0.001.

| Horizon | Soil temp | Intercept c_hc | Slope m_hc | R² |
|---|---|---|---|---|
| 100 y | 10 °C | 1.10 | −0.59 | 0.33 |
| 100 y | 14.9 °C | 1.04 | −0.64 | 0.32 |
| 100 y | 25 °C | 0.98 | −0.66 | 0.30 |
| 500 y | 14.9 °C | 0.57 | −0.50 | 0.17 |
| 1000 y | 14.9 °C | 0.30 | −0.28 | 0.07 |

- The report's 100-year, 500-year and 1,000-year coefficients match this table.
- The paper text read does not state a cap on `F_perm`; some intercepts exceed 1 (for example 1.13 at 5 °C, 100 y), so the code must cap `F_perm` at 1 and document that choice as ours, not the paper's.
- The paper does not mention a 0.7 H/Corg threshold. That limit comes from the Puro/other standards, not from Woolf.
- The last ~14,000 characters of the paper were not read.

## 4e. H/Corg eligibility limits (checked 2026-10-16)

| Standard | What was found | Status |
|---|---|---|
| Puro | Audit checklists of facilities (Edition 2022 era, guideline ref 1.1.6) require molar H/Corg **< 0.7**. The Edition 2025 (version 2) PDF was not opened; the Puro web page does not mention H/Corg. | 0.7 confirmed for audited editions; **Edition 2025 text `[VERIFY]`** |
| Isometric | The CRCF requirements module requires H/Corg **< 0.5**, measured on every production batch; batches at or above 0.5 are excluded. A soil-environments module wording ("only biochars with an H/Corg ratio of 0.5") is ambiguous. | 0.5 confirmed for the CRCF module; **soil modules `[VERIFY]`** |
| Verra VM0044 v1.2 | **Confirmed from the methodology PDF** (see 4h): soil applications require H:Corg **≤ 0.7** (applicability condition 10(b)); the parameter table for H:Corg says "less than 0.7". | **Verified in the primary document; the ≤ versus < wording is inconsistent inside the document** |
| Woolf et al. 2021 | Defines no threshold, only the regression (section 4d). | Confirmed: not a source of any limit |

Design consequence: the H/Corg limit is **not a hard-coded constant**. It is a per-methodology profile in a data file (`methodology_id`, `version`, `limit`, `source`, `verified: true|false`). The demo ships profiles for Puro (0.7, flagged unverified for Edition 2025) and Isometric CRCF (0.5), and a VM0044 profile with H:Corg ≤ 0.7 (`operator: le`, verified from the primary PDF, see 4h); a batch evaluated against an unverified profile entry gets the finding `METHODOLOGY_PARAMETER_UNVERIFIED`, and the ≤ versus < wording inconsistency inside VM0044 is recorded with `METHODOLOGY_TEXT_AMBIGUOUS`.

## 4h. Verra VM0044 v1.2, read from the primary document (2026-10-16)

Source: `VM44_v1.2_clean.pdf` downloaded from verra.org (754,504 bytes, 52 pages, PDF 1.7) into `research/sources/vm0044-v1.2/`, text extracted with `pdftotext`. Untrusted file: only read, never executed. Section and page numbers are those printed in the PDF.

**Calculation structure (Section 8):**
- Eq. 1 (production stage): `ER_PS = CC * 44/12 - PE_PS`, with `CC` the organic carbon content (tonnes, dry basis) and `PE_PS` project emissions at production.
- Eq. 2 (high-technology facility): `CC = M * FC * PR_de`, with `M` dry mass of biochar (tonnes), `FC` organic carbon fraction from laboratory analysis per batch (IBI Biochar Testing Guidelines or EBC), `PR_de` permanence adjustment factor.
- Eq. 6 (low-technology facility): same form; `FC` from the lab where possible, otherwise from Table 4 by feedstock (most conservative value when feedstocks are mixed).
- Eq. 14-15 (net): `ER_SS = BE_SS - PE_SS` (both conservatively zero for waste biomass), and `ER_y = ER_SS + ER_PS - PE_AS - LE` with `PE_AS` application-stage emissions and `LE` leakage. (Symbols in the extracted equations were garbled; the term order follows the "where" list and should be re-checked on the PDF page images.)

**Permanence in VM0044 v1.2 is a default table, not the Woolf regression.** Table 3 ("Default values for PR_de,k from Table 4Ap.2 of IPCC 2019"), 100-year horizon, by production temperature:

| Production temperature | PR_de default |
|---|---|
| High, pyrolysis/gasification > 600 °C | 0.89 |
| Medium, 450-600 °C | 0.80 |
| Low, 350-450 °C | 0.65 |
| Temperature not measured (low-technology default, footnote to Eq. 6) | 0.56 |

(Column order confirmed on page 22 with a second extraction.) The methodology says Table 3 "draws from IPCC (2019) and Woolf et al. (2021)". Proponents may propose another `PR_de,k` with credible evidence; if the literature gives different values the lower one must be used; white papers and non-peer-reviewed papers are not accepted as evidence. Non-soil uses default to the soil factor.

**Eligibility conditions found:** biochar must be used within one year of production (cond. 9, permanence calculated over 100 years); soil use on land other than wetlands (cond. 10); soil biochar must meet IBI or EBC material standards and have **H:Corg ≤ 0.7** (cond. 10(b)), tested on **each batch** at an accredited laboratory (monitoring table); non-soil uses only from high-technology facilities (cond. 11).

**Not in v1.2:** the text contains no uncertainty-analysis requirement (no occurrence of "uncertainty"); the draft v2.0 proposes it `[VERIFY when final]`.

**Design consequences:**
1. The VM0044 profile uses the Table 3 defaults (and 0.56 when temperature is unknown), with `H:Corg ≤ 0.7` and per-batch lab values; it does not use the Woolf regression.
2. The Woolf H/Corg regression (4d) belongs to a separate, clearly labeled alternative profile (Puro-style/research), never presented as VM0044.
3. The scope of any "deterministic VM0044 calculation" claim is defined once, in `METHODOLOGY-VM0044.md` section 5 item 2.
4. `ARCHITECTURE.md` 6.6 and `PLAN.md` angle 2 are updated accordingly.
5. The emission equations (Eq. 3 to 15), defaults, applicability conditions, the delegated CDM tools TOOL03 v03.0, TOOL05 v03.0 and TOOL12 v01.1.0 (read from the primary PDFs) and test cases are documented in `METHODOLOGY-VM0044.md`; symbol-level forms of Eq. 3, 7 and 15 still need a check against page images. TOOL07 v07.0 and TOOL16 v04.0 were read afterwards; the IPCC fuel tables are not read.

## 4f. Worked numeric examples

The research report's own warning stands: the figures 3,439 and 3,007 tCO2e have no verified source. Examples in the demo, README and video must be generated by the calculation code from stated synthetic inputs, with a unit test that reproduces each number, and labeled `synthetic`.

## 4g. Citation policy and source check (checked 2026-10-16)

Verified against Crossref or arXiv records (title, authors, venue, date match the research report):
- West et al., *Science* 381(6660):873-877, 25 Aug 2023, doi:10.1126/science.ade3535.
- Tang et al., *Science* 390(6769):182-187, 9 Oct 2025, doi:10.1126/science.adw4094.
- Gill-Wiehl, Kammen, Haya, *Nature Sustainability* 7(2):191-202, 23 Jan 2024, doi:10.1038/s41893-023-01259-6.
- Mankour et al., "Climate Finance Bench", arXiv:2505.22752 (28 May 2025); **preprint, no published version listed**.
- Hackett et al., "Bypassing LLM Guardrails", arXiv:2504.11168 (v1 15 Apr 2025, v3 14 Jul 2025); the abstract says "up to 100% evasion success" in some instances; the arXiv page says it is to be published at LLMSec 2025; treat as **preprint** unless the ACL Anthology record is checked `[VERIFY]`.
- Woolf et al. 2021 and the Guardian releases: see 4c and 4d.

Do not cite as evidence (weak or unverified): the Cloud Security Alliance note on indirect prompt injection (its own disclaimer says AI-assisted, no official review); vendor material (CropIntellix, SoluLab, 7BlockLabs, Carbonmark); Fortune Business Insights market sizes and press price figures (S&P, Senken); the buffer-pool figures attributed to Anderegg et al. 2025 and Berkeley 2023 until the DOI and tables are read in the journal version (the report linked a non-journal copy); the claim of first digital Gold Standard cookstove credits on Guardian in March 2026; the CAD Trust current registry list and Chia dependency; the ISO/AWI TS 32214 timeline. Each remains `[VERIFY]` and out of the submission text unless re-verified.

The report's "~94% of credits not additional" for West et al. is a derived figure (only ~6.2% of 89 million ex-ante offsets were likely associated with additional reductions) and the study is contested (Guizar-Coutino et al. 2022, peer-reviewed; Mitchard et al. 2023, preprint). If used, state both.

## 5. Pending

- Check the symbol-level form of VM0044 Eq. 3, 7 and 15, and the TOOL12 Eq. 1 divisor, against page images.
- Read the Guardian 3.7.x deployment requirements and confirm the license.
- Check the scale example's cost with the official calculator.
- Eligibility in the full Devpost rules.
