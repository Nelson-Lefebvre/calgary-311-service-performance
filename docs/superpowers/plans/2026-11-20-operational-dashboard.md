# Operational Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the owner the data, extracts, parameters, calculated fields and a skeleton workbook for a two-screen operational dashboard (Priorities, Monthly situation), plus a French build guide.

**Architecture:** One new dbt mart at request-type grain feeds a new export; a monthly KPI export is computed in `src/export.py` from existing marts. `tableau/build_workbook.py` is rewritten to emit Hyper extracts, shared parameters and one skeleton sheet per visual, with empty dashboards. The owner lays out the dashboards in Tableau Public.

**Tech Stack:** DuckDB, dbt-duckdb, Python 3.13 (`uv`), tableauhyperapi, Tableau Public 2026.3, pytest.

**Spec:** `docs/superpowers/specs/2026-11-20-operational-dashboard-design.md`

## Global Constraints

- Tableau Public reads file sources saved as extracts only.
- Field requests are the default; information requests stay available through `request_type`.
- Backlog is semi-additive: sum across categories or communities, never across months.
- Exclude `311 Contact Us` from backlog figures (same rule as `fct_backlog_monthly`).
- Benchmark share of the two latest request months is incomplete: flag it, never headline it.
- Population is 2019; show the caveat text "Population from the 2019 municipal census." next to any per-capita figure.
- Every headline figure must reconcile with `fct_backlog_monthly` / `fct_category_monthly`.
- Commits on this repo end with `Co-Authored-By: Claude <noreply@anthropic.com>`; no Claude Code footer.
- Never push to `main`; work on branch `operational-dashboard`, open a PR.

## Review Focus

1. Community x request type with open requests now but none three months earlier (or the reverse): row must exist with 0 on the missing side, not vanish. Test in Task 1.
2. Communities with no population or population 0 (`N/A`, industrial areas): per-capita value null, never a division error or infinity. Test in Task 1.
3. Monthly KPI year-on-year for the first 12 months (2022): prior-year columns null, not 0. Test in Task 2.
4. Parameter "All" value for category: every sheet shows all categories when selected. Check in Task 3 (calc formula) and Task 5 (screenshot).
5. Latest month end is the default of the month parameter and moves with the monthly refresh: the parameter's list is built from data at build time. Test in Task 3.

---

### Task 0: Worktree data link

**Files:** none committed.

- [ ] **Step 1:** Replace the empty `data` folder of the worktree with a junction to the main checkout's data: `cmd /c rmdir data && cmd /c mklink /J data ..\..\..\data` (run from the worktree root; `data` must be empty first).
- [ ] **Step 2:** Verify: `ls data/processed` lists `calgary311.duckdb`, `exports`, `tableau`.

### Task 1: Mart `fct_backlog_service_monthly` and its export

**Files:**
- Create: `dbt/models/marts/fct_backlog_service_monthly.sql`
- Modify: `dbt/models/marts/_marts.yml`, `src/export.py` (QUERIES)
- Test: `tests/test_exports.py`

**Interfaces:**
- Produces table `fct_backlog_service_monthly`, grain month_end x request_type x service_category x service_name x comm_code x age_band, columns: `month_end date, request_type, service_category, service_name, comm_code, comm_name, age_band, open_requests int, open_3m_earlier int, population_2019 int null`.
- Produces export `backlog_service_community_monthly.csv`: the last 13 complete month ends of that table.

- [ ] **Step 1: Write failing tests** in `tests/test_exports.py`, reading `data/processed/calgary311.duckdb` read-only (`pytest.skip` if absent):

```python
def test_service_mart_reconciles_with_backlog(con):
    # same month end, same totals by category and age band
    diff = con.sql("""
        select count(*) from (
          select month_end, service_category, request_type, age_band, sum(open_requests) n
          from fct_backlog_service_monthly group by all
        ) a full join (
          select month_end, service_category, request_type, age_band, sum(open_requests) n
          from fct_backlog_monthly
          where month_end >= (select min(month_end) from fct_backlog_service_monthly)
          group by all
        ) b using (month_end, service_category, request_type, age_band)
        where a.n is distinct from b.n""").fetchone()[0]
    assert diff == 0

def test_trend_keeps_rows_that_appear_or_disappear(con):
    # a row open 3 months ago but closed now must still exist with open_requests = 0
    assert con.sql("select count(*) from fct_backlog_service_monthly where open_requests = 0 and open_3m_earlier > 0").fetchone()[0] > 0
    assert con.sql("select count(*) from fct_backlog_service_monthly where open_3m_earlier is null").fetchone()[0] == 0

def test_population_never_zero(con):
    assert con.sql("select count(*) from fct_backlog_service_monthly where population_2019 = 0").fetchone()[0] == 0

def test_export_has_13_month_ends():
    import duckdb
    n = duckdb.sql("select count(distinct month_end) from 'data/processed/exports/backlog_service_community_monthly.csv'").fetchone()[0]
    assert n == 13
```

