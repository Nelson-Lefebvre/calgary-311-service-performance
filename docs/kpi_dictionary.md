# KPI dictionary

Shared rules:

- **Period**: requests with `requested_date` from 2022-01-01 up to (excluding) the snapshot date.
- **Valid request**: status is not `Duplicate (Open)`, `Duplicate (Closed)` or `TO BE DELETED`.
- **Time to close**: `closed_date - requested_date` in whole days, for valid closed requests with `closed_date >= requested_date`.
- **Benchmark period**: 2022-2024. **Assessed period**: 2025 onward.
- Percentiles and percentages are recomputed from request-level data at every grain. Never average them.
- A partial month or year is compared with the same days of the previous year.

| KPI | Definition | Formula | Grain | Additive | Owner (fictional) |
|---|---|---|---|---|---|
| Requests | Valid requests received | `count(*)` | day × service × community × channel | Yes | 311 & Insights |
| Median time to close | Typical days from request to closure | `median(days_to_close)` | service category × month | No | Business unit |
| P90 time to close | Days within which 90% of requests close | `quantile(days_to_close, 0.9)` | service category × month | No | Business unit |
| Benchmark | Internal target per category | P80 of 2022-2024 `days_to_close` | service category | No | 311 & Insights |
| % closed within benchmark | Share of closed requests at or under the benchmark | `closed_within / closed` | service category × month | No (recompute from counts) | Business unit |
| Open backlog | Valid requests open at month end | `requested_date <= month_end AND (closed_date IS NULL OR closed_date > month_end)` | service category × community × month end | Semi-additive (not over time) | Business unit |
| Backlog age | Open backlog split by age at month end | bands 0-7, 8-30, 31-90, 90+ days | month end | Semi-additive | Business unit |
| Duplicate rate | Share of requests flagged as duplicates | `duplicates / all requests` | service category × month | No | 311 & Insights |
| Requests per 1,000 residents | Request intensity by community | `requests / population_2019 × 1000` | community × year | No; population frozen at 2019 | 311 & Insights |

Status thresholds for % closed within benchmark: green ≥ 80%, amber 70-80%, red < 70%. Always shown with a label or icon, not colour alone.

Known limits:

- Backlog history is reconstructed from the latest dates; a reopened request shows only its last closure.
- "Closed" may mean handed over, not completed (2021 audit).
- Population is the 2019 municipal census; newer suburban communities are undercounted, which inflates their rate.
