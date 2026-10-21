# METHODOLOGY — Verra VM0044 v1.2 (equations, parameters, implementation notes)

Source: `VM44_v1.2_clean.pdf` from verra.org, 52 pages, downloaded 2026-10-16 to `research/sources/vm0044-v1.2/` and read as text extracted with `pdftotext`. Section numbers and page numbers below are those printed in the PDF.

**Reliability of this document.** The text extraction lost the math symbols, so the equations were first reconstructed from the prose. On 2026-10-17 Eq. 3, 7 and 15 and TOOL12 Eq. 1 were checked symbol by symbol against rendered page images (VM0044 pages 22, 26 and 33; TOOL12 page 6); results in section 9 and `DECISIONS-LEDGER.md` O-6. Other equations are still reconstructed from text. Nothing here is legal or certification advice.

## 1. Overview of the calculation (Section 8)

```
Net removals ER_y = ER_SS,y + ER_PS,y - PE_AS,y - LE_y                (Eq. 15)
  ER_SS,y = BE_SS,y - PE_SS,y   (both 0 for waste biomass)           (Eq. 14)
  ER_PS,y = CC_t,k,y * 44/12 - PE_PS,t,p,y                           (Eq. 1)
    CC_t,k,y = M_t,k,p,y * FC_p,t,p * PR_de,k                        (Eq. 2 high-tech / Eq. 6 low-tech)
    PE_PS,p,y = (P_ED + P_EP + P_EC) * (sum_t sum_k M_t,k,p,y / M_p,y)  (Eq. 3 high-tech / Eq. 7 low-tech; verified on page images)
  PE_AS,y = sum( E_P,t,k,y + E_ap,t,k,y )                            (Eq. 11)
  LE_y = LE_as + LE_bd + LE_ts + LE_tap                              (Eq. 13)
```

Units: tonnes CO2e (tCO2e) for emissions and removals; tonnes (dry basis) for biochar mass. 100-year permanence horizon.

## 2. Equations

| Eq. | Quantity | Form (reconstructed) | Notes |
|---|---|---|---|
| 1 | `ER_PS,y` removals at production stage | `CC * 44/12 − PE_PS` | `44/12` converts organic carbon to CO2 |
| 2 | `CC_t,k,y` organic carbon, high-tech facility | `M_t,k,p,y × FC_p,t,p × PR_de,k` | `FC` from laboratory analysis (IBI Biochar Testing Guidelines or EBC), dry basis |
| 3 | `PE_PS,p,y` production-stage emissions, high-tech | `(P_ED,p,y + P_EP,p,y + P_EC,p,y) × (Σ_t Σ_k M_t,k,p,y / M_p,y)` | Verified on the page image (p. 22). The factor is the share of the facility's dry-mass production that belongs to the project, summed over biochar types and application types. The code computes the per-batch slice `M_batch / M_p,y`; summing the slices of all batches of the facility-year gives exactly Eq. 3 |
| 4 | `PE_D,p,y` pre-treatment emissions | `PE_DE + PE_DF` | Grid electricity via CDM TOOL05; fossil fuel via CDM TOOL03; zero if renewable energy |
| (text) | `PE_P,p,y` conversion emissions, high-tech | `= 0` | Net emissions considered de minimis because pyrolysis gases must be combusted or recovered (footnote 19) |
| 5 | `PE_C,p,y` auxiliary energy for pyrolysis | `PE_CE + PE_CF` | TOOL05 and TOOL03; zero if renewable |
| 6 | `CC_t,k,y`, low-tech facility | `M × FC × PR_de,k` | `FC` from laboratory where possible, else Table 4; default `PR_de` = 0.56 if pyrolysis temperature unknown |
| 7 | `PE_PS,p,y`, low-tech | `(P_ED,p,y + P_EP,p,y + P_EC,p,y) × (Σ_t Σ_k M_t,k,p,y / M_p,y)` | Verified on the page image (p. 26): same form as Eq. 3. The "Where" list of Eq. 7 prints `P_ED` twice, the third entry is the auxiliary-energy term `P_EC` (a typo in the source) |
| 8 | `PE_D,p,y`, low-tech | `PE_DE + PE_DF` | As Eq. 4 |
| 9 | `PE_P,p,y`, low-tech | `Fe × GWP_CH4 × M_t,k,p,y` | `Fe` average CH4 per tonne of biochar (tCH4/tonne); default 0.049 t CH4/tonne for traditional kilns if the kiln type is not listed (Table 3 of Cornelissen et al. 2016); `GWP_CH4` from the latest VCS Standard |
| 10 | `PE_C,p,y`, low-tech | `PE_CE + PE_CF` | As Eq. 5 |
| 11 | `PE_AS,y` application-stage emissions | `Σ (E_P,t,k,y + E_ap,t,k,y)` | Sum over biochar types and application types |
| 12 | `E_P,k,y` processing of biochar (grinding, sieving) | `PE_PE + PE_PF` | Electricity (TOOL05) and fossil fuel (TOOL03); zero if no processing or renewable energy |
| (text) | `E_ap,k,y` utilization | `= 0` | Fossil fuel use and fertilizer mixing considered negligible (footnote 24, from CDM AR-ACM0003) |
| 13 | `LE_y` total leakage | `LE_as + LE_bd + LE_ts + LE_tap` | `LE_as = 0` (no purposely grown biomass), `LE_bd = 0` (waste biomass only); `LE_ts` waste biomass transport; `LE_tap` biochar transport |
| 14 | `ER_SS,y` sourcing stage | `BE_SS − PE_SS` | Both conservatively zero |
| 15 | `ER_y` net removals | `ER_SS,y + ER_PS,y − PE_AS,y − LE_y` | Verified on the page image (p. 33) |

