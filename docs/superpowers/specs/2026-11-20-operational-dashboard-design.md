# Operational dashboard: design

Date: 2026-11-20. Status: awaiting approval.

## Intent

The current Tableau Public dashboard is a stack of six charts with raw labels and no filters. It shows findings but does not help anyone act. The reader is an operations manager of a City business unit (fictional, named as such). Two uses, in this order:

1. **Weekly: which communities and which request types to send crews to first.** This is the main screen.
2. **Monthly: an overview of the situation** for a monthly review with leadership.

The dashboard is also portfolio evidence. The owner must be able to explain and rebuild every part of it in an interview, which drives the split of work below.

## Goals

**Screen 1, Priorities (default view)**
- Filters at the top: service category, age band (default 90+), request type (default field), month end (default latest).
- Community choropleth (surr-xmvs boundaries), colour = open requests in the selected age band. Clicking a community filters the rest of the screen.
- Ranked priority table: community x request type (`service_name`), open requests by age band as a heat table, worst first.
- Trend column: change in open requests versus three month ends earlier, with an option to sort by it.
- Optional measure: open requests per 1,000 residents (2019 population), off by default, with the caveat shown next to it.
- Headline line: open 90+ requests, change on the same month of the first year, share held by the top category.
- Caveat on screen: some old open records may be stale rather than pending work.

**Screen 2, Monthly situation**
- Four headline figures with change on the same month a year earlier: requests received, share closed within benchmark, open 90+ stock, Roads & Mobility share of it.
- Trend of the 90+ stock and of the benchmark share.
- Services slipping against their own benchmark (2022-2024 against 2025 onward).
- Seasonality and snow lag at the bottom.

**Both screens**
- One shared service-category filter drives both screens.
- One accent colour, red reserved for alerts, colour-blind-safe palette.
- Titles that state the finding; tooltips written as sentences; raw field names hidden.
- Data date shown ("Data to 2026-10-31, snapshot 2026-11-19").
- A phone layout of each screen.

## Non-goals

- Point maps (coordinates are community centre points).
- Live database connection (Tableau Public reads extracts only).
- Forecasts.
- Request-level drill-down to individual addresses.

## Anti-goals

- Any figure that does not reconcile with the dbt marts or the README.
- A dashboard the owner cannot explain or rebuild by hand.
- A priority list that pushes crews to records that are probably stale without saying so.

## Constraints

- Tableau Public: file sources only, saved as extracts; no row-level security; public data.
- Separate pre-aggregated sources at different grains. Tableau filters only act within one source, so cross-source filtering uses **parameters** referenced by a calculated filter in each source.
- Population is frozen at 2019 (last municipal census) and some community codes were reused (`data_quality.md` #9, #10).
- Five community codes have no polygon (`01I`, `09K`, `12I`, `ABT`, `N/A`); they stay in the table and are absent from the map.
- The benchmark share of the two latest request months is incomplete (most requests not closed yet); the monthly screen shows it greyed and the year-on-year figure uses the last complete month.

## Approaches considered

| | Approach | Trade-off |
|---|---|---|
| A | Generator writes the complete workbook (XML) | Reproducible, but built blind: 4-6 republish rounds for map, actions and layout; dashboard is "made by the AI" |
| **B (chosen)** | **Claude builds data, extracts, parameters, calculated fields and a skeleton workbook; the owner does layout and formatting in Tableau with a step-by-step guide** | Owner can defend every click in an interview; fastest path to a good-looking result; layout is no longer regenerated (monthly refresh only replaces extracts) |
| C | A, with Claude seeing the screen (computer use) | Fixes A's slowness, not the interview argument |

The owner chose B and enabled screen visibility so Claude can check the result in Tableau while the owner builds.

## Decided by the owner

- Main use: weekly priorities by community and request type; secondary: monthly overview.
- Include the three-month trend and the request-type level; per-capita rate as an option.
- Approach B.

## Split of work

**Claude**
1. New dbt mart and export `backlog_service_community_monthly`: month end x community x service category x `service_name` x age band, field and information, last 13 month ends; includes `open_3m_earlier` for the trend and `population_2019`.
2. New export `monthly_kpis`: one row per month with requests, benchmark share, open 90+ stock, Roads share, and the same values a year earlier.
3. Community boundaries joined to the backlog for the map (relationship on `comm_code`).
4. Hyper extracts, shared parameters (category, age band, request type, month end, per-capita toggle) and their filter calculations in every source, plus captions, number formats and tooltips text fields.
5. Skeleton workbook: every sheet exists with the right fields and filters; dashboards empty.
6. Step-by-step build guide in French for the owner (outside the repo, in `Projet-311/guide/`), with expected result for each step.
7. Tests: dbt tests on the new mart grain; build script asserts row counts; figures in the headline reconciled against `fct_backlog_monthly`.

**Owner**
- Dashboard layout, formatting, filter actions, phone layout, publishing.
- Saves the final `.twb`, which Claude commits back to the repo.

## Left to the builder

- Exact colours within the palette rule, sizes and spacing.
- Whether the heat table uses squares or shaded text.
