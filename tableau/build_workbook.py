"""Write the Tableau Public workbook (tableau/calgary_311.twb) from the export CSVs.

Usage:
    uv run python tableau/build_workbook.py [exports_dir]

The workbook reads data/processed/exports/*.csv (absolute path stored in the file, as
Tableau requires). Open it in Tableau Public, check it, then File > Save to Tableau Public.
One data source per question; the only relationship is the community map (see
docs/ARCHITECTURE.md, "Tableau model").
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "processed" / "exports"
OUT = ROOT / "tableau" / "calgary_311.twb"
# Tableau Public only saves workbooks whose sources are extracts, so each CSV is also loaded into a .hyper file.
EXTRACTS = EXPORTS.parent / "tableau"

DATES = {"month_end", "request_month", "day"}
INTS = {"open_requests", "requests", "closed_requests", "closed_within_benchmark",
        "closed_with_benchmark", "snow_requests", "main_requests", "second_requests", "diff"}

# id -> (caption, csv file)
SOURCES = {
    "cm": ("Timeliness (category_monthly)", "category_monthly.csv"),
    "bc": ("Backlog (backlog_category_monthly)", "backlog_category_monthly.csv"),
    "bcom": ("Backlog by community (backlog_community_monthly)", "backlog_community_monthly.csv"),
    "sn": ("Snow (daily_snow_requests)", "daily_snow_requests.csv"),
}

# Calculated fields per source: (internal name, caption, datatype, role, type, formula)
CALCS = {
    "cm": [
        ("Calculation_pct", "% within benchmark", "real", "measure", "quantitative",
         "SUM([closed_within_benchmark]) / SUM([closed_with_benchmark])"),
        ("Calculation_period", "Period", "string", "dimension", "nominal",
         # The two latest request months are left out: most of their requests are not closed yet.
         "IF [request_month] < #2025-01-01# THEN '2022-2024' "
         "ELSEIF [request_month] <= DATEADD('month', -2, {FIXED : MAX([request_month])}) THEN '2025 on' END"),
        ("Calculation_monthtotal", "Requests in month", "integer", "measure", "quantitative",
         "{FIXED [request_month] : SUM([requests])}"),
        ("Calculation_fullmonth", "Full month", "boolean", "dimension", "nominal",
         "[request_month] < {FIXED : MAX([request_month])}"),
    ],
    "bc": [
        ("Calculation_latest", "Latest month end", "boolean", "dimension", "nominal",
         "[month_end] = {FIXED : MAX([month_end])}"),
    ],
    "bcom": [
        ("Calculation_latest", "Latest month end", "boolean", "dimension", "nominal",
         "[month_end] = {FIXED : MAX([month_end])}"),
    ],
}


CAPTIONS = {"open_requests": "Open requests", "month_end": "Month end", "service_category": "Service category",
            "comm_name": "Community", "request_month": "Month", "snow_requests": "Snow requests",
            "snowfall_cm": "Snowfall (cm)", "day": "Day"}


def header(csv: Path) -> list[str]:
    return csv.read_text(encoding="utf-8").splitlines()[0].split(",")


def dtype(col: str) -> str:
    return "date" if col in DATES else "integer" if col in INTS else (
        "string" if col in {"service_category", "request_type", "age_band", "comm_code", "comm_name"} else "real")


def ds_name(sid: str) -> str:
    return f"federated.{sid}"


def datasource(sid: str) -> str:
    caption, fname = SOURCES[sid]
    cols = header(EXPORTS / fname)
    table = "[" + fname.replace(".", "#") + "]"
    rel_cols = "\n".join(
        f"            <column datatype='{dtype(c)}' name={quoteattr(c)} ordinal='{i}' />" for i, c in enumerate(cols))
    meta = []
    for c in cols:
        dt = dtype(c)
        role, typ = ("measure", "quantitative") if dt in {"integer", "real"} else ("dimension", "ordinal" if dt == "date" else "nominal")
        cap = f" caption={quoteattr(CAPTIONS[c])}" if c in CAPTIONS else ""
        meta.append(f"    <column{cap} datatype='{dt}' name='[{c}]' role='{role}' type='{typ}' />")
    for name, cap, dt, role, typ, formula in CALCS.get(sid, []):
        fmt = " default-format='p0%'" if name == "Calculation_pct" else ""
        meta.append(f"    <column caption={quoteattr(cap)}{fmt} datatype='{dt}' name='[{name}]' role='{role}' type='{typ}'>\n"
                    f"      <calculation class='tableau' formula={quoteattr(formula)} />\n    </column>")
    return f"""  <datasource caption={quoteattr(caption)} inline='true' name='{ds_name(sid)}' version='18.1'>
    <connection class='federated'>
      <named-connections>
        <named-connection caption={quoteattr(fname)} name='textscan.{sid}'>
          <connection class='textscan' directory={quoteattr(EXPORTS.as_posix())} filename={quoteattr(fname)} password='' server='' />
        </named-connection>
      </named-connections>
      <relation connection='textscan.{sid}' name={quoteattr(fname)} table='{table}' type='table'>
        <columns character-set='UTF-8' header='yes' locale='en_CA' separator=','>
{rel_cols}
        </columns>
      </relation>
    </connection>
{chr(10).join(meta)}
  <extract count='-1' enabled='true' units='records'>
    <connection access_mode='readonly' author-locale='en_US' class='hyper' dbname={quoteattr((EXTRACTS / f'{sid}.hyper').as_posix())} default-settings='hyper' schema='Extract' sslmode='' tablename='Extract' username='tableau'>
      <relation name='Extract' table='[Extract].[Extract]' type='table' />
    </connection>
  </extract>
  </datasource>"""


def inst(sid: str, col: str, deriv: str, kind: str) -> tuple[str, str]:
    """Column instance reference and its declaration. kind: nk/ok/qk."""
    prefix = {"None": "none", "Sum": "sum", "Avg": "avg", "Month-Trunc": "tmn", "Month": "mn", "Day-Trunc": "tdy"}[deriv]
    name = f"[{prefix}:{col}:{kind}]"
    typ = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}[kind]
    decl = f"<column-instance column='[{col}]' derivation='{deriv}' name='{name}' pivot='key' type='{typ}' />"
    return f"[{ds_name(sid)}].{name}", decl


def member_filter(sid: str, col: str, value: str) -> tuple[str, str, str]:
    ref, decl = inst(sid, col, "None", "nk")
    v = escape(value if value in {"true", "false"} else f'"{value}"', {"'": "&apos;"})
    f = (f"<filter class='categorical' column='{ref}'>\n"
         f"  <groupfilter function='member' level='{ref.rsplit('].', 1)[1]}' member='{v}' "
         "user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />\n</filter>")
    return ref, decl, f


def worksheet(name: str, sid: str, *, rows: str, cols: str, decls: list[str], filters: list[tuple[str, str, str]],
              mark: str, encodings: str = "", sorts: str = "", extra_filters: str = "", title: str | None = None) -> str:
    all_decls = list(dict.fromkeys(decls + [f[1] for f in filters]))
    filt = "\n".join(f[2] for f in filters) + extra_filters
    slices = "".join(f"<column>{f[0]}</column>" for f in filters)
    title_xml = (f"<layout-options><title><formatted-text><run>{escape(title)}</run></formatted-text></title></layout-options>"
                 if title else "")
    return f"""  <worksheet name={quoteattr(name)}>
    {title_xml}
    <table>
      <view>
        <datasources><datasource caption={quoteattr(SOURCES[sid][0])} name='{ds_name(sid)}' /></datasources>
        <datasource-dependencies datasource='{ds_name(sid)}'>
          {chr(10).join(all_decls)}
        </datasource-dependencies>
        {filt}
        {sorts}
        {f'<slices>{slices}</slices>' if slices else ''}
        <aggregation value='true' />
      </view>
      <style />
      <panes>
        <pane selection-relaxation-option='selection-relaxation-allow'>
          <view><breakdown value='auto' /></view>
          <mark class='{mark}' />
          {encodings}
        </pane>
      </panes>
      <rows>{rows}</rows>
      <cols>{cols}</cols>
    </table>
  </worksheet>"""


def calc_decl(sid: str, name: str) -> str:
    for n, cap, dt, role, typ, formula in CALCS[sid]:
        if n == name:
            fmt = " default-format='p0%'" if n == "Calculation_pct" else ""
            return (f"<column caption={quoteattr(cap)}{fmt} datatype='{dt}' name='[{n}]' role='{role}' type='{typ}'>"
                    f"<calculation class='tableau' formula={quoteattr(formula)} /></column>")
    raise KeyError(name)


def key_numbers() -> str:
    """Headline figures, computed from the exports at build time so the text matches the data."""
    import csv
    from collections import defaultdict

    rows = [r for r in csv.DictReader((EXPORTS / "backlog_category_monthly.csv").open(encoding="utf-8"))
            if r["request_type"] == "field" and r["age_band"] == "90+"]
    by_month, roads = defaultdict(int), defaultdict(int)
    for r in rows:
        by_month[r["month_end"]] += int(r["open_requests"])
        if r["service_category"] == "Roads & Mobility":
            roads[r["month_end"]] += int(r["open_requests"])
    latest = max(by_month)
    base = min(m for m in by_month if m[5:7] == latest[5:7])
    change = round((by_month[latest] / by_month[base] - 1) * 100)
    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

    def label(m: str) -> str:
        return f"{names[int(m[5:7]) - 1]} {m[:4]}"

    return (f"{by_month[latest]:,} field requests open 90+ days at the end of {label(latest)}, "
            f"{change:+d}% on {label(base)}. Roads & Mobility holds {round(roads[latest] / by_month[latest] * 100)}% of them.")


def build() -> str:
    sheets = []

    v, vd = inst("bc", "open_requests", "Sum", "qk")

    # 2. Old backlog trend
    m, md = inst("bc", "month_end", "Month-Trunc", "qk")
    sheets.append(worksheet(
        "Old backlog trend", "bc", rows=v, cols=m, decls=[vd, md],
        filters=[member_filter("bc", "request_type", "field"), member_filter("bc", "age_band", "90+")],
        mark="Line", title="Field requests open 90+ days reached their highest level since 2022"))

    # 3. Timeliness by service and period
    pct_d = "<column-instance column='[Calculation_pct]' derivation='User' name='[usr:Calculation_pct:qk]' pivot='key' type='quantitative' />"
    pct = f"[{ds_name('cm')}].[usr:Calculation_pct:qk]"
    cat, catd = inst("cm", "service_category", "None", "nk")
    per, perd = inst("cm", "Calculation_period", "None", "nk")
    sheets.append(worksheet(
        "Timeliness by service", "cm", rows=cat, cols=pct,
        decls=[calc_decl("cm", "Calculation_pct"), calc_decl("cm", "Calculation_period"), pct_d, catd, perd],
        filters=[member_filter("cm", "request_type", "field")],
        extra_filters=f"\n<filter class='categorical' column='{per}'><groupfilter function='except' user:ui-domain='database' user:ui-enumeration='exclusive' user:ui-marker='enumerate'><groupfilter function='level-members' level='[none:Calculation_period:nk]' /><groupfilter function='member' level='[none:Calculation_period:nk]' member='%null%' /></groupfilter></filter>",
        sorts=f"<sort class='computed' column='{cat}' direction='ASC' using='{pct}' />",
        mark="Circle", encodings=f"<encodings><color column='{per}' /></encodings>",
        title="Closed within own benchmark: only Fire fell (blue 2022-2024, orange 2025 on)"))

    # 4. Old backlog by service, latest month end
    bcat, bcatd = inst("bc", "service_category", "None", "nk")
    sheets.append(worksheet(
        "Old backlog by service", "bc", rows=bcat, cols=v, decls=[vd, bcatd, calc_decl("bc", "Calculation_latest")],
        filters=[member_filter("bc", "request_type", "field"), member_filter("bc", "age_band", "90+"),
                 member_filter("bc", "Calculation_latest", "true")],
        sorts=f"<sort class='computed' column='{bcat}' direction='DESC' using='{v}' />",
        mark="Bar", title="Roads & Mobility holds most of the old work"))

    # 5. Top communities, latest month end
    cv, cvd = inst("bcom", "open_requests", "Sum", "qk")
    cn, cnd = inst("bcom", "comm_name", "None", "nk")
    top = (f"\n<filter class='categorical' column='{cn}'><groupfilter count='12' end='top' function='end' units='records' "
           "user:ui-marker='end' user:ui-top-by-field='true'><groupfilter direction='DESC' expression='SUM([open_requests])' "
           f"function='order' user:ui-marker='order'><groupfilter function='level-members' level='[none:comm_name:nk]' "
           "user:ui-enumeration='all' user:ui-marker='enumerate' /></groupfilter></groupfilter></filter>")
    sheets.append(worksheet(
        "Top communities", "bcom", rows=cn, cols=cv, decls=[cvd, cnd, calc_decl("bcom", "Calculation_latest"), inst("bcom", "comm_code", "None", "nk")[1]],
        filters=[member_filter("bcom", "age_band", "90+"), member_filter("bcom", "Calculation_latest", "true")],
        extra_filters=top + (f"\n<filter class='categorical' column='[{ds_name('bcom')}].[none:comm_code:nk]'><groupfilter function='except' "
                             "user:ui-domain='database' user:ui-enumeration='exclusive' user:ui-marker='enumerate'>"
                             "<groupfilter function='level-members' level='[none:comm_code:nk]' />"
                             "<groupfilter function='member' level='[none:comm_code:nk]' member='&quot;N/A&quot;' /></groupfilter></filter>"),
        sorts=f"<sort class='computed' column='{cn}' direction='DESC' using='{cv}' />",
        mark="Bar", title="Top 12 communities by field requests open 90+ days"))

    # 6. Seasonality: average requests per calendar month (full months only)
    mo, mod = inst("cm", "request_month", "Month", "ok")
    avg = f"[{ds_name('cm')}].[avg:Calculation_monthtotal:qk]"
    avg_d = "<column-instance column='[Calculation_monthtotal]' derivation='Avg' name='[avg:Calculation_monthtotal:qk]' pivot='key' type='quantitative' />"
    sheets.append(worksheet(
        "Seasonality", "cm", rows=avg, cols=mo,
        decls=[calc_decl("cm", "Calculation_monthtotal"), calc_decl("cm", "Calculation_fullmonth"), avg_d, mod],
        filters=[member_filter("cm", "Calculation_fullmonth", "true")],
        mark="Bar", title="Average requests per calendar month: June peaks, February and December are lowest"))

    # 7. Snow: daily snow requests and snowfall, winter 2025-2026
    d, dd = inst("sn", "day", "Day-Trunc", "qk")
    sr, srd = inst("sn", "snow_requests", "Sum", "qk")
    sf, sfd = inst("sn", "snowfall_cm", "Sum", "qk")
    win = (f"\n<filter class='quantitative' column='{d}' included-values='in-range'>"
           "<min>#2025-10-01#</min><max>#2026-04-30#</max></filter>")
    sheets.append(worksheet(
        "Snow and requests", "sn", rows=f"({sr} / {sf})", cols=d, decls=[srd, sfd, dd], filters=[],
        extra_filters=win, mark="Bar",
        title="Winter 2025-2026: snow requests (top) follow snowfall (bottom) by one to three days"))

    names = ["Old backlog trend", "Timeliness by service", "Old backlog by service",
             "Top communities", "Seasonality", "Snow and requests"]

    # Dashboard: title, headline, then a 2 x 3 grid. Coordinates are in 1/100000 of the canvas.
    title = ("Calgary 311 Service Performance. Field crews close new requests as fast as before, except Fire. "
             "Old work is the problem: requests open 90+ days are at their highest level since 2022.")
    note = ("Source: City of Calgary Open Data (311 Service Requests iahh-g8bj, Community District Boundaries surr-xmvs) "
            "and ECCC daily climate data, CALGARY INTL A. Benchmark: each service's own 80th percentile time to close in "
            "2022-2024. 'Closed' means closed in the system, not fixed. Snapshot 2026-11-19.")
    grid = [("Old backlog trend", 0, 0), ("Timeliness by service", 1, 0), ("Old backlog by service", 0, 1),
            ("Top communities", 1, 1), ("Seasonality", 0, 2), ("Snow and requests", 1, 2)]
    zones = [f"<zone h='7000' id='2' type-v2='text' w='100000' x='0' y='0'><formatted-text>"
             f"<run bold='true' fontsize='14'>{escape(title)}</run><run>&#10;</run>"
             f"<run fontsize='12'>{escape(key_numbers())}</run></formatted-text></zone>"]
    zid = 4
    for name, cx, cy in grid:
        zones.append(f"<zone h='29000' id='{zid}' name={quoteattr(name)} w='50000' x='{cx * 50000}' y='{7000 + cy * 29000}' />")
        zid += 1
    zones.append(f"<zone h='6000' id='{zid}' type-v2='text' w='100000' x='0' y='94000'><formatted-text>"
                 f"<run fontsize='8'>{escape(note)}</run></formatted-text></zone>")
    dashboard = f"""  <dashboard name='Calgary 311 Service Performance'>
    <style />
    <size maxheight='1400' maxwidth='1300' minheight='1400' minwidth='1300' sizing-mode='fixed' />
    <zones>
      <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
        {chr(10).join(zones)}
      </zone>
    </zones>
  </dashboard>"""

    cards = ("<cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' />"
             "</strip></edge><edge name='top'><strip size='2147483647'><card type='columns' /></strip>"
             "<strip size='2147483647'><card type='rows' /></strip><strip size='31'><card type='title' /></strip></edge></cards>")
    windows = "\n".join(f"    <window class='worksheet' name={quoteattr(n)}>{cards}</window>" for n in names)

    return f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook original-version='18.1' source-build='2026.3.0' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences />
  <datasources>
{chr(10).join(datasource(s) for s in SOURCES)}
  </datasources>
  <worksheets>
{chr(10).join(sheets)}
  </worksheets>
  <dashboards>
{dashboard}
  </dashboards>
  <windows source-height='30'>
{windows}
  </windows>
</workbook>
"""