## 3. Parameters with defaults stated in the PDF

| Parameter | Value / rule | Where |
|---|---|---|
| `PR_de,k` (soil), pyrolysis/gasification > 600 °C | 0.89 | Table 3 (IPCC 2019 Table 4Ap.2), p. 22 |
| `PR_de,k`, 450-600 °C | 0.80 | Table 3 |
| `PR_de,k`, 350-450 °C | 0.65 | Table 3 |
| `PR_de,k`, temperature not measured | 0.56 | Footnote 21 to Eq. 6 (IPCC 2019 Fig. 4Ap.1(b)) |
| `PR_de,k` non-soil | Soil default unless scientifically robust evidence; lower value must be used if the literature differs; white papers and non-peer-reviewed papers are not accepted | Section 8.2.2.1 |
| `FC_p` (low-tech, by feedstock and process) | Pyrolysis / gasification: animal manure 0.38 / 0.09; wood 0.77 / 0.52; herbaceous 0.65 / 0.28; rice husks and straw 0.49 / 0.13; nut shells, pits, stones 0.74 / 0.40; biosolids (paper sludge) 0.35 / 0.07. Most conservative value for mixed feedstocks | Table 4 (IPCC 2019 Table 4Ap.1), p. 26 |
| `Fe` (CH4, low-tech) | 0.049 t CH4/tonne if kiln type not listed | Under Eq. 9, p. 27-28 |
| `H:Corg` (soil use) | **≤ 0.7** (applicability condition 10(b)); the parameter table says "less than 0.7"; measured on each batch at an accredited laboratory | p. 13 and p. 39-40 |
| Time to application | Biochar used within one year of production (condition 9) | p. 13 |
| Transport leakage threshold | Count `LE_ts` / `LE_tap` only if distance exceeds 200 km (round trip for waste biomass transport); use CDM TOOL12 for freight, TOOL16 for biomass | Section 8.3, p. 29-30 |
| `BE_SS`, `PE_SS`, `E_ap`, `LE_as`, `LE_bd`, `PE_P` (high-tech) | 0 | Sections 8.2.1, 8.2.2.1, 8.2.3, 8.3 |
| `GWP_CH4` | Value in the latest VCS Standard (not stated in VM0044) | Under Eq. 9 |

## 4. Inputs the methodology delegates to other documents