- [ ] **Step 2:** `uv run pytest tests/test_exports.py -v`. Expected: FAIL (table does not exist).
- [ ] **Step 3: Write the mart.** Reuse the `month_ends` / `open_at_month_end` CTEs of `fct_backlog_monthly.sql`, add `r.service_name`, keep the last 16 complete month ends (13 shown + 3 look-back). Aggregate to the grain, then full outer join the aggregate to itself on the grain with `b.month_end = last_day(a.month_end - interval 3 month)`; `coalesce` counts to 0; keep rows whose month end is within the last 13. Left join `stg_community_population` on `comm_code`, `nullif(population_2019, 0)`. Add `unique_combination` test on the grain in `_marts.yml`.
- [ ] **Step 4:** Add export query `backlog_service_community_monthly` to `QUERIES`: `select * from fct_backlog_service_monthly order by month_end, comm_code, service_name, age_band`.
- [ ] **Step 5:** Run `cd dbt && uv run dbt build --profiles-dir . --select fct_backlog_service_monthly --vars "{snapshot: 2026-11-19}"` then `uv run python -m src.export` then `uv run pytest tests -v`. Expected: dbt PASS, all tests PASS, export row count printed (about 250,000).
- [ ] **Step 6: Commit** `feat: request-type backlog mart with 3-month trend and population`.

### Task 2: Monthly KPI export

**Files:**
- Modify: `src/export.py` (QUERIES), `tests/test_exports.py`

**Interfaces:**
- Produces `monthly_kpis.csv`, one row per request month from 2022-01, field requests only: `month date, requests int, within_benchmark_share double, open_90_plus int, roads_share_of_90_plus double, is_complete bool, requests_ly int, within_benchmark_share_ly double, open_90_plus_ly int, roads_share_of_90_plus_ly double`. `_ly` = same month one year earlier, null when absent. `is_complete` = false for the two latest request months. Backlog columns use the month end of `month`.

- [ ] **Step 1: Failing tests:**

```python
def test_kpis_latest_complete_backlog_matches_readme():
    import duckdb
    r = duckdb.sql("select open_90_plus, round(roads_share_of_90_plus*100) from 'data/processed/exports/monthly_kpis.csv' where month = date '2026-10-01'").fetchone()
    assert r == (34661, 77)

def test_kpis_first_year_has_null_prior_year():
    import duckdb
    assert duckdb.sql("select count(*) from 'data/processed/exports/monthly_kpis.csv' where year(month) = 2022 and requests_ly is not null").fetchone()[0] == 0

def test_kpis_two_latest_months_incomplete():
    import duckdb
    assert duckdb.sql("select list(is_complete order by month desc)[1:3] from 'data/processed/exports/monthly_kpis.csv'").fetchone()[0] == [False, False, True]
```

- [ ] **Step 2:** Run, expect FAIL (file missing).
- [ ] **Step 3:** Add query `monthly_kpis`: requests and benchmark share from `fct_category_monthly` (share = `sum(closed_within_benchmark) / sum(closed_with_benchmark)`), 90+ stock and Roads share from `fct_backlog_monthly` joined on `last_day(month)`; prior-year columns by self-join on `month - interval 12 month`.
- [ ] **Step 4:** Re-export, run tests. Expected PASS.
- [ ] **Step 5: Commit** `feat: monthly KPI export with prior-year values`.

### Task 3: Workbook generator: sources, extracts, parameters, calculations

**Files:**
- Modify: `tableau/build_workbook.py` (SOURCES, CALCS, new PARAMETERS, `datasource()`)
- Test: `tests/test_workbook.py`

**Interfaces:**
- SOURCES ids: `svc` (backlog_service_community_monthly), `kpi` (monthly_kpis), `cm`, `sn` kept; `bc`, `bcom` dropped from the workbook (CSVs still exported).
- Community map: `svc` joined to `communities.geojson` on `comm_code` as a second relation in the same datasource (left join; codes without polygon keep their rows).
- Parameters (datasource `Parameters`): `Category` (string list: "All" + categories from `category_monthly.csv`, default "All"), `Age band` (list 0-7, 8-30, 31-90, 90+, default 90+), `Request type` (field, information, default field), `Month end` (date list from `svc` month ends, default latest), `Per 1,000 residents` (boolean, default false).
- Calculations in `svc`: `Keep row` = `([Parameters].[Category]="All" OR [service_category]=[Parameters].[Category]) AND [age_band]=[Parameters].[Age band] AND [request_type]=[Parameters].[Request type] AND [month_end]=[Parameters].[Month end]`; `Open` = `IF [Parameters].[Per 1,000 residents] THEN SUM([open_requests])/SUM([population_2019])*1000 ELSE SUM([open_requests]) END`; `Change 3 months` = `SUM([open_requests])-SUM([open_3m_earlier])`; `Change 3 months %` = `Change / NULLIF(SUM([open_3m_earlier]),0)`; `Tooltip text` sentence. Same `Keep row` category clause in `cm` and `kpi`.
- Captions and number formats on every field; `p0%` on shares.

