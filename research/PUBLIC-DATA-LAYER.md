# Public data layer: what ClimAudit could ingest (research notes, 2026-10-17)

Status: research by a delegated agent from provider pages; nothing was downloaded or integrated. Items marked UNVERIFIED were not confirmed on an official page. Licence and terms must be re-read before any integration. Nothing here is legal advice.

## A. Credit and project databases (double counting, project identity)

| Source | Ingestible | Access | Licence / terms | Notes |
|---|---|---|---|---|
| Berkeley Voluntary Registry Offsets Database | Yes, snapshot | One .xlsx per release (v2026-08 seen), no auth | CC BY 4.0, citation required | Projects, issuances, retirements for ACR, ART, CAR, Gold Standard, Isometric, Verra. Column list and coordinates UNVERIFIED |
| CarbonPlan OffsetsDB | Yes, bulk | Zipped CSV/Parquet on S3 and Python package `offsets-db-data`, no auth | Code MIT; data: no copyright claimed, terms of data access apply | Freshness contradictory (paused vs daily): check the file's Last-Modified before use |
| Isometric registry API | Yes, live | REST, docs.isometric.com | UNVERIFIED (auth, rate limits, terms) | Suppliers, projects, issuances, retirements, LCA data per batch |
| Puro.earth registry API | No | Authenticated, onboarding needed | not found | Public web registry is browse-only; do not scrape |
| Verra registry | No official export or API found | Web search; unofficial scrapers exist | Terms of Use not read | Treat as a manual lookup link; platform migrated around 2026-07-27 |
| Gold Standard | No public API found | Web registry | UNVERIFIED | |
| CDR.fyi | No | Premium portal | not read | |
| EBC / Carbon Standards International | No bulk data | Producer batch IDs only | Ithaka Institute: database use private only | |
| Open biochar registry with a download | None found | | | |

Possible uses: duplicate project or serial check (Verra serial format allows block range, vintage and country to be parsed and compared), country-level location plausibility, methodology and vintage sanity (VM0044 v1.2 active since 2025-06-27), issuance versus claim plausibility. A hit is a flag for the human verifier, never proof of fraud.

## B. Other checks

| Source | Check | Access and terms (as read) | Limits |
|---|---|---|---|
| ESA WorldCover v200 (2021) | Land cover at the application point | Public S3, no key, CC BY 4.0, 10 m | Static snapshot, coarse classes |
| Open-Meteo historical API | Weather on claimed application dates | REST, no key, free for non-commercial use (CC BY 4.0) | Free tier not for commercial products |
| Nominatim and OSRM demo | Transport distance versus the 200 km rule | REST, 1 request/s, identifying User-Agent, ODbL | Light use only; great-circle distance is a safe fallback |
| GLEIF LEI API | Legal entity identity | REST, CC0 | Many small producers have no LEI |
| Ember electricity data | Grid emission factor | REST, free key | Country, annual |
| NASA FIRMS | Thermal anomalies at a facility | Free key required | Small kilns are below detection, weak evidence only |
| SoilGrids | Soil sanity check | REST API paused | File download only |
| Dynamic World | Near-real-time land cover | Google Earth Engine, free for non-commercial use | Needs a registration |
| OpenSanctions | Sanctions screening | CC BY-NC 4.0 | Non-commercial only, false positives |
| Hansen / Global Forest Watch, NASA POWER, FAOSTAT, JRC, Köppen-Geiger, IPCC EFDB, IEA, OpenCorporates | various | UNVERIFIED | Not confirmed |

## C. Shortlist for the hackathon

1. Berkeley database snapshot (cleanest licence).
2. OffsetsDB (after checking freshness).
3. Isometric public API (after confirming auth and terms).
4. ESA WorldCover on public S3.
5. Open-Meteo historical weather.
6. Great-circle distance, optionally Nominatim and OSRM.
7. GLEIF LEI lookup.
8. Ember grid factors.

Not usable as-is: Verra bulk data, Puro API, CDR.fyi, EBC data, SoilGrids API (paused), OpenSanctions in a commercial product.