These are **not defined inside VM0044** and are the main implementation gap. For the prototype each is an explicit input (with provenance label) or a profile parameter marked `verified: false` until read:
- CDM TOOL03, TOOL05, TOOL07, TOOL12 and TOOL16: **now read, see section 8**. Still unread: the IPCC 2006 fuel tables used by TOOL03 and the detailed OM/BM data procedures of TOOL07.
- VCS Methodology Requirements section 2.5.2 (evidence for default factors) and the VCS Standard (GWP values).
- Cornelissen et al. (2016) Table 3 for kiln-specific `Fe`.
- IBI Biochar Testing Guidelines and EBC Production Guidelines (laboratory methods, material limits).
- Definitions of "high technology production facility" (Section 3 of VM0044) and the full applicability list (Section 4); read Section 3 and Section 4 in full before coding the facility classification `[VERIFY]`.

## 5. Implementation notes for the prototype

1. **Profile file.** One data file per methodology profile (`VM0044@1.2`) holding the table defaults above with page references and `verified` flags. No constants in code.
2. **Scope of the claim.** "Deterministic VM0044 v1.2 calculation" covers Eq. 1, 2/6, 3/7 (with allocation), 9, 11, 12, 13, 14, 15 using Table 3 and Table 4 defaults. Emissions from electricity, fuel and freight are inputs, not computed from the CDM tools, unless the tools are read and implemented.
3. **Sanity checks that follow from the text:** `M` and `M_p,y` on a dry basis (finding `MOISTURE_NOT_DEDUCTED`); `FC` between 0 and 1; `PR_de` taken from the table for the declared temperature class; H:Corg per batch against the profile limit; application date within one year of production; transport distance versus the 200 km rule.
4. **Uncertainty.** v1.2 states no uncertainty requirement. The prototype's provenance-based haircut is our conservative addition, labeled as such, and not a VM0044 rule.
5. **Out of scope or declared limits:** non-soil applications beyond using the soil default; the full list of facility-type conditions until Section 3/4 are read; version 2.0 (draft, public consultation 15 Jul-17 Aug 2026) changes eligibility, H/Corg monitoring and uncertainty and must not be mixed with v1.2.
6. **Reproducible examples.** Every number used in README, video or UI is generated from stated synthetic inputs by this calculation and covered by a test (see `VERIFICATIONS.md` 4f).

## 6. Test cases derived from the text

| Case | Expected |
|---|---|
| High-tech, > 600 °C, `M` = 100 t dry, `FC` = 0.80, `PE_PS` = 0 | `CC` = 100 × 0.80 × 0.89 = 71.2 t C; `ER_PS` = 71.2 × 44/12 = 261.07 tCO2e |
| Low-technology facility (temperature not measured, default 0.56), `M` = 100 t dry, `FC` = 0.80 from the laboratory, production-stage emissions `PE_PS` assumed 0 only to isolate the permanence term (in a real low-tech case `PE_P` from Eq. 9 is not zero) | `CC` = 100 × 0.80 × 0.56 = 44.8 t C; `ER_PS` = 164.27 tCO2e |
| Low-tech, wood, pyrolysis, `FC` from Table 4 = 0.77, kiln not listed, `M` = 10 t | `PE_P` = 0.049 × `GWP_CH4` × 10; GWP from the VCS Standard, so the test passes the GWP as an input |
| H:Corg = 0.70 | Passes if the profile treats the limit as ≤ 0.7; accepted by the VM0044 profile (`operator: le`) and recorded with the low finding `METHODOLOGY_TEXT_AMBIGUOUS` (decision in `BACKEND-SPEC.md` section 14) |
| Round-trip transport 150 km vs 250 km | `LE_ts` = 0 vs computed from TOOL12 inputs |
| Wet mass passed as dry mass | `MOISTURE_NOT_DEDUCTED` |

The two arithmetic rows are computed by hand from the table values (71.2 × 44/12 = 261.0667; 44.8 × 44/12 = 164.2667) and are synthetic examples, not real credits.

## 7. Definitions (Section 3) and applicability conditions (Section 4)

