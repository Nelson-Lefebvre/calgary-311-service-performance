"""Checks on the dbt marts and CSV exports that feed Tableau. Skipped when the local database is absent."""

from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "calgary311.duckdb"
EXPORTS = ROOT / "data" / "processed" / "exports"

pytestmark = pytest.mark.skipif(not DB.exists(), reason="local database not built")


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(DB), read_only=True)
    yield c
    c.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def csv(name):
    return f"'{(EXPORTS / name).as_posix()}'"


def test_service_mart_reconciles_with_backlog(con):
    diff = one(con, """
        select count(*) from (
            select month_end, service_category, request_type, age_band, sum(open_requests) as n
            from fct_backlog_service_monthly group by all
        ) as a
        full join (
            select month_end, service_category, request_type, age_band, sum(open_requests) as n
            from fct_backlog_monthly
            where month_end >= (select min(month_end) from fct_backlog_service_monthly)
            group by all
        ) as b using (month_end, service_category, request_type, age_band)
        where coalesce(a.n, 0) <> coalesce(b.n, 0)""")
    assert diff == 0


def test_trend_keeps_rows_that_appear_or_disappear(con):
    assert one(con, "select count(*) from fct_backlog_service_monthly where open_requests = 0 and open_3m_earlier > 0") > 0
    assert one(con, "select count(*) from fct_backlog_service_monthly where open_3m_earlier is null") == 0


def test_population_never_zero(con):
    assert one(con, "select count(*) from fct_backlog_service_monthly where population_2019 = 0") == 0


def test_service_export_has_13_month_ends(con):
    assert one(con, f"select count(distinct month_end) from {csv('backlog_service_community_monthly.csv')}") == 13


def test_kpis_latest_backlog_matches_readme(con):
    r = con.execute(f"""select open_90_plus, round(roads_share_of_90_plus * 100)
                        from {csv('monthly_kpis.csv')} where month = date '2026-10-01'""").fetchone()
    assert r == (34661, 77)


def test_kpis_first_year_has_null_prior_year(con):
    assert one(con, f"select count(*) from {csv('monthly_kpis.csv')} where year(month) = 2022 and requests_ly is not null") == 0


def test_kpis_two_latest_months_incomplete(con):
    assert one(con, f"select list(is_complete order by month desc)[1:3] from {csv('monthly_kpis.csv')}") == [False, False, True]


def test_kpis_one_row_per_month(con):
    assert one(con, f"select count(*) - count(distinct month) from {csv('monthly_kpis.csv')}") == 0
