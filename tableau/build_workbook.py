"""Write the Tableau Public workbook skeleton (tableau/calgary_311.twb) from the export CSVs.

Usage:
    uv run python tableau/build_workbook.py [exports_dir] [extracts_dir]

What this script owns: data sources (as Hyper extracts, which Tableau Public requires), the shared
parameters, calculated fields, captions and formats, and one sheet per visual. What it does not own:
dashboard layout, formatting and actions, which are built by hand in Tableau Public following
guide/guide-dashboard-operationnel.md (outside the repo). See docs/ARCHITECTURE.md, "Tableau model".

The sources are separate files at different grains, so a normal Tableau filter only acts on one of
them. The shared filters are parameters instead: each source has a calculated field that compares
its rows with the parameters, and every sheet keeps the rows where that field is true.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[1]

DATES = {"month_end", "request_month", "day", "month"}
BOOLS = {"is_complete"}
STRINGS = {"service_category", "request_type", "age_band", "comm_code", "comm_name", "service_name"}
INTS = {"open_requests", "open_3m_earlier", "population_2019", "requests", "closed_requests",
        "closed_within_benchmark", "closed_with_benchmark", "snow_requests", "open_90_plus",
        "requests_ly", "open_90_plus_ly"}

# id -> (caption, csv file)
SOURCES = {
    "svc": ("Operations backlog", "backlog_service_community_monthly.csv"),
    "kpi": ("Monthly KPIs", "monthly_kpis.csv"),
    "cm": ("Timeliness", "category_monthly.csv"),
    "sn": ("Snow", "daily_snow_requests.csv"),
}

CAPTIONS = {
    "month_end": "Month end", "request_type": "Request type", "service_category": "Service category",
    "service_name": "Request type (detail)", "comm_code": "Community code", "comm_name": "Community",
    "age_band": "Days open", "open_requests": "Open requests", "open_3m_earlier": "Open requests 3 months earlier",
    "population_2019": "Population (2019)", "month": "Month", "requests": "Requests",
    "within_benchmark_share": "Closed within benchmark", "open_90_plus": "Open 90+ days",
    "roads_share_of_90_plus": "Roads & Mobility share of 90+", "is_complete": "Complete month",
    "requests_ly": "Requests, year before", "within_benchmark_share_ly": "Closed within benchmark, year before",
    "open_90_plus_ly": "Open 90+ days, year before", "roads_share_of_90_plus_ly": "Roads & Mobility share, year before",
    "request_month": "Month", "snow_requests": "Snow requests", "snowfall_cm": "Snowfall (cm)", "day": "Day",
    "closed_requests": "Closed requests", "closed_with_benchmark": "Closed (with benchmark)",
    "closed_within_benchmark": "Closed within benchmark (count)", "median_days_to_close": "Median days to close",
    "p90_days_to_close": "P90 days to close", "pct_within_benchmark": "Within benchmark (row ratio, do not average)",
    "pct_within_benchmark_p90": "Within P90 benchmark (row ratio, do not average)", "snow_on_ground_cm": "Snow on ground (cm)",
    "min_temp_c": "Minimum temperature (C)",
}
PERCENT = {"within_benchmark_share", "roads_share_of_90_plus", "within_benchmark_share_ly",
           "roads_share_of_90_plus_ly", "pct_within_benchmark", "pct_within_benchmark_p90"}

# Parameters: internal name -> (caption, datatype). Values are filled from the data in parameters().
P_CATEGORY, P_AGE, P_TYPE, P_MONTH, P_PERCAP = (f"[Parameters].[Parameter {i}]" for i in range(1, 6))

# Calculated fields per source: (internal name, caption, datatype, role, type, formula, format)
CATEGORY_RULE = f"({P_CATEGORY} = 'All' OR [service_category] = {P_CATEGORY})"
CALCS = {
    "svc": [
        ("Calculation_keep", "Keep row", "boolean", "dimension", "nominal",
         f"{CATEGORY_RULE} AND [age_band] = {P_AGE} AND [request_type] = {P_TYPE} AND [month_end] = {P_MONTH}", ""),
        # MIN, not SUM: population repeats on every row of a community. Rate is meaningful per community only.
        ("Calculation_open", "Open (count or per 1,000)", "real", "measure", "quantitative",
         f"IF {P_PERCAP} THEN SUM([open_requests]) / MIN([population_2019]) * 1000 ELSE SUM([open_requests]) END", "n#,##0.#"),
        ("Calculation_keep_allages", "Keep row (all days open)", "boolean", "dimension", "nominal",
         f"{CATEGORY_RULE} AND [request_type] = {P_TYPE} AND [month_end] = {P_MONTH}", ""),
        ("Calculation_pair", "Community and request type", "string", "dimension", "nominal",
         "[comm_name] + ' - ' + [service_name]", ""),
        ("Calculation_selected_band", "Open in selected days-open band", "integer", "measure", "quantitative",
         f"SUM(IF [age_band] = {P_AGE} THEN [open_requests] END)", "n#,##0"),
        ("Calculation_change", "Change vs 3 months earlier", "integer", "measure", "quantitative",
         "SUM([open_requests]) - SUM([open_3m_earlier])", "n+#,##0;-#,##0;0"),
        ("Calculation_change_pct", "Change vs 3 months earlier (%)", "real", "measure", "quantitative",
         "IF SUM([open_3m_earlier]) > 0 THEN (SUM([open_requests]) - SUM([open_3m_earlier])) / SUM([open_3m_earlier]) END",
         "p+0%;-0%;0%"),
    ],
    "cm": [
        ("Calculation_keep", "Keep row", "boolean", "dimension", "nominal",
         f"{CATEGORY_RULE} AND [request_type] = {P_TYPE}", ""),
        ("Calculation_pct", "% within benchmark", "real", "measure", "quantitative",
         "SUM([closed_within_benchmark]) / SUM([closed_with_benchmark])", "p0%"),
        ("Calculation_period", "Period", "string", "dimension", "nominal",
         # The two latest request months are left out: most of their requests are not closed yet.
         "IF [request_month] < #2025-01-01# THEN '2022-2024' "
         "ELSEIF [request_month] <= DATEADD('month', -2, {FIXED : MAX([request_month])}) THEN '2025 on' END", ""),
        ("Calculation_monthtotal", "Requests in month", "integer", "measure", "quantitative",
         "{FIXED [request_month] : SUM([requests])}", "n#,##0"),
        ("Calculation_fullmonth", "Full month", "boolean", "dimension", "nominal",
         "[request_month] < {FIXED : MAX([request_month])}", ""),
    ],
    "kpi": [
        ("Calculation_latest_complete", "Latest complete month", "boolean", "dimension", "nominal",
         "[month] = {FIXED : MAX(IF [is_complete] THEN [month] END)}", ""),
        ("Calculation_latest_stock", "Latest month end", "boolean", "dimension", "nominal",
         "[month] = {FIXED : MAX(IF NOT ISNULL([open_90_plus]) THEN [month] END)}", ""),
        ("Calculation_requests_yoy", "Requests vs year before", "real", "measure", "quantitative",
         "SUM([requests]) / SUM([requests_ly]) - 1", "p+0%;-0%;0%"),
        ("Calculation_share_yoy", "Benchmark share vs year before (points)", "real", "measure", "quantitative",
         "(SUM([within_benchmark_share]) - SUM([within_benchmark_share_ly])) * 100", "n+0.0;-0.0;0"),
        ("Calculation_stock_yoy", "Open 90+ vs year before", "real", "measure", "quantitative",
         "SUM([open_90_plus]) / SUM([open_90_plus_ly]) - 1", "p+0%;-0%;0%"),
        ("Calculation_share_shown", "Closed within benchmark (complete months)", "real", "measure", "quantitative",
         "IF ATTR([is_complete]) THEN SUM([within_benchmark_share]) END", "p0%"),
    ],
}


def header(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()[0].split(",")


def dtype(col: str) -> str:
    if col in DATES:
        return "date"
    if col in BOOLS:
        return "boolean"
    if col in STRINGS:
        return "string"
    return "integer" if col in INTS else "real"


def ds_name(sid: str) -> str:
    return f"federated.{sid}"


def column_values(exports: Path, fname: str, col: str) -> list[str]:
    with (exports / fname).open(encoding="utf-8") as f:
        return sorted({r[col] for r in csv.DictReader(f)})


def parameters(exports: Path) -> str:
    """Parameter lists come from the data, so the defaults move with each monthly refresh."""
    months = column_values(exports, SOURCES["svc"][1], "month_end")
    categories = ["All"] + column_values(exports, SOURCES["cm"][1], "service_category")
    q = lambda v: f'"{v}"'  # noqa: E731  Tableau string literal
    specs = [
        ("Category", "string", q("All"), [q(c) for c in categories]),
        ("Age band", "string", q("90+"), [q(a) for a in ("0-7", "8-30", "31-90", "90+")]),
        ("Request type", "string", q("field"), [q("field"), q("information")]),
        ("Month end", "date", f"#{months[-1]}#", [f"#{m}#" for m in months]),
        ("Per 1,000 residents", "boolean", "false", ["false", "true"]),
    ]
    cols = []
    for i, (cap, dt, default, members) in enumerate(specs, start=1):
        mem = "".join(f"<member value={quoteattr(m)} />" for m in members)
        cols.append(f"    <column caption={quoteattr(cap)} datatype='{dt}' name='[Parameter {i}]' param-domain-type='list' "
                    f"role='measure' type='nominal' value={quoteattr(default)}>\n"
                    f"      <calculation class='tableau' formula={quoteattr(default)} />\n"
                    f"      <members>{mem}</members>\n    </column>")
    return ("  <datasource hasconnection='false' inline='true' name='Parameters' version='18.1'>\n"
            "    <aliases enabled='yes' />\n" + "\n".join(cols) + "\n  </datasource>")


def calc_column(sid: str, name: str) -> str:
    for n, cap, dt, role, typ, formula, fmt in CALCS[sid]:
        if n == name:
            f = f" default-format={quoteattr(fmt)}" if fmt else ""
            return (f"<column caption={quoteattr(cap)}{f} datatype='{dt}' name='[{n}]' role='{role}' type='{typ}'>"
                    f"<calculation class='tableau' formula={quoteattr(formula)} /></column>")
    raise KeyError(name)


def datasource(sid: str, exports: Path, extracts: Path) -> str:
    caption, fname = SOURCES[sid]
    cols = header(exports / fname)
    table = "[" + fname.replace(".", "#") + "]"
    rel_cols = "\n".join(
        f"            <column datatype='{dtype(c)}' name={quoteattr(c)} ordinal='{i}' />" for i, c in enumerate(cols))
    meta = []
    for c in cols:
        dt = dtype(c)
        role, typ = ("measure", "quantitative") if dt in {"integer", "real"} else ("dimension", "ordinal" if dt == "date" else "nominal")
        cap = f" caption={quoteattr(CAPTIONS[c])}" if c in CAPTIONS else ""
        fmt = " default-format='p0%'" if c in PERCENT else (" default-format='n#,##0'" if dt == "integer" else "")
        meta.append(f"    <column{cap}{fmt} datatype='{dt}' name='[{c}]' role='{role}' type='{typ}' />")
    meta += [f"    {calc_column(sid, c[0])}" for c in CALCS.get(sid, [])]
    return f"""  <datasource caption={quoteattr(caption)} inline='true' name='{ds_name(sid)}' version='18.1'>
    <connection class='federated'>
      <named-connections>
        <named-connection caption={quoteattr(fname)} name='textscan.{sid}'>
          <connection class='textscan' directory={quoteattr(exports.as_posix())} filename={quoteattr(fname)} password='' server='' />
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
    <connection access_mode='readonly' author-locale='en_US' class='hyper' dbname={quoteattr((extracts / f'{sid}.hyper').as_posix())} default-settings='hyper' schema='Extract' sslmode='' tablename='Extract' username='tableau'>
      <relation name='Extract' table='[Extract].[Extract]' type='table' />
    </connection>
  </extract>
  </datasource>"""


def inst(sid: str, col: str, deriv: str, kind: str) -> tuple[str, str]:
    """Column instance reference and its declaration. kind: nk/ok/qk."""
    prefix = {"None": "none", "Sum": "sum", "Avg": "avg", "User": "usr", "Month-Trunc": "tmn", "Month": "mn",
              "Day-Trunc": "tdy"}[deriv]
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
        <datasources><datasource caption={quoteattr(SOURCES[sid][0])} name='{ds_name(sid)}' /><datasource name='Parameters' /></datasources>
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


def cinst(sid: str, calc: str) -> tuple[str, list[str]]:
    """Reference and declarations for a calculated field: dimension (None) or aggregate measure (User)."""
    role = next(c[3] for c in CALCS[sid] if c[0] == calc)
    deriv, prefix, kind, typ = (("None", "none", "nk", "nominal") if role == "dimension"
                                else ("User", "usr", "qk", "quantitative"))
    name = f"[{prefix}:{calc}:{kind}]"
    return (f"[{ds_name(sid)}].{name}",
            [calc_column(sid, calc),
             f"<column-instance column='[{calc}]' derivation='{deriv}' name='{name}' pivot='key' type='{typ}' />"])


def calc_filter(sid: str, calc: str, *, context: bool = False) -> tuple[str, str, str]:
    """Keep rows where a boolean calculated field is true. Context filters run before Top N filters."""
    ref, decls = cinst(sid, calc)
    _, _, f = member_filter(sid, calc, "true")
    if context:
        f = f.replace("<filter class='categorical'", "<filter class='categorical' context='true'", 1)
    return ref, "".join(decls), f


def formula(sid: str, calc: str) -> str:
    return next(c[5] for c in CALCS[sid] if c[0] == calc)


def top_filter(sid: str, dim_calc: str, expression: str, n: int) -> str:
    level = f"[none:{dim_calc}:nk]"
    return (f"\n<filter class='categorical' column='[{ds_name(sid)}].{level}'><groupfilter count='{n}' end='top' "
            "function='end' units='records' user:ui-marker='end' user:ui-top-by-field='true'>"
            f"<groupfilter direction='DESC' expression={quoteattr(expression)} function='order' user:ui-marker='order'>"
            f"<groupfilter function='level-members' level='{level}' user:ui-enumeration='all' user:ui-marker='enumerate' />"
            "</groupfilter></groupfilter></filter>")


def svc_decls(*calcs: str) -> list[str]:
    return [d for c in calcs for d in cinst("svc", c)[1]]


def sheets() -> list[str]:
    out = []

    # P2 Priority table: top 25 community x request type in the selected band, all bands shown as columns
    pair, _ = cinst("svc", "Calculation_pair")
    band_v, _ = cinst("svc", "Calculation_selected_band")
    age, aged = inst("svc", "age_band", "None", "nk")
    v, vd = inst("svc", "open_requests", "Sum", "qk")
    out.append(worksheet(
        "P2 Priority table", "svc", rows=pair, cols=age,
        decls=svc_decls("Calculation_pair", "Calculation_selected_band") + [aged, vd],
        filters=[calc_filter("svc", "Calculation_keep_allages", context=True)],
        extra_filters=top_filter("svc", "Calculation_pair", formula("svc", "Calculation_selected_band"), 25),
        sorts=f"<sort class='computed' column='{pair}' direction='DESC' using='{band_v}' />",
        mark="Square", encodings=f"<encodings><color column='{v}' /><text column='{v}' /></encodings>",
        title="Where to send crews first: open requests by community and request type"))

    # P3 Trend: top 25 increases over three months, selected band
    ch, _ = cinst("svc", "Calculation_change")
    out.append(worksheet(
        "P3 Trend 3 months", "svc", rows=pair, cols=ch,
        decls=svc_decls("Calculation_pair", "Calculation_change"),
        filters=[calc_filter("svc", "Calculation_keep", context=True)],
        extra_filters=top_filter("svc", "Calculation_pair", formula("svc", "Calculation_change"), 25),
        sorts=f"<sort class='computed' column='{pair}' direction='DESC' using='{ch}' />",
        mark="Bar", encodings=f"<encodings><color column='{ch}' /></encodings>",
        title="Fastest growing: change in open requests over three months"))

    # P5 Communities: selected measure (count or per 1,000) per community; the map uses the same fields
    cn, cnd = inst("svc", "comm_name", "None", "nk")
    op, _ = cinst("svc", "Calculation_open")
    out.append(worksheet(
        "P5 Communities", "svc", rows=cn, cols=op, decls=svc_decls("Calculation_open") + [cnd],
        filters=[calc_filter("svc", "Calculation_keep", context=True)],
        extra_filters=top_filter("svc", "comm_name", formula("svc", "Calculation_open"), 15),
        sorts=f"<sort class='computed' column='{cn}' direction='DESC' using='{op}' />",
        mark="Bar", title="Communities with the most open requests in the selected band"))

    # P4 Stock headline (also used on the monthly screen): latest month end
    o90, o90d = inst("kpi", "open_90_plus", "Sum", "qk")
    rs, rsd = inst("kpi", "roads_share_of_90_plus", "Sum", "qk")
    syoy, syoyd = cinst("kpi", "Calculation_stock_yoy")
    out.append(worksheet(
        "P4 Stock headline", "kpi", rows="", cols="", decls=[o90d, rsd] + syoyd,
        filters=[calc_filter("kpi", "Calculation_latest_stock")],
        mark="Text", encodings=f"<encodings><text column='{o90}' /><text column='{syoy}' /><text column='{rs}' /></encodings>",
        title="Field requests open 90+ days, latest month end (all services)"))

    # M1 Flow headline: latest complete month
    rq, rqd = inst("kpi", "requests", "Sum", "qk")
    ryoy, ryoyd = cinst("kpi", "Calculation_requests_yoy")
    sh, shd = inst("kpi", "within_benchmark_share", "Sum", "qk")
    shy, shyd = cinst("kpi", "Calculation_share_yoy")
    out.append(worksheet(
        "M1 Flow headline", "kpi", rows="", cols="", decls=[rqd, shd] + ryoyd + shyd,
        filters=[calc_filter("kpi", "Calculation_latest_complete")],
        mark="Text",
        encodings=(f"<encodings><text column='{rq}' /><text column='{ryoy}' /><text column='{sh}' />"
                   f"<text column='{shy}' /></encodings>"),
        title="Requests and share closed within benchmark, latest complete month (all services)"))

    # M2 Stock trend
    mt, mtd = inst("kpi", "month", "Month-Trunc", "qk")
    out.append(worksheet(
        "M2 Stock trend", "kpi", rows=o90, cols=mt, decls=[o90d, mtd], filters=[], mark="Line",
        title="Requests open 90+ days are at their highest level since 2022"))

    # M3 Benchmark trend: complete months only
    ss, ssd = cinst("kpi", "Calculation_share_shown")
    out.append(worksheet(
        "M3 Benchmark trend", "kpi", rows=ss, cols=mt, decls=ssd + [mtd], filters=[], mark="Line",
        title="Share of requests closed within their service benchmark, complete months"))

    # M4 Slipping services: 2022-2024 against 2025 on, one dot per period
    pct, pctd = cinst("cm", "Calculation_pct")
    cat, catd = inst("cm", "service_category", "None", "nk")
    per, perd = cinst("cm", "Calculation_period")
    out.append(worksheet(
        "M4 Slipping services", "cm", rows=cat, cols=pct, decls=pctd + perd + [catd],
        filters=[calc_filter("cm", "Calculation_keep")],
        extra_filters=(f"\n<filter class='categorical' column='{per}'><groupfilter function='except' user:ui-domain='database' "
                       "user:ui-enumeration='exclusive' user:ui-marker='enumerate'><groupfilter function='level-members' "
                       "level='[none:Calculation_period:nk]' /><groupfilter function='member' level='[none:Calculation_period:nk]' "
                       "member='%null%' /></groupfilter></filter>"),
        sorts=f"<sort class='computed' column='{cat}' direction='ASC' using='{pct}' />",
        mark="Circle", encodings=f"<encodings><color column='{per}' /></encodings>",
        title="Closed within own benchmark, 2022-2024 against 2025 on: only Fire slipped"))


    # M5 Seasonality: average requests per calendar month (full months only)
    mo, mod = inst("cm", "request_month", "Month", "ok")
    avg = f"[{ds_name('cm')}].[avg:Calculation_monthtotal:qk]"
    avg_d = ("<column-instance column='[Calculation_monthtotal]' derivation='Avg' name='[avg:Calculation_monthtotal:qk]' "
             "pivot='key' type='quantitative' />")
    out.append(worksheet(
        "M5 Seasonality", "cm", rows=avg, cols=mo,
        decls=[calc_column("cm", "Calculation_monthtotal"), calc_column("cm", "Calculation_fullmonth"), avg_d, mod],
        filters=[member_filter("cm", "Calculation_fullmonth", "true")],
        mark="Bar", title="Requests peak in June; February and December are the quietest months"))

    # M6 Snow: daily snow requests and snowfall, winter 2025-2026
    d, dd = inst("sn", "day", "Day-Trunc", "qk")
    sr, srd = inst("sn", "snow_requests", "Sum", "qk")
    sf, sfd = inst("sn", "snowfall_cm", "Sum", "qk")
    win = (f"\n<filter class='quantitative' column='{d}' included-values='in-range'>"
           "<min>#2025-10-01#</min><max>#2026-04-30#</max></filter>")
    out.append(worksheet(
        "M6 Snow", "sn", rows=f"({sr} / {sf})", cols=d, decls=[srd, sfd, dd], filters=[],
        extra_filters=win, mark="Bar",
        title="Snow requests (top) follow snowfall (bottom) by one to three days, winter 2025-2026"))
    return out


STALE = ("Some requests open 90+ days may be records that were never closed in the system rather than work "
         "still waiting. Check a sample before sending a crew.")
POPULATION = "Population from the 2019 municipal census."


def data_date(exports: Path) -> str:
    import json

    latest = json.loads((exports / "manifest.json").read_text(encoding="utf-8"))["latest_request_date"]
    month_end = column_values(exports, SOURCES["svc"][1], "month_end")[-1]
    return (f"Backlog to {month_end}, requests to {latest}. Source: City of Calgary Open Data (311 Service Requests "
            "iahh-g8bj, communities surr-xmvs), ECCC daily climate CALGARY INTL A. Benchmark: each service's own "
            "80th percentile time to close in 2022-2024. 'Closed' means closed in the system, not fixed.")


def dashboard(name: str, title: str, notes: list[str]) -> str:
    """Empty canvas with the fixed texts; sheets are placed by hand (see the build guide)."""
    zones = [f"<zone h='6000' id='2' type-v2='text' w='100000' x='0' y='0'><formatted-text>"
             f"<run bold='true' fontsize='16'>{escape(title)}</run></formatted-text></zone>"]
    y = 100000 - 4000 * len(notes)
    for i, note in enumerate(notes):
        zones.append(f"<zone h='4000' id='{3 + i}' type-v2='text' w='100000' x='0' y='{y + 4000 * i}'><formatted-text>"
                     f"<run fontsize='8'>{escape(note)}</run></formatted-text></zone>")
    return f"""  <dashboard name={quoteattr(name)}>
    <style />
    <size maxheight='900' maxwidth='1300' minheight='900' minwidth='1300' sizing-mode='fixed' />
    <zones>
      <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
        {chr(10).join(zones)}
      </zone>
    </zones>
  </dashboard>"""


def build(exports: Path, extracts: Path) -> str:
    ws = sheets()
    dated = data_date(exports)
    dashboards = [
        dashboard("Priorities", "Calgary 311: where to send crews first", [STALE, POPULATION, dated]),
        dashboard("Monthly situation", "Calgary 311: monthly situation", [dated]),
    ]
    names = [s.split("name=", 1)[1].split(">", 1)[0].strip("'\"") for s in ws]
    cards = ("<cards><edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' />"
             "</strip></edge><edge name='top'><strip size='2147483647'><card type='columns' /></strip>"
             "<strip size='2147483647'><card type='rows' /></strip><strip size='31'><card type='title' /></strip></edge></cards>")
    windows = "\n".join([f"    <window class='dashboard' name={quoteattr(n)}><viewpoints /><active id='-1' /></window>" for n in ("Priorities", "Monthly situation")]
                        + [f"    <window class='worksheet' name={quoteattr(n)}>{cards}</window>" for n in names])
    return f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook original-version='18.1' source-build='2026.3.0' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences />
  <datasources>
{parameters(exports)}
{chr(10).join(datasource(s, exports, extracts) for s in SOURCES)}
  </datasources>
  <worksheets>
{chr(10).join(ws)}
  </worksheets>
  <dashboards>
{chr(10).join(dashboards)}
  </dashboards>
  <windows source-height='30'>
{windows}
  </windows>
</workbook>
"""