Read in full on pages 6-13 of the PDF. Section 4 text that is not reproduced here (Table 1 examples, footnotes, Appendix 2 guidance on proving the fate of waste biomass) is in the PDF and was not needed for the checks below.

### 7.1 Definitions that drive checks

| Term | Definition in VM0044 v1.2 | Implementation consequence |
|---|---|---|
| **Dry weight basis** | "weight of water as a percentage of the completely dry solid"; procedures from the IBI Biochar Testing Guidelines (ASTM D1762-84); feedstock moisture may use ASTM D4442-20, oven drying at 102-105 °C to constant weight | **This is dry-basis moisture** (`w = m_water / m_dry`), so `m_dry = m_wet / (1 + w/100)`. The wet-basis formula `m_dry = m_wet * (1 - w/100)` used in the research report is a different convention. Every moisture value must carry its basis; the check converts explicitly and the finding states which basis was assumed |
| **High technology production facility** | Meets **all** of: (a) pyrolysis gases recovered or combusted; (b) at least 70% of the heat energy produced is used (lower heating value of feedstock vs biochar produced as example proof); (c) pollution controls (for example thermal oxidizer) meeting local, national or international thresholds, strictest applies; (d) production temperature measured and reported (based on the EBC Production Guidelines) | Facility class is derived from four boolean evidence items; if any is missing the facility is low-technology automatically |
| **Low technology production facility** | Any facility not meeting all high-technology conditions | Uses Eq. 6/7 with Table 4 defaults and the 0.56 permanence default if temperature is unknown |
| **Biochar** | Solid stabilized carbon from thermochemical processing in an oxygen-limited environment; pyrolysis and gasification treated interchangeably | Torrefaction and hydrothermal carbonization are excluded (condition 1) |
| **Non-soil applications** | Biochar must be **at least 50% carbon by dry weight** (charcoal use excluded) | Check on `FC` for non-soil batches |
| **Long-lived biochar products** | Average product life with evidence from peer-reviewed literature; biochar not combusted at end of life | Evidence item required for non-soil permanence claims |
| **Organic carbon content** | Mass proportion (%) of organic carbon stored, on dry weight | `FC` is a dry-basis fraction |
| **Chain of custody** | Tracking and documentation from sourcing (waste biomass) to application (soil or non-soil) | Maps to the evidence package and the audit trail (HCS) |
| **Freight** | Transport trips grouped by same vehicle class and same origin and destination | Grouping rule for TOOL12 inputs |
| **Waste biomass** | By-products, residues and waste streams of agriculture, forestry, related industries, recycling economy, manure, others in Table 1 | Feedstock eligibility check |

### 7.2 Applicability conditions (Section 4) as checkable rules

| # | Condition | Check type |
|---|---|---|
| Scope | New (greenfield) biochar production facility that sources waste biomass, produces biochar and ensures soil or non-soil use; credits only for biochar actually utilized | Facility is new (evidence); issued quantity ≤ utilized quantity |
| 1 | Eligible waste biomass through pyrolysis, gasification or biomass boilers; torrefaction and hydrothermal carbonization excluded | Process type enum |
| 2 | Low or high technology facilities allowed | Facility class |
| 3 | Producer has a health and safety program for workers | Document present |
| 4(a) | Feedstock purely biogenic waste biomass, not purpose-grown | Feedstock category |
| 4(b) | Feedstock would otherwise have decayed or been combusted without energy (guidance in Appendix 2) | Document present; human judgment |
| 4(c) | Feedstock not imported from other countries | Origin country equals project country |
| 4(d) | Table 1 sustainability criteria per feedstock category (agricultural residues, food processing residues, forestry/wood, recycling economy/aquaculture/manure, high-carbon fly ash) | Category-specific document checks; for agricultural residues removal limited to 50% of total residues without documentation; HCFA ≤ 5% of annual throughput |
| 5 | Biochar complies with the latest IBI Biochar Testing Guidelines or EBC Production Guidelines | Laboratory report present, accredited laboratory |
| 6 | Transport by ship/boat/other up to 200 km; road transport only beyond 200 km per CDM TOOL12 | Distance and mode fields |
| 7 | Mineral additives up to 10% of mass; above 10% (dry basis) the lab must show the product still meets IBI/EBC thresholds | Additive share check |
| 8 | Other evidence of sustainability: certification schemes (RSB, ISCC or others endorsed by a relevant legislative or international body) | Optional evidence |
| 9 | Biochar utilized within one year of production; permanence over 100 years | Production date to application date ≤ 1 year |
| 10 | Soil use on land other than wetlands (cropland, grassland, vegetated urban soils, forest); surface application mixed with substrates such as compost, manure or digestate; subsurface alone or mixed; **(a)** meets IBI/EBC or national material standards; **(b)** H:Corg ≤ 0.7 | Land type enum; application method; H:Corg per batch |
| 11 | Non-soil applications (cement, asphalt and others with long-term storage) only from high-technology facilities | Facility class vs application type |
| 12 | Proof that biochar and final products are long-lived (lab results, peer-reviewed research, third-party product assessment, decay rate analysis); product lifetime stated | Evidence present for non-soil |

