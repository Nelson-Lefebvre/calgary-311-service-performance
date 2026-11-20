"""Export aggregated tables for Tableau Public (which reads files, not databases).

Usage:
    uv run python -m src.export

Writes data/processed/exports/*.csv and copies the community boundaries GeoJSON.
Field (operations) requests are the default focus; information requests stay available
through the request_type column.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "calgary311.duckdb"
OUT = ROOT / "data" / "processed" / "exports"

QUERIES = {
    # Timeliness: one row per category x month, recomputed from counts.
    "category_monthly": """
        select * from fct_category_monthly order by service_category, request_month
    """,
    # Backlog by community for the map: field work only, summed over categories.
    "backlog_community_monthly": """
        select month_end, comm_code, comm_name, age_band, sum(open_requests) as open_requests
        from fct_backlog_monthly
        where request_type = 'field'
        group by all
        order by month_end, comm_code, age_band
    """,
    # Backlog trend by category and age band (all request types, filter in Tableau).
    "backlog_category_monthly": """
        select month_end, service_category, request_type, age_band,
               sum(open_requests) as open_requests
        from fct_backlog_monthly
        group by all
        order by month_end, service_category, age_band
    """,
    # Seasonality and weather: snow-related requests per day with snowfall.
    "daily_snow_requests": """
        with snow as (
            select requested_date as request_date, count(*) as snow_requests
            from fct_service_request
            where service_name ilike '%snow%'
            group by 1
        )
        select w.weather_date as day, coalesce(s.snow_requests, 0) as snow_requests,
               w.snowfall_cm, w.snow_on_ground_cm, w.min_temp_c
        from stg_weather_daily as w
        left join snow as s on s.request_date = w.weather_date
        order by day
    """,
    # Operational view: service name x community x age band, last 13 month ends, with 3-month trend.
    "backlog_service_community_monthly": """
        select * from fct_backlog_service_monthly
        order by month_end, comm_code, service_name, age_band
    """,
    # Monthly situation: field requests, one row per request month, with the same month a year earlier.
    # The two latest request months are incomplete (current partial month, and most requests of the
    # month before not yet closed), so is_complete is false for them.
    "monthly_kpis": """
        with timeliness as (
            select request_month as month, sum(requests) as requests,
                   sum(closed_within_benchmark) / sum(closed_with_benchmark) as within_benchmark_share
            from fct_category_monthly
            where request_type = 'field'
            group by all
        ),
        backlog as (
            select month_end, sum(open_requests) as open_90_plus,
                   sum(open_requests) filter (where service_category = 'Roads & Mobility')
                       / sum(open_requests) as roads_share_of_90_plus
            from fct_backlog_monthly
            where request_type = 'field' and age_band = '90+'
            group by all
        ),
        kpis as (
            select t.month, t.requests, t.within_benchmark_share, b.open_90_plus, b.roads_share_of_90_plus,
                   t.month < (select max(month) from timeliness) - interval 1 month as is_complete
            from timeliness as t
            left join backlog as b on b.month_end = last_day(t.month)
        )
        select k.*,
               ly.requests as requests_ly,
               ly.within_benchmark_share as within_benchmark_share_ly,
               ly.open_90_plus as open_90_plus_ly,
               ly.roads_share_of_90_plus as roads_share_of_90_plus_ly
        from kpis as k
        left join kpis as ly on ly.month = k.month - interval 12 month
        order by k.month
    """,
    "reconciliation_monthly": "select * from reconciliation_monthly",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)
    # Staging views use paths relative to dbt/, so resolve them from there.
    con.execute(f"set file_search_path = '{(ROOT / 'dbt').as_posix()}'")
    counts = {}
    for name, sql in QUERIES.items():
        path = OUT / f"{name}.csv"
        con.execute(f"copy ({sql}) to '{path.as_posix()}' (header)")
        counts[name] = con.execute(f"select count(*) from ({sql})").fetchall()[0][0]
        print(f"{name}: {counts[name]:,} rows")

    snapshot = con.execute("select max(requested_date) from fct_service_request").fetchall()[0][0]
    raw = sorted((ROOT / "data" / "raw").glob("snapshot=*"))[-1]
    shutil.copy(raw / "communities.geojson", OUT / "communities.geojson")
    (OUT / "manifest.json").write_text(
        json.dumps({"latest_request_date": str(snapshot), "rows": counts}, indent=2)
    )


if __name__ == "__main__":
    main()
