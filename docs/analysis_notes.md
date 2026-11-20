# Analysis notes (snapshot 2026-11-19)

Operations first: the main reader runs field crews. Information requests (tax, transit, recreation questions) are kept but shown separately.

## Q1. Timeliness: share of closed requests within their own service benchmark (P80 of 2022-2024)

By construction the benchmark period sits near 80%. The assessed period (2025 to September 2026) shows who drifted.

| Category | Type | 2022-2024 | 2025-Sep 2026 | Median days (then, now) |
|---|---|---|---|---|
| Fire | field | 81.3% | **72.7%** | 5, 6 |
| Roads & Mobility | field | 78.2% | 78.4% | 1, 1 |
| Water | field | 83.9% | 83.4% | 2, 2 |
| Bylaw & Community Safety | field | 80.4% | 83.8% | 8, 7 |
| Waste & Recycling | field | 83.1% | 83.9% | 2, 1 |
| Parks | field | 82.7% | 87.4% | 3, 3 |
| Building Inspections | field | 83.9% | 90.1% | 3, 1 |
| Animal Services | field | 84.1% | 90.3% | 1, 1 |
| Transit | information | 81.3% | 72.5% | 7, 7 |
| Property Tax & Assessment | information | 85.8% | 76.0% | 4, 3 |

Reading: among field services, only Fire slipped clearly. New requests elsewhere close as fast or faster than before.

## Q2. Backlog: field requests open at the end of October (same month every year)

| Year | Open | Open 90+ days | Roads & Mobility 90+ days |
|---|---|---|---|
| 2022 | 42,541 | 29,634 | 22,309 |
| 2023 | 36,938 | 25,616 | 19,598 |
| 2024 | 41,419 | 30,428 | 22,707 |
| 2025 | 37,087 | 26,357 | 19,462 |
| 2026 | 45,946 | 34,661 | 26,544 |

Reading: **fast on new work, slow on old work.** Timeliness of new requests held, yet requests open more than 90 days reached their highest October level (+32% on 2025, +17% on 2022). Roads & Mobility holds 77% of them, mostly scheduled repairs (curb and gutter, signs, back lanes). Caveat: some old open records may be stale rather than pending work (see the "311 Contact Us" finding); this needs confirming with the business unit before acting.

## Q3. Seasonality and weather

- Volume peaks in June (57,060 a month on average) and bottoms in February and December (about 32,800): June is 74% above February.
- Snow-related requests (sidewalk snow and ice, roads snow and ice, pathways) correlate with the **previous 3 days'** snowfall (0.24), not with same-day snowfall (about 0). Residents report after the clearing window, so crews can expect the peak one to three days after a storm.

Query for the lag (run from `dbt/`):

```sql
with r as (select requested_date d, count(*) n from fct_service_request where service_name ilike '%snow%' group by 1),
w as (select weather_date d, snowfall_cm s from stg_weather_daily),
j as (select w.d, coalesce(r.n, 0) n, w.s,
        sum(w.s) over (order by w.d rows between 3 preceding and 1 preceding) s_prev3
      from w left join r using (d) where month(w.d) in (10,11,12,1,2,3,4,5))
select corr(n, s) same_day, corr(n, s_prev3) prev_3_days from j;
```