### 7.3 Findings and schema impact

- New or sharpened findings for `SCHEMA.md`: `FEEDSTOCK_NOT_ELIGIBLE`, `FEEDSTOCK_IMPORTED`, `FACILITY_CLASS_INCONSISTENT` (claimed high technology but a required condition missing), `APPLICATION_TOO_LATE` (more than one year after production), `NON_SOIL_FROM_LOW_TECH`, `CARBON_FRACTION_BELOW_50_NON_SOIL`, `ADDITIVE_SHARE_ABOVE_LIMIT`, `TRANSPORT_MODE_NOT_ALLOWED`, `MOISTURE_BASIS_UNSPECIFIED`.
- `MOISTURE_NOT_DEDUCTED` must record which basis was used. The definition in 7.1 is dry-basis, so the prototype stores `moisture_pct` with `moisture_basis: "dry" | "wet"`, requires it, and converts to dry mass accordingly.
- The one-year rule and the 200 km rule are date and distance checks that need `produced_at`, `applied_at`, `distance_km` and `transport_mode` in the evidence kinds.

## 8. Delegated CDM tools (read from the primary PDFs, 2026-10-16)

VM0044 v1.2 points to these documents (footnotes 17, 18, 25, 26). The PDFs were downloaded by the user from cdm.unfccc.int in a normal browser (direct script download is blocked by bot protection, which is not bypassed) and stored in `research/sources/cdm-tool03/`, `cdm-tool05/`, `cdm-tool12/`. Text was extracted with `pdftotext`; equation symbols were again partly lost, so each form below is reconstructed from the equation number, units and "Where" lists (the symbol layouts of Eq. 3, 7, 15 and TOOL12 Eq. 1 were image-checked on 2026-10-17). TOOL16 v04.0 and TOOL07 v07.0 were added later (8.4, 8.5).

Mapping in VM0044: `PE_DF`, `PE_CF`, `E_PF` use TOOL03; `PE_DE`, `PE_CE`, `E_PE` use TOOL05; `LE_ts`, `LE_tap` use TOOL12 (and TOOL16 for the 200 km rule).

### 8.1 TOOL03 v03.0 — CO2 from fossil fuel combustion (EB 96 Annex 4, 22 Sep 2017)

Scope: project or leakage CO2 from fuel combustion computed from fuel quantity and properties; the calling methodology names the combustion process `j`.

| Eq. | Form | Notes |
|---|---|---|
| 1 | `PE_FC,j,y = Σ_i ( FC_i,j,y × COEF_i,y )` (tCO2/yr) | `FC` quantity of fuel type `i` burned in process `j` (mass or volume per year); `COEF` CO2 emission coefficient (tCO2 per mass or volume unit) |
| 2 (Option A, mass) | `COEF_i,y = w_C,i,y × 44/12` | `w_C` carbon mass fraction (tC per mass unit) |
| 3 (Option A, volume) | `COEF_i,y = w_C,i,y × ρ_i,y × 44/12` | `ρ` density (mass per volume unit) |
| 4 (Option B) | `COEF_i,y = NCV_i,y × EF_CO2,i,y` | `NCV` net calorific value (GJ per unit), `EF_CO2` (tCO2/GJ) |

