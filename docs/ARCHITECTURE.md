# Architecture and implementation

How the data gets from the City's open data portal to the dashboard, what each table holds, and the choices made on the way. Business context and requirements are in the [README](../README.md) and [`scoping.md`](scoping.md); KPI definitions in [`kpi_dictionary.md`](kpi_dictionary.md).

## Pipeline

```mermaid
%%{init: {'theme':'base','themeVariables':{
  'primaryColor':'#EEF3F8','primaryBorderColor':'#2C7FC4','primaryTextColor':'#10263A',
  'lineColor':'#7B8D9C','fontFamily':'Segoe UI, system-ui, sans-serif','fontSize':'13px'}}}%%
flowchart LR
    subgraph SRC["Public sources"]
        A1["311 requests<br/>iahh-g8bj · SODA API"]
        A2["Second extract<br/>arf6-qysm"]
        A3["Community boundaries<br/>surr-xmvs · GeoJSON"]
        A4["Community population<br/>jtpc-xgsh"]
        A5["ECCC daily weather<br/>CALGARY INTL A 3031092"]
    end
    subgraph ING["src/ingest.py"]
        B["Month-by-month download<br/>row count checked against the API"]
    end
    subgraph RAW["data/raw/snapshot=YYYY-MM-DD"]
        C["Parquet + GeoJSON<br/>frozen, dated snapshot"]
    end
    subgraph DBT["dbt on DuckDB"]
        D1["staging<br/>typed views"]
        D2["intermediate<br/>cleaned requests, benchmarks"]
        D3["marts<br/>facts at stated grain"]
    end
    subgraph OUT["src/export.py"]
        E["CSV + GeoJSON<br/>data/processed/exports"]
    end
    F["Tableau Public<br/>dashboard"]
    G["GitHub Release<br/>data-YYYY-MM-DD"]

    A1 & A2 & A3 & A4 & A5 --> B --> C --> D1 --> D2 --> D3 --> E --> F
    E --> G
```

The whole chain runs on a laptop in about an hour (the API serves roughly one month of requests per minute) and costs nothing. [`.github/workflows/refresh.yml`](../.github/workflows/refresh.yml) runs the same four commands on the 1st of each month and publishes the exports as a GitHub Release.

## Sources

| Source | Id | What it gives | Used for |
|---|---|---|---|
| 311 Service Requests | `iahh-g8bj` | One row per request since 2010: dates (no time of day), status, service, community | Everything |
| 311 Service Requests (separate extract) | `arf6-qysm` | Same requests from a different table, capped at 1M rows | Reconciliation, 2024 only |
| Community District Boundaries | `surr-xmvs` | 313 community polygons with `comm_code` | Map |
| Historical Community Populations | `jtpc-xgsh` | Population by community, last census 2019 | Context only |
| ECCC historical daily climate | station 3031092 | Snowfall, snow on ground, temperature, precipitation | Weather association |

The portal also lists "Monthly", "by Community" and "by Channel" 311 datasets. They are saved charts on `iahh-g8bj` (same `tableId`), so they cannot serve as an independent check.

### Terms

