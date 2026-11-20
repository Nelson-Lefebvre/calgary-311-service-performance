# Scoping: Calgary 311 Service Performance

> Draft written as if for a real client. The stakeholder is fictional and named as such; the data is real.

## Context

The City of Calgary receives about 500,000 service requests a year through 311 (phone, app, web), from missed garbage carts to streetlight repairs.
Each request is routed to a business unit, which closes it when the work is done or handed over.
The City publishes every request as open data, updated daily, but publishes no per-service response-time targets.

## Stakeholder (fictional)

**Operations manager of a City business unit** (for example Waste & Recycling or Roads).

| Decision they make | How often | What they need to know |
|---|---|---|
| Where to send crews this week | Weekly | Which services and communities have the oldest open requests |
| Whether a service is slipping | Monthly | Time to close against the service's own benchmark, and the trend |
| How to staff for peaks | Quarterly | When volume peaks, by how much, and whether weather drives it |

Secondary audience: 311 & Insights leadership, who want one overview page.

## Business questions

1. **Timeliness**: which services close requests most slowly against their benchmark, and is it getting worse?
2. **Backlog**: is the stock of open requests growing, and in which services or communities?
3. **Seasonality**: when do volumes peak, and are peaks associated with weather (snow, cold)?

## Scope

| In scope | Out of scope (this version) |
|---|---|
| Requests from 2022-01-01 to the snapshot date | Requests before 2022 (different definition of "closed", logic errors) |
| Volume, time to close, backlog, duplicates | Call-centre metrics (wait time, handling time): not in the data |
| Community-level maps | Point maps: coordinates are community centre points, not request addresses |
| Daily weather from Calgary International Airport | Per-capita rates beyond 2019 population (last municipal census) |
| Internal benchmark per service category | Official City targets: not published |

## Assumptions

- `closed_date` marks when the City closed the request, not proof the work was done. A 2021 audit found requests were sometimes closed on transfer. The metric is therefore called **time to close**.
- Dates have no time of day, so time to close is measured in whole days.
- The benchmark for each category is the 80th percentile of its 2022-2024 time to close. A category "misses" when it falls behind its own past performance.
- Requests marked "Duplicate" are excluded from timeliness and backlog, and reported as a duplicate rate.

## Success criteria

- Each business question is answered on the dashboard in under 5 seconds of reading.
- Every number in the README traces to a query in `docs/evidence_log.md`.
- Monthly totals reconcile with a second City extract (`arf6-qysm`) within 0.5% for complete months, or the gap is explained.
- The pipeline rebuilds from scratch with one command, at zero cost.

## User stories

- As an operations manager, I want to see which service categories are behind their benchmark this month, so that I can reassign crews.
- As an operations manager, I want to see the age of open requests by community, so that I can clear the oldest first.
- As an operations manager, I want to see how volume rose during past snow events, so that I can plan winter staffing.
- As 311 leadership, I want one page with volume, timeliness and backlog against last year, so that I can report upward.

## Prioritisation (MoSCoW)

| Must | Should | Could | Won't (this version) |
|---|---|---|---|
| Time to close vs benchmark by category | Weather association | 3-month volume forecast | Call-centre metrics |
| Monthly backlog and its age | Duplicate rate by service | Per-capita rates with 2021 federal census | Point maps |
| Community map of backlog | Channel mix (with the "Other" caveat) | | Pre-2022 trends, cloud database (Azure SQL dropped: GitHub Actions + CSV instead) |