Option A is preferred when data exist. Data sources, in order of preference: (a) supplier invoices, (b) project measurements (ISO 17025 accredited laboratory or equivalent), (c) regional or national defaults (liquid fuels only, documented sources), (d) IPCC 2006 Guidelines Vol. 2 values at the upper limit of the 95% uncertainty interval (Table 1.2 for NCV, Table 1.4 for EF_CO2). Values from (a)-(c) must be checked against the IPCC uncertainty range; values below the range need justification. Fuel quantities are metered continuously and cross-checked against purchase invoices and an annual energy balance; data gaps for household/SME users may be filled with invoices, equipment output adjusted by efficiency, the highest previous value for the same period, or a sample, if the gap does not exceed 30 consecutive days within six months. Data kept at least 2 years after the end of the last crediting period.

No fuel-specific numeric defaults are stated in the tool itself; they come from the IPCC tables, which have not been read.

### 8.2 TOOL05 v03.0 — emissions from electricity consumption (EB 96, 22 Sep 2017)

Equations 1-3 (generic approach), one for each of project, baseline and leakage:

`PE_EC,y = Σ_j ( EC_PJ,j,y × EF_EL,j,y × (1 + TDL_j,y) )` (Eq. 1; Eq. 2 for baseline with `k`, Eq. 3 for leakage with `l`), in tCO2/yr, with `EC` electricity consumed (MWh/yr), `EF_EL` emission factor for electricity generation (tCO2/MWh) and `TDL` average technical transmission and distribution losses.

Emission factor `EF_EL` by scenario:
- **Scenario A (grid consumption).** Option A1: combined margin emission factor from the "Tool to calculate the emission factor for an electricity system" (TOOL07, see 8.5). Option A2, conservative defaults: **1.3 tCO2/MWh** when scenario A applies only to project/leakage sources (or project/leakage consumption exceeds baseline consumption); **0.4 tCO2/MWh** for grids with less than 50% hydro (five-year average or long-term average), **0.25 tCO2/MWh** for other grids, when scenario A applies only to baseline sources (or baseline consumption exceeds project/leakage).
- **Scenario B (off-grid captive fossil plant).** Option B1 computes the factor from the captive plant's fuel use (Eq. 4-6, using TOOL03); Option B2 defaults: **1.3 tCO2/MWh** for project/leakage sources, **0.4 tCO2/MWh** for baseline sources (with conditions on relative consumption at the site).
- **Scenario C (grid plus captive plants).** Cases C.I-C.III (not read in detail; the prototype uses Scenario A or explicit inputs).
- **Simplified options for project/leakage under Scenario B.** Option B3: emissions from all fuel combustion in the captive plant via TOOL03. Option B4 (Eq. 7-8): `PE_EC,j,y = 11,400 × PPCP,j` (and the same for leakage), i.e. rated capacity (MW) × 8,760 h × 1.3 tCO2/MWh rounded to 11,400 tCO2 per MW per year; no monitoring required.

`TDL` rules (data table 3): in Scenario B and Scenario C case C.II, `TDL = 0`. In other cases use the latest host-country annual average (not older than 5 years) or defaults: **20%** for project/leakage sources (and for baseline sources when project+leakage consumption is larger than baseline consumption), **3%** for baseline sources (and for project/leakage sources when their consumption is smaller than the baseline). Only technical losses, not commercial losses or theft.

Conservative direction built into the tool: for project emissions the higher defaults (1.3, 20%) apply; for baseline the lower ones.

### 8.3 TOOL12 v01.1.0 — freight transport (EB 70 Annex 23, 23 Nov 2012)

Applies to road freight (and rail with the heavy-vehicle default) when transport is not the main project activity; CO2 only. Two options per freight transportation activity `f`, fixed for the crediting period.