- [ ] **Step 1: Failing tests** in `tests/test_workbook.py`: build into a temp dir and parse the `.twb` with `xml.etree`:

```python
def test_parameters_defaults(built):
    p = {c.get("caption"): c for c in built.iter("column") if c.get("param-domain-type")}
    assert set(p) == {"Category", "Age band", "Request type", "Month end", "Per 1,000 residents"}
    assert p["Age band"].get("value") == '"90+"'
    assert p["Month end"].get("value") == "#2026-10-31#"

def test_every_extract_row_count_matches_csv(built_counts):
    for sid, (hyper_rows, csv_rows) in built_counts.items():
        assert hyper_rows == csv_rows, sid
```

- [ ] **Step 2:** Run, expect FAIL.
- [ ] **Step 3:** Implement. Latest month end and category list are read from the CSVs at build time (never hard-coded). Expose `build(exports: Path, out: Path) -> dict[str, tuple[int, int]]` returning row counts for the test.
- [ ] **Step 4:** Run tests, expect PASS. Open the `.twb` in Tableau Public; take a screenshot (PowerShell `CopyFromScreen`) and check: no error dialog, 4 data sources, 5 parameters.
- [ ] **Step 5: Commit** `feat: workbook sources, extracts, shared parameters and calculations`.

### Task 4: Skeleton sheets

**Files:**
- Modify: `tableau/build_workbook.py` (`build()` sheets)

Sheets (titles state the finding; each filtered by `Keep row` = true):

| Sheet | Source | Content |
|---|---|---|
| P1 Map | svc | filled map by community, colour = `Open`, sequential single hue |
| P2 Priority table | svc | rows community, request type; columns age band; text + colour = open requests; sort desc by total |
| P3 Trend 3 months | svc | bar per community x request type, `Change 3 months`, red only when > 0 |
| P4 Headline | kpi | text: 90+ stock, change vs same month 2022, Roads share |
| M1 KPI tiles | kpi | four numbers with prior-year change, latest complete month |
| M2 Stock trend | kpi | line `open_90_plus` by month |
| M3 Benchmark trend | kpi | line `within_benchmark_share`, incomplete months greyed |
| M4 Slipping services | cm | dot plot, 2022-2024 vs 2025 on, by category |
| M5 Seasonality | cm | kept from current workbook |
| M6 Snow | sn | kept from current workbook |

Two empty dashboards `Priorities` and `Monthly situation` (1300 x 900, plus phone device layout), each with the caveat text zone and data-date line.

- [ ] **Step 1:** Implement the sheets.
- [ ] **Step 2:** Run `uv run pytest tests -v` (PASS), rebuild, open in Tableau Public, screenshot each sheet tab. Expected: every sheet renders with data, no red pills, map shows Calgary communities.
- [ ] **Step 3: Commit** `feat: skeleton sheets for priorities and monthly screens`.

### Task 5: French build guide and docs

**Files:**
- Create: `../../../../guide/guide-dashboard-operationnel.md` (`Projet-311/guide/`, outside the repo)
- Modify: `docs/ARCHITECTURE.md` (new mart and exports in grain table, lineage), `README.md` (dashboard section: two screens)

- [ ] **Step 1:** Write the guide: for each dashboard, numbered steps (drag sheet X to position Y, set size, add parameter controls, filter action Map to Priority table "on select", colours, phone layout, publish), each with the expected result. Include the "stale records" caveat text and the population caveat verbatim.
- [ ] **Step 2:** Update docs; check README figures still match `monthly_kpis.csv`.
- [ ] **Step 3: Commit** `docs: operational dashboard sources and build notes`, push branch, open PR.

### Task 6: Owner build, then check

- [ ] **Step 1:** Owner builds the dashboards following the guide; Claude screenshots Tableau at owner checkpoints and points out issues.
- [ ] **Step 2:** Owner publishes; Claude fetches the static image and the fresh render, checks headline figures against `monthly_kpis.csv`.
- [ ] **Step 3:** Claude commits the owner's saved `.twb` to the branch.
