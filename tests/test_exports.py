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