- **Option A:** monitor fuel burned by the vehicles (outbound and return trips) and compute with TOOL03, where `PE_FC,j,y` corresponds to `PE_TR,m` or `LE_TR,m`. For biofuels use the emission factor of the fossil fuel that would otherwise be used.
- **Option B (conservative defaults), Equation 1:** `PE_TR,m` (or `LE_TR,m`) `= Σ_f ( D_f,m × FR_f,m × EF_CO2,f ) × 10^-6` in tCO2, verified on the page image (TOOL12 p. 6; the printed exponent is -6, equivalent to dividing by 10^6, from g CO2/(t·km) × km × t → g → t). `D_f,m` is the **return-trip** distance (km), `FR_f,m` the mass of freight (t), `EF_CO2,f` the default factor.
- **Defaults:** light vehicles (gross vehicle mass ≤ 26 t) **245 g CO2/(t·km)**; heavy vehicles (> 26 t) **129 g CO2/(t·km)**; the factors include loaded outbound and empty return trips; derived assuming biomass loads, 30 km/h average speed and a 1% gradient. Rail: use the heavy-vehicle default.
- **Monitoring (Option B):** freight mass continuously, from project or truck-operator records; distance determined once per activity for a reference trip (odometer or online source) and updated when it changes; vehicle class recorded.

### 8.4 TOOL16 v04.0 — project and leakage emissions from biomass (EB 96 Annex, 2017; read 2026-10-16)

Most of the tool covers biomass cultivation in dedicated plantations (soil organic carbon loss, fertilization, clearance) and leakage from shift of pre-project activities and from diversion of biomass residues. VM0044 sets those leakage terms to zero (waste biomass only), so only Section 6 matters here:
- Eq. 8: `PE_BR,y = PE_EC,y + PE_TR,y`, emissions from utilization of biomass residues = energy consumption + transport (tCO2e).
- 6.1 Energy consumption: estimated with TOOL03 and TOOL05 (this covers thermal and mechanical processing of the residue).
- 6.2 Transport of biomass residue to the processing facility: estimated with TOOL12.
- Paragraphs 31 and 33: **small-scale project activities may, unless the methodology requires otherwise, neglect** energy-consumption emissions of residue processing and may neglect transport emissions if the transportation distance is **less than 200 km**.
- The tool defines "project region" as the area within a 250 km radius of the project activity (definition (e)), used in the residue-diversion section.

Implications: the 200 km threshold in the tool is a permission for small-scale activities ("may ... neglect"), phrased as "transportation distance"; it says nothing about round trips. VM0044 v1.2 adopts it as a rule and states that distance is to-and-from (round trip) for `LE_ts`. The prototype follows VM0044's wording (round trip, count only when strictly more than 200 km, as VM0044 states), and records the TOOL16 wording in the profile notes. The boundary case of exactly 200 km should be a flagged edge case.

### 8.5 TOOL07 v07.0 — emission factor of an electricity system (60 pages; read 2026-10-16)

Used by TOOL05 Option A1. It computes the combined margin (CM) emission factor `EF_grid,CM,y` of a grid in six steps: (1) identify the relevant electricity systems, (2) optionally include off-grid plants, (3) choose the operating-margin (OM) method, (4) compute the OM, (5) compute the build margin (BM), (6) compute the CM.

- **Equation 16 (weighted average CM):** `EF_grid,CM,y = EF_grid,OM,y × w_OM + EF_grid,BM,y × w_BM`, tCO2/MWh. The weighted average is the preferred option.
- **Default weights (para. 86):** wind and solar projects `w_OM = 0.75`, `w_BM = 0.25`; all other projects `w_OM = 0.5`, `w_BM = 0.5` for the first crediting period and `w_OM = 0.25`, `w_BM = 0.75` for the second and third. Alternative weights need approval and must sum to 1.
- **Simplified CM:** allowed only when the BM data requirements cannot be met, and for LDC/SIDS/isolated grids (`CM = AOM` in the flow chart); details in paragraphs 103-106 and a default BM factor in paragraph 104 (not read in detail).
- Data needed are plant-level generation, fuel consumption and commissioning dates, normally published by the host-country authority; this is infeasible to reproduce in the prototype.

