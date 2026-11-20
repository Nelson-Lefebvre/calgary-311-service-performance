# Calgary 311 Service Performance

Operations analytics on 2.5 million real City of Calgary 311 service requests (2022 onward): how fast crews close requests against a defensible benchmark, where old work piles up, and when demand peaks.

> Work in progress. Data pipeline and analysis are done on a development snapshot; the Tableau Public dashboard and final `2026-12-01` snapshot are next.

## Who this is for

A (fictional) **operations manager** of a City business unit, such as Roads or Waste & Recycling, who decides where crews go each week. Full scoping in [`docs/scoping.md`](docs/scoping.md).

| Question | Answer so far (snapshot 2026-11-19) |
|---|---|
| Which services close requests slowest against their benchmark? | Among field services, only **Fire** slipped clearly (81% to 73% within benchmark). Others held or improved. |
| Is old work piling up? | Yes. Field requests open 90+ days hit their highest October level: **34,661**, +17% on 2022. Roads & Mobility holds 77% of them. |
| When does demand peak? | June runs 74% above February. Snow-related requests follow snowfall by **1 to 3 days**, not the same day. |

Details and caveats: [`docs/analysis_notes.md`](docs/analysis_notes.md). One-page version for managers: [`docs/exec_memo.md`](docs/exec_memo.md).

## The problem worth talking about

Two numbers in this data would mislead anyone who took them at face value.

1. **The map.** Every geolocated request sits on its community's centre point, not on the request address. A dot map would show neat clusters that don't exist, so all maps here are by community.
2. **"Closed".** A 2021 City audit found requests were sometimes closed when handed to another department. So the metric is *time to close*, not *time to resolve*, and 26,489 contact-form items that were simply never closed are kept out of the backlog.

All findings and how each is handled: [`docs/data_quality.md`](docs/data_quality.md).

## How it works

```text
City of Calgary open data (SODA API) ─┐
ECCC daily weather (CALGARY INTL A) ──┼─> src/ingest.py ─> dated Parquet snapshot ─> dbt (DuckDB) ─> src/export.py ─> CSV for Tableau
Community boundaries and population ──┘      checks every page against the API count     staging, intermediate, marts, 20 tests
```

- **Cost: $0.** A GitHub Actions job ([`refresh.yml`](.github/workflows/refresh.yml)) reruns the whole pipeline on the 1st of each month and publishes the CSVs as a GitHub Release; Tableau Public reads those CSVs. Trade-off: no cloud database. DuckDB handles 2.5 million rows on a laptop, and Tableau Public cannot connect live to a database anyway.
- **Benchmark**: the City publishes no per-service targets, so each request is judged against its own service's 80th percentile time to close in 2022-2024 (category fallback for small services). See [`docs/kpi_dictionary.md`](docs/kpi_dictionary.md).
- **Backlog**: rebuilt month by month from request and closing dates, including requests opened before 2022 and still open.
- **Reconciliation**: monthly totals match the City's only separate extract (`arf6-qysm`) within 1.1% for 2024; that extract is capped at one million rows and unusable from 2025.
- **Every published number** traces to a query in [`docs/evidence_log.md`](docs/evidence_log.md).

## Run it

```powershell
uv sync
uv run python -m src.ingest --snapshot 2026-12-01
cd dbt; uv run dbt build --profiles-dir . --vars "{snapshot: 2026-12-01}"; cd ..
uv run python -m src.export
```

## How I used AI

I built this project with Claude Code as a pair programmer.

- **Claude drafted:** scaffolding, ingestion and dbt boilerplate, first versions of the docs.
- **I decided:** the business questions, KPI definitions, the internal benchmark, the analysis period and how each data anomaly is handled.
- **I verified:** every published number is logged with its query in `docs/evidence_log.md`.
- **Where AI got it wrong:** it first compared December with October backlog, which inflated growth to +48%; the same-month comparison gives +17%. All cases are in [`docs/ai_log.md`](docs/ai_log.md).

## Data sources and licence

- City of Calgary Open Data: 311 Service Requests (`iahh-g8bj`, `arf6-qysm`), Community District Boundaries (`surr-xmvs`), Historical Community Populations (`jtpc-xgsh`). Licence and attribution: *to confirm from the [Open Calgary Terms of Use](https://data.calgary.ca/d/Open-Data-Terms/u45n-7awa)*.
- Environment and Climate Change Canada, historical daily climate data, station CALGARY INTL A (climate ID 3031092).