def build_extracts() -> None:
    """Load each CSV into <sid>.hyper, table "Extract"."Extract", the layout Tableau expects."""
    from tableauhyperapi import Connection, CreateMode, HyperProcess, SqlType, TableDefinition, TableName, Telemetry

    sql = {"date": SqlType.date(), "integer": SqlType.big_int(), "real": SqlType.double(), "string": SqlType.text()}
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        for sid, (_, fname) in SOURCES.items():
            csv = EXPORTS / fname
            table = TableDefinition(TableName("Extract", "Extract"),
                                    [TableDefinition.Column(c, sql[dtype(c)]) for c in header(csv)])
            with Connection(hyper.endpoint, EXTRACTS / f"{sid}.hyper", CreateMode.CREATE_AND_REPLACE) as con:
                con.catalog.create_schema("Extract")
                con.catalog.create_table(table)
                path = csv.as_posix().replace("'", "''")
                n = con.execute_command(f"COPY {table.table_name} FROM '{path}' WITH (format csv, header)")
                rows = sum(1 for _ in csv.open(encoding="utf-8")) - 1
                assert n == rows, f"{fname}: {n} rows loaded, {rows} in the CSV"  # self-check: nothing dropped
                print(f"{sid}.hyper: {n:,} rows")


if __name__ == "__main__":
    build_extracts()
    xml = build()
    OUT.write_text(xml, encoding="utf-8")
    import xml.dom.minidom as md  # self-check: the file must at least be well-formed XML
    md.parseString(xml.encode("utf-8"))
    print(f"Wrote {OUT}")
