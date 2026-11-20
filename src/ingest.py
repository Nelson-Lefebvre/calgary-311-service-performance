"""Download a dated snapshot of every source into data/raw/<snapshot>/.

Usage:
    uv run python -m src.ingest                      # snapshot = today
    uv run python -m src.ingest --snapshot 2026-12-01

The snapshot date is an exclusive upper bound on requested_date, so a snapshot
taken on the same day always returns the same rows for past months.
"""

from __future__ import annotations

import argparse
import io
import json
import time
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import requests

ROOT = Path(__file__).resolve().parents[1]
SODA = "https://data.calgary.ca/resource"
ECCC = "https://api.weather.gc.ca/collections/climate-daily/items"
START = date(2022, 1, 1)

REQUESTS_ID = "iahh-g8bj"  # 311 Service Requests (full history)
SECOND_EXTRACT_ID = "arf6-qysm"  # separate table, 2024+, capped at 1M rows
COMMUNITIES_ID = "ab7m-fwn6"  # community boundaries
POPULATION_ID = "jtpc-xgsh"  # community populations, last census 2019
WEATHER_STATION = "3031092"  # CALGARY INTL A, daily since 2012-07-12

REQUEST_COLUMNS = [
    "service_request_id",
    "requested_date",
    "updated_date",
    "closed_date",
    "status_description",
    "source",
    "service_name",
    "agency_responsible",
    "comm_code",
    "comm_name",
    "location_type",
]

session = requests.Session()
session.headers["User-Agent"] = "calgary-311-service-performance (portfolio project)"


def get(url: str, params: dict | None = None, retries: int = 4) -> requests.Response:
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=180)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt * 5)
    raise RuntimeError("unreachable")


def month_starts(start: date, end: date) -> list[date]:
    months, d = [], start.replace(day=1)
    while d < end:
        months.append(d)
        d = date(d.year + d.month // 12, d.month % 12 + 1, 1)
    return months


def soda_count(dataset: str, where: str) -> int:
    r = get(f"{SODA}/{dataset}.json", {"$select": "count(*) AS n", "$where": where})
    return int(r.json()[0]["n"])


def soda_csv(dataset: str, where: str, columns: list[str], expected: int) -> pl.DataFrame:
    """Download all rows matching `where`, paging by 50k, ordered by id."""
    frames, offset, page = [], 0, 50_000
    while offset < expected:
        r = get(
            f"{SODA}/{dataset}.csv",
            {
                "$select": ",".join(columns),
                "$where": where,
                "$order": "service_request_id",
                "$limit": page,
                "$offset": offset,
            },
        )
        frames.append(pl.read_csv(io.BytesIO(r.content), infer_schema=False))
        offset += page
    df = pl.concat(frames) if frames else pl.DataFrame(schema={c: pl.String for c in columns})
    # Trust boundary: a short or duplicated page means a broken download, not a fact about the city.
    if df.height != expected or df["service_request_id"].n_unique() != expected:
        raise ValueError(
            f"{dataset} {where}: expected {expected} unique rows, got {df.height} "
            f"({df['service_request_id'].n_unique()} unique)"
        )
    return df


def ingest_requests(dataset: str, start: date, end: date, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for m in month_starts(start, end):
        nxt = month_starts(m, date(m.year + 1, m.month, 1))[1]
        upper = min(nxt, end)
        where = f"requested_date >= '{m}' AND requested_date < '{upper}'"
        n = soda_count(dataset, where)
        df = soda_csv(dataset, where, REQUEST_COLUMNS, n)
        df.write_parquet(out / f"{m:%Y-%m}.parquet")
        counts[f"{m:%Y-%m}"] = n
        print(f"  {dataset} {m:%Y-%m}: {n:,} rows")
    return counts


def ingest_carryover(out: Path) -> int:
    """Requests made before START that were still open on START: the backlog needs them."""
    where = f"requested_date < '{START}' AND (closed_date IS NULL OR closed_date >= '{START}')"
    df = soda_csv(REQUESTS_ID, where, REQUEST_COLUMNS, soda_count(REQUESTS_ID, where))
    df.write_parquet(out / "carryover.parquet")
    print(f"  carryover: {df.height:,} rows")
    return df.height


def ingest_weather(start: date, end: date, out: Path) -> int:
    rows, offset = [], 0
    while True:
        r = get(
            ECCC,
            {
                "f": "json",
                "CLIMATE_IDENTIFIER": WEATHER_STATION,
                "datetime": f"{start}/{end}",
                "properties": "LOCAL_DATE,MIN_TEMPERATURE,MAX_TEMPERATURE,MEAN_TEMPERATURE,"
                "TOTAL_SNOW,SNOW_ON_GROUND,TOTAL_PRECIPITATION",
                "sortby": "LOCAL_DATE",
                "limit": 5000,
                "offset": offset,
            },
        )
        feats = r.json().get("features", [])
        rows += [f["properties"] for f in feats]
        if len(feats) < 5000:
            break
        offset += 5000
    df = pl.DataFrame(rows, infer_schema_length=None)
    df = df.filter(pl.col("LOCAL_DATE").str.slice(0, 10) < str(end))
    df.write_parquet(out / "weather_daily.parquet")
    return df.height


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    snap: date = args.snapshot

    out = ROOT / "data" / "raw" / f"snapshot={snap}"
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "snapshot": str(snap),
        "period": [str(START), str(snap)],
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    print("311 requests (iahh-g8bj)")
    manifest["requests"] = ingest_requests(REQUESTS_ID, START, snap, out / "requests")

    print("Carryover: pre-2022 requests still open on 2022-01-01")
    manifest["carryover"] = ingest_carryover(out)

    print("Second extract (arf6-qysm)")
    manifest["second_extract"] = ingest_requests(
        SECOND_EXTRACT_ID, date(2024, 1, 1), snap, out / "second_extract"
    )

    print("Community boundaries and population")
    (out / "communities.geojson").write_bytes(
        get(f"{SODA}/{COMMUNITIES_ID}.geojson", {"$limit": 5000}).content
    )
    pop = pl.read_csv(
        io.BytesIO(get(f"{SODA}/{POPULATION_ID}.csv", {"$limit": 50000}).content),
        infer_schema=False,
    )
    pop.write_parquet(out / "community_population.parquet")
    manifest["population_rows"] = pop.height

    print("Weather (ECCC)")
    manifest["weather_days"] = ingest_weather(START, snap, out)

    manifest["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Done: {out}")


if __name__ == "__main__":
    main()
