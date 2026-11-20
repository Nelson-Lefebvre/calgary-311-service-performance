# Evidence log

One row per number published in the README or dashboard. Snapshot `2026-11-19` until the `2026-12-01` snapshot replaces it; re-run the queries and update this table then.

Confidence: **High** = computed and cross-checked against an independent source; **Medium** = computed with internal checks only; **Low** = external, unverified (never a headline).

| # | Claim | Source / model | Query (DuckDB, run from `dbt/`) | Cross-check | Confidence |
|---|---|---|---|---|---|
| E1 | 2.49M requests since 2022 (2,494,730) | `stg_requests` | `select count(*) from stg_requests` | Equals the API `count(*)` per month at download (enforced by `src/ingest.py`); 2024 within 1.1% of `arf6-qysm` | High |
| E2 | 2.47M valid requests (2,471,994), 75% field work | `fct_service_request` | `select count(*), avg(case when request_type='field' then 1.0 else 0 end) from fct_service_request` | E1 minus duplicates (22,736) | High |
| E3 | 72% of field requests close within 7 days | `fct_service_request` | `avg(case when days_to_close<=7 then 1.0 else 0 end) filter (where request_type='field')` | Quarterly median 1-4 days, stable | Medium |
| E4 | Field backlog at end of October: 42,541 (2022), 37,087 (2025), 45,946 (2026) | `fct_backlog_monthly` | `sum(open_requests) filter (where request_type='field') ... where month(month_end)=10` | Same month each year to avoid seasonality | Medium |
| E5 | Field requests open more than 90 days, end of October: 29,634 (2022) to 34,661 (2026), +17% | `fct_backlog_monthly` | as E4 with `age_band='90+'` | Same-month comparison | Medium |
| E6 | Roads & Mobility holds 77% of field requests open 90+ days (26,544 of 34,661, Oct 2026) | `fct_backlog_monthly` | as E5 grouped by `service_category` | Top open services: curb and gutter repair, signs, back lanes | Medium |
| E7 | Snow-related requests follow snowfall by 1-3 days: correlation 0.24 with the previous 3 days' snowfall, about 0 the same day | `stg_weather_daily`, `fct_service_request` | see `docs/analysis_notes.md` | Matches the 24-hour sidewalk-clearing bylaw delay | Medium |
| E8 | June volume is 74% above February (57,060 vs 32,778 per month on average) | `fct_service_request` | monthly average over complete years | Seasonal shape repeats each year | Medium |
| E9 | 4,492 reopened requests; 26,489 contact-form items never closed | `int_requests` | see `docs/data_quality.md` | Manual inspection of service names and dates | High |