City of Calgary data is published under the Open Government Licence - City of Calgary (to confirm on the [Terms of Use page](https://data.calgary.ca/d/Open-Data-Terms/u45n-7awa) before publishing). ECCC data is published under the Open Government Licence - Canada. Both allow reuse with attribution.

## dbt lineage

```mermaid
%%{init: {'theme':'base','themeVariables':{
  'primaryColor':'#EEF3F8','primaryBorderColor':'#2C7FC4','primaryTextColor':'#10263A',
  'lineColor':'#7B8D9C','fontFamily':'Segoe UI, system-ui, sans-serif','fontSize':'13px'}}}%%
flowchart LR
    s1[stg_requests] --> i1[int_requests]
    s2[stg_carryover] --> i1
    seed[(service_category_map<br/>seed)] --> i1
    i1 --> i2[int_category_benchmark]
    i1 --> f1[fct_service_request]
    i2 --> f1
    f1 --> f2[fct_category_monthly]
    i1 --> f3[fct_backlog_monthly]
    i1 --> f6[fct_backlog_service_monthly]
    s5 --> f6
    f1 --> f4[fct_daily_weather_requests]
    s4[stg_weather_daily] --> f4
    s3[stg_second_extract] --> f5[reconciliation_monthly]
    s1 --> f5
    s5[stg_community_population]
```

`stg_carryover` holds requests opened before 2022 and still open at the start of the period. Only the backlog uses them; without them 48,244 open requests vanished from the stock (see [`ai_log.md`](ai_log.md)).

## Data model

```mermaid
%%{init: {'theme':'base','themeVariables':{
  'primaryColor':'#EEF3F8','primaryBorderColor':'#2C7FC4','primaryTextColor':'#10263A',
  'lineColor':'#7B8D9C','fontFamily':'Segoe UI, system-ui, sans-serif','fontSize':'13px'}}}%%
erDiagram
    service_category_map ||--o{ fct_service_request : "service_prefix"
    int_category_benchmark ||--o{ fct_service_request : "benchmark_key"
    fct_service_request }o--|| stg_weather_daily : "requested_date = weather_date"
    fct_service_request }o--o| communities : "comm_code"

    fct_service_request {
        string service_request_id PK
        date   requested_date
        date   closed_date "null while open"
        string service_name
        string service_category "from seed"
        string request_type "field / information / unmapped"
        string comm_code FK
        bool   is_closed_valid "closed, not duplicate, not deleted"
        int    days_to_close "whole days, dates only"
        double benchmark_days_p80 "own service, 2022-2024"
        bool   is_within_benchmark
        bool   is_assessed_period "requested 2025 or later"
    }
    int_category_benchmark {
        string benchmark_key PK "service, or category fallback"
        string benchmark_level "service / category"
        int    benchmark_closed_requests
        double benchmark_days_p80
        double benchmark_days_p90
    }
    service_category_map {
        string service_prefix PK
        string service_category
        string request_type
    }
    stg_weather_daily {
        date   weather_date PK
        double snowfall_cm
        double snow_on_ground_cm
        double min_temp_c
        double precipitation_mm
    }
    communities {
        string comm_code PK
        string name
        string sector
        geometry polygon
    }
```

The aggregate marts are built from `fct_service_request` (or `int_requests` for the backlog) and carry no foreign keys of their own:

| Table | Grain (one row is) | Rows | Additive? |
|---|---|---|---|
| `fct_service_request` | one request | 2,471,994 | yes (counts) |
| `fct_category_monthly` | service category x request type x month of request | 987 | counts yes; ratios and medians no, recompute from counts |
| `fct_backlog_monthly` | month end x category x request type x community x age band | 377,576 | across categories and communities yes; across months **no** (a stock) |
| `fct_backlog_service_monthly` | month end x request type x category x service name x community x age band, last 13 month ends, with the value 3 month ends earlier | 317,531 | same as `fct_backlog_monthly` |
| `fct_daily_weather_requests` | day x service category | 28,014 | yes |
| `reconciliation_monthly` | month (only 2024 is comparable) | 35 | n/a |
| `int_category_benchmark` | service (or category fallback) | 463 | n/a |

Two rules follow from that table and apply in every tool that reads the marts:

- A ratio is computed from its numerator and denominator at the grain shown, never averaged: `sum(closed_within_benchmark) / sum(closed_with_benchmark)`.
- The backlog is filtered to one month end before it is summed. Adding two month ends counts the same open requests twice.

## Tableau model

The dashboard has two screens. **Priorities** (weekly): which communities and which request types to send crews to first. **Monthly situation**: an overview for a monthly review. `tableau/build_workbook.py` writes the data sources, parameters, calculated fields and one sheet per visual; the dashboard layout is done by hand in Tableau Public.

| Source | File | Grain | Used by |
|---|---|---|---|
| Operations backlog | `backlog_service_community_monthly.csv` (+ `communities.geojson` on `comm_code` for the map) | month end x request type x category x service name x community x days open, last 13 month ends | Priorities: map, priority table, 3-month trend, communities |
| Monthly KPIs | `monthly_kpis.csv` | request month, field requests | Both screens: headline figures; monthly trends |
| Timeliness | `category_monthly.csv` | category x request type x month | Monthly: slipping services, seasonality |
| Snow | `daily_snow_requests.csv` | day | Monthly: snow lag |

The sources have different grains, so a normal Tableau filter acts on one source only. The shared filters are **parameters** (Category, Days open, Request type, Month end, Per 1,000 residents). Each source has a `Keep row` calculated field that compares its rows with the parameters, and every sheet keeps the rows where it is true. The priority sheets set it as a context filter so their Top 25 is computed after it. Monthly KPIs are city-wide field requests: they have no category column, and a Roads & Mobility share per category would mean nothing.

Two dates on one screen are deliberate. A month-end backlog stock is final once the month is over (latest: October 2026). Flow figures (requests, share closed within benchmark) wait two months, because most requests of the last month are not closed yet (latest complete: September 2026). Each tile says which month it shows.

Per 1,000 residents uses the 2019 municipal census, divides by the community's population once (not once per row), and is shown only by community.

Earlier version of the model (one source per question):

```mermaid
%%{init: {'theme':'base','themeVariables':{
  'primaryColor':'#EEF3F8','primaryBorderColor':'#2C7FC4','primaryTextColor':'#10263A',
  'lineColor':'#7B8D9C','fontFamily':'Segoe UI, system-ui, sans-serif','fontSize':'13px'}}}%%
flowchart LR
    subgraph S1["Source 1 · timeliness"]
        cm[category_monthly.csv]
    end
    subgraph S2["Source 2 · backlog trend"]
        bc[backlog_category_monthly.csv]
    end
    subgraph S3["Source 3 · map"]
        geo[communities.geojson] ---|comm_code| bcom[backlog_community_monthly.csv]
    end
    subgraph S4["Source 4 · weather"]
        sn[daily_snow_requests.csv]
    end
    cm -. "dashboard filter action<br/>service_category" .- bc
```

Relating the other files on month or category would mix a month of request with a month-end stock, and Tableau would add values that do not add up.

## Tests

| Layer | Test | Why |
|---|---|---|
| Ingestion | Each month's row count equals the API's `count(*)` at download, or the run fails | A silent partial page would shrink every figure |
| Ingestion | Boundaries file must have geometry and `comm_code` on every feature | `ab7m-fwn6` once returned 313 features with null geometry |
| Ingestion (pytest) | Month windows cross year ends and include the partial last month | Off-by-one months are the classic API pagination bug |
| Staging | `service_request_id` unique and not null; `status_description` in accepted values | Duplicated or unexpected rows |
| Staging | `weather_date` unique | One weather row per day, or the join multiplies requests |
| Marts | Unique grain on `fct_category_monthly` and `fct_backlog_monthly` | Catches a missing group-by column (it did once: see `ai_log.md`) |
| Marts | `days_to_close` never negative | Closing before opening means a parsing error |
| Marts | Each 2024 month within 1.5% of `arf6-qysm` | The only independent check on completeness (0.2-1.1% in practice) |
| Marts | At least 97% of requests mapped to a category | Keeps the "Other" bucket small enough to ignore |
| Intermediate | A closed request has a closing date on or after its request date | Internal consistency of status and dates |
| Marts | Every request day has a weather row (warns) | The weather join must not drop days silently |

`dbt build` currently gives 20 passing tests and 1 warning (plus 17 pytest checks on the exports and the workbook: `uv run pytest`): 5 request days have no weather row at the airport station, kept as nulls.

## Running it

```powershell
uv sync
uv run python -m src.ingest --snapshot 2026-12-01
cd dbt; uv run dbt build --profiles-dir . --vars "{snapshot: 2026-12-01}"; cd ..
uv run python -m src.export
uv run python tableau/build_workbook.py
```

`tableau/build_workbook.py` writes `tableau/calgary_311.twb` (sources, parameters, calculated fields, sheets, empty dashboards) and one Hyper extract per source in `data/processed/extracts/` (Tableau Public only saves workbooks built on extracts). Open the workbook in Tableau Public and use File > Save to Tableau Public.

Or trigger **Actions > Monthly refresh > Run workflow** on GitHub and download the Release. GitHub disables a scheduled workflow after 60 days without repository activity; re-enable it from the Actions tab.

## Assumed trade-offs

| Choice | Alternative | Why |
|---|---|---|
| DuckDB + CSV exports | Cloud database (Azure SQL free offer was planned) | Tableau Public cannot connect live to a database, and 2.5M rows fit on a laptop. The cloud database added cost risk and setup with no change for the reader |
| GitHub Actions monthly job | Scheduled cloud function | Free on a public repository, no account or secret to manage |
| Internal benchmark (P80 of 2022-2024 per service) | Official targets | The City publishes none. Each service is judged against its own past, so the ranking says who drifted, not who is slow by nature |
| Time to close | Time to resolve | The data records when a request was closed, not whether the work was done |
| Community-level maps only | Point map | Every geolocated request sits on its community's centre point |
| Period from 2022 | Full history from 2010 | Earlier years carry known logic errors and a different closing practice |
| Whole days | Hours | The dataset has dates without times |