def build_extracts(exports: Path, extracts: Path) -> dict[str, tuple[int, int]]:
    """Load each CSV into <sid>.hyper, table "Extract"."Extract", the layout Tableau expects."""
    from tableauhyperapi import (
        Connection,
        CreateMode,
        HyperProcess,
        SqlType,
        TableDefinition,
        TableName,
        Telemetry,
    )

    sql = {"date": SqlType.date(), "integer": SqlType.big_int(), "real": SqlType.double(), "string": SqlType.text(),
           "boolean": SqlType.bool()}
    extracts.mkdir(parents=True, exist_ok=True)
    counts = {}
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        for sid, (_, fname) in SOURCES.items():
            path = exports / fname
            table = TableDefinition(TableName("Extract", "Extract"),
                                    [TableDefinition.Column(c, sql[dtype(c)]) for c in header(path)])
            with Connection(hyper.endpoint, extracts / f"{sid}.hyper", CreateMode.CREATE_AND_REPLACE) as con:
                con.catalog.create_schema("Extract")
                con.catalog.create_table(table)
                p = path.as_posix().replace("'", "''")
                n = con.execute_command(f"COPY {table.table_name} FROM '{p}' WITH (format csv, header)")
                rows = sum(1 for _ in path.open(encoding="utf-8")) - 1
                assert n == rows, f"{fname}: {n} rows loaded, {rows} in the CSV"  # self-check: nothing dropped
                counts[sid] = (n, rows)
                print(f"{sid}.hyper: {n:,} rows")
    return counts


def run(exports: Path, out: Path, extracts: Path) -> dict[str, tuple[int, int]]:
    counts = build_extracts(exports, extracts)
    xml = build(exports, extracts)
    import xml.dom.minidom as md  # self-check: the file must at least be well-formed XML

    md.parseString(xml.encode("utf-8"))
    out.write_text(xml, encoding="utf-8")
    print(f"Wrote {out}")
    return counts


if __name__ == "__main__":
    exports = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "processed" / "exports"
    # optional second argument: extracts folder (default data/processed/extracts; Tableau locks open .hyper files)
    extracts = Path(sys.argv[2]) if len(sys.argv) > 2 else exports.parent / "extracts"
    run(exports, ROOT / "tableau" / "calgary_311.twb", extracts)
