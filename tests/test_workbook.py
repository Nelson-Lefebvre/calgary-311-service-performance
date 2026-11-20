"""Build the workbook into a temp folder and check its parameters, sources and extracts."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "data" / "processed" / "exports"
sys.path.insert(0, str(ROOT / "tableau"))

pytestmark = pytest.mark.skipif(not (EXPORTS / "monthly_kpis.csv").exists(), reason="exports not built")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    import build_workbook

    tmp = tmp_path_factory.mktemp("wb")
    counts = build_workbook.run(EXPORTS, tmp / "wb.twb", tmp / "extracts")
    return ET.parse(tmp / "wb.twb").getroot(), counts


def params(root):
    return {c.get("caption"): c for c in root.iter("column") if c.get("param-domain-type")}


def test_parameters_and_defaults(built):
    p = params(built[0])
    assert set(p) == {"Category", "Age band", "Request type", "Month end", "Per 1,000 residents"}
    assert p["Age band"].get("value") == '"90+"'
    assert p["Request type"].get("value") == '"field"'
    assert p["Category"].get("value") == '"All"'
    assert p["Per 1,000 residents"].get("value") == "false"


def test_month_end_default_is_latest_in_data(built):
    import duckdb

    latest = duckdb.execute(
        f"select max(month_end) from '{(EXPORTS / 'backlog_service_community_monthly.csv').as_posix()}'"
    ).fetchone()[0]
    m = params(built[0])["Month end"]
    assert m.get("value") == f"#{latest}#"
    assert len(m.findall("./members/member")) == 13


def test_category_list_has_all_first(built):
    members = [x.get("value") for x in params(built[0])["Category"].findall("./members/member")]
    assert members[0] == '"All"' and '"Roads & Mobility"' in members


def test_sources(built):
    captions = {d.get("caption") for d in built[0].find("datasources") if d.get("name") != "Parameters"}
    assert captions == {"Operations backlog", "Monthly KPIs", "Timeliness", "Snow"}


def test_every_extract_row_count_matches_csv(built):
    for sid, (hyper_rows, csv_rows) in built[1].items():
        assert hyper_rows == csv_rows, sid


def test_sheets_and_dashboards(built):
    root = built[0]
    sheets = {w.get("name") for w in root.iter("worksheet")}
    assert sheets == {"P2 Priority table", "P3 Trend 3 months", "P4 Stock headline", "P5 Communities",
                      "M1 Flow headline", "M2 Stock trend", "M3 Benchmark trend", "M4 Slipping services",
                      "M5 Seasonality", "M6 Snow"}
    assert {d.get("name") for d in root.iter("dashboard")} == {"Priorities", "Monthly situation"}


def test_priorities_shows_caveats(built):
    texts = " ".join(r.text or "" for d in built[0].iter("dashboard") if d.get("name") == "Priorities"
                     for r in d.iter("run"))
    assert "never closed in the system" in texts and "2019 municipal census" in texts
