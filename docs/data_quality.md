# Data quality

Snapshot `2026-11-19` (development snapshot; the published snapshot will be `2026-12-01`).
Every figure below comes from `dbt build` on that snapshot or from the queries in `docs/evidence_log.md`.

## Scope decision

Only requests from 2022-01-01 are analysed. Before 2022, the City used inconsistent definitions of "closed" (2021 audit) and the data contains logic errors that disappear afterwards:

| Check | 2010-2026 | 2022 onward |
|---|---|---|
| Requests closed before they were opened | 927 | 0 |
| "Closed" with no closing date | 6 | 0 |
| "TO BE DELETED" rows | 103 | 0 |

## Findings and how they are handled

| # | Finding | Size (2022+) | Handling |
|---|---|---|---|
| 1 | **Coordinates are community centre points**, not request addresses (`location_type` is only "Community Centrepoint" or "None", despite the documented third value "Service Request Location") | 100% of geolocated rows | No point map. Maps are by community polygon. |
| 2 | **"Closed" may mean handed over**, not completed (2021 audit, LiveWire Calgary 2024) | n/a | The metric is named *time to close*, never *time to resolve*. |
| 3 | **Reopened requests**: status "Open" with a closing date | 4,492 | Treated as open (`effective_closed_date` is null); flagged `is_reopened`. |
| 4 | **Duplicates** flagged by the City | 22,736 | Excluded from timeliness and backlog; reported as a duplicate rate. |
| 5 | **Unstable service names**: department renames change prefixes (CBS became DBBS; AT and Finance both handle property tax) | 787 names, 105 prefixes | Seed `service_category_map.csv` maps 40 prefixes to 15 stable categories and tags each as *field* or *information*. Unmapped share: 1.3% ("Other"); a test fails below 97% coverage. |
| 6 | **"311 Contact Us" never closed**: contact-form items opened 2019 to Aug 2025 and left open | 26,489 open | Excluded from the backlog: they are not open work. |
| 7 | **Pre-2022 requests still open in 2022** would be missed by a 2022 filter | 48,244 | Ingested separately (`carryover`) and counted in the backlog only. |
| 8 | **No community** (`location_type = None`) | about 5.8% of all-time rows | Kept in totals as "No community"; excluded from maps. |
| 9 | **Population codes reused**: WBN, OGD, PKD and SIL each name two communities in the 2019 census table | 4 codes | Key is code + name. |
| 10 | **Population frozen at 2019** (last municipal census) | all communities | Per-capita rates carry a warning; newer suburbs are undercounted. |
| 11 | **Dates have no time of day** | 100% | Time to close in whole days; 0 = closed the same day. |
| 12 | **Weather gaps** at CALGARY INTL A (3031092) | 5 days | Left as missing; test `assert_weather_coverage` warns. |
| 13 | **Ambiguous channel "Other"** | about 29% of all-time rows | Channel mix shown with a caveat. |
| 14 | **Codes without a boundary**: `09K`, `ABT` and `N/A` have no polygon in `surr-xmvs` | 554 of 45,946 open field requests (1.2%, Oct 2026) | Kept in totals; absent from the map. |

## Reconciliation with a second extract

The three "aggregate" datasets on the portal (`88ea-sw8f`, `3pe6-xec5`, `sbdg-se3c`) are charts built on the same table as `iahh-g8bj` (same `tableId`), so they cannot validate it.
The only separate table is `arf6-qysm` ("Current Year"):

- **2024**: the second extract runs 0.2% to 1.1% short every month (3,408 requests present in the main table are missing from it, none the other way). Within tolerance (1.5%), test passes.
- **2025 onward**: the second extract stops being usable. It holds exactly 1,000,000 rows and whole months collapse (July 2025: 2,378 rows against 53,671; November 2025: 53 against 33,055). It is capped, not complete, despite its name.

Conclusion: the main table is internally consistent and matches the only independent extract where that extract is complete.

## Benchmark coverage

97.4% of closed requests are judged against their own service's P80 (services with at least 100 closed requests in 2022-2024); 2.6% fall back to their category's P80.