Implication: the prototype takes `EF_grid,CM,y` as an **explicit input with source and year** (for example an official national grid factor), or uses the TOOL05 Option A2 conservative defaults. TOOL07 is not re-implemented. A connected-system rule exists (factor is zero if a connected system lies in Annex I countries) and is not applied.

### 8.6 Consequences for the prototype

1. The three tools are now implementable as pure functions with a documented input set: TOOL03 (Eq. 1-4), TOOL05 Scenario A with Option A2 defaults and TDL rules, and TOOL12 Option B. Option A1 of TOOL05 (needs TOOL07) and the IPCC fuel tables are **not** available; those factors stay explicit inputs with provenance.
2. Defaults found (1.3, 0.4, 0.25 tCO2/MWh; TDL 20% and 3%; 245 and 129 g CO2/t·km; 11,400) go in the methodology profile data file with page references and `verified: true` for the tool versions read; the conditions attached to each default (relative consumption of project versus baseline) must be implemented, not just the numbers.
3. VM0044 applies these tools to project and leakage sources only (`PE_DE`, `PE_CE`, `E_PE`, `LE_ts`, `LE_tap`), so the project-side rule applies: the higher default values are the conservative ones.
4. Distance rules interact: TOOL12 uses the **return-trip** distance `D_f,m`; VM0044 counts waste biomass transport leakage only above 200 km and states the round-trip nature for `LE_ts`; TOOL16 v4 (now read, 8.4) only allows small-scale activities to neglect transport under 200 km, without saying round trip. Follow VM0044's wording and flag the exactly-200 km edge case.
5. Test vectors from the tools: TOOL12 Option B, 100 t of freight over a 100 km return-trip distance with a heavy vehicle: `100 × 100 × 129 / 10^6 = 1.29 tCO2`; with a light vehicle: `100 × 100 × 245 / 10^6 = 2.45 tCO2`. TOOL05 Option B4 with a 0.5 MW captive plant: `11,400 × 0.5 = 5,700 tCO2/yr`. TOOL05 Scenario A, Option A2(a), 100 MWh, TDL 20%: `100 × 1.3 × 1.2 = 156 tCO2`. TOOL03 Option B with illustrative inputs (`NCV` 0.043 GJ/kg, `EF` 0.0741 tCO2/GJ are placeholders, not tool values): coefficient `0.043 × 0.0741 = 0.0031863` tCO2/kg.

## For your review
- Symbol layout of Eq. 3, 7 and 15 and of TOOL12 Eq. 1: confirmed on page images (2026-10-17), no change to the numbers; only symbol names differ from the earlier draft (`P_ED`, `P_EP`, `P_EC` instead of `PE_D`, `PE_P`, `PE_C`; Eq. 4 is `P_ED = P_EDE + P_EDF`).
- H:Corg = 0.70 is decided: accepted (≤, condition 10(b)) with `METHODOLOGY_TEXT_AMBIGUOUS`; confirm or change in `BACKEND-SPEC.md` section 15.
- Sections 3 and 4 of VM0044 and TOOL03/05/07/12/16 have been read (sections 7 and 8). Decide whether to obtain the IPCC fuel tables or keep fuel and grid factors as explicit inputs (current plan).
- Confirm the TOOL12 Eq. 1 divisor (10^6) and the exact symbol layout of TOOL05 Eq. 1-3 against page images.

## 9. Changes after the independent code review (2026-10-16)

- **Exactly 200 km is counted.** The profile uses `comparison: greater_or_equal` for the transport threshold, because the VM0044 text defines "more than 200 km" in one place and "zero below 200 km" in another and leaves 200 km itself open; counting it is the conservative side. The finding `TRANSPORT_DISTANCE_AT_THRESHOLD` still flags the case. This supersedes the "strictly greater" wording in sections 3, 5 and 6 above.
- **One calendar year** replaces 365 days in the application-timing rule (a leap day made 366 days look late); 29 February maps to 28 February.
- **Period.** The batch period is derived from the application dates of its lots, not from client input.
- **TOOL03 and TOOL05** are not wired into the report: the corresponding evidence kinds were removed and emissions enter as explicit tCO2e totals with a source note. The calculators remain as tested helpers.
