# AI log

Each time the AI pair programmer (Claude Code) proposed something wrong, risky or debatable, and how it was caught.

| Date | What the AI proposed | Why it was wrong | How it was caught | Fix |
|---|---|---|---|---|
| 2026-11-19 | Use the portal's "Monthly", "by Community" and "by Channel" datasets as independent aggregates for reconciliation | They are charts on the same table (same `tableId`), so agreement would prove nothing | Checked each dataset's metadata before relying on it | Reconcile against `arf6-qysm`, the only separate table |
| 2026-11-19 | Filter requests to 2022 onward for every model, including the backlog | Requests opened before 2022 and still open were silently dropped from the backlog (48,244 rows) | Open count in the data (65k) was lower than the City's all-time open count (80k) | Separate `carryover` extract, used by the backlog only |
| 2026-11-19 | One P80 benchmark per category | A category mixes very different services (pothole repair vs snow clearing), so one blended target judges both badly | Reviewing the category contents before publishing | Benchmark per service, category fallback for small services |
| 2026-11-19 | Report backlog growth as December 2022 vs October 2026 (+48% for 90+ days) | Backlog is seasonal; comparing different months inflated the trend | Re-ran the comparison month-for-month | Same-month comparison: +17% for 90+ days (E5) |
| 2026-11-19 | Correlate snow requests with same-day snowfall (result about 0, suggesting no link) | Requests lag snowfall: residents report after the 24-hour clearing window | The near-zero result contradicted the obvious winter peak | Lagged window: 0.24 with the previous 3 days (E7) |
