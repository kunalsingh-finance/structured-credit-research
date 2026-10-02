"""Build a portable research dashboard and a two-page credit memo from model evidence.

No forecast calculations are invented here. Monetary model inputs remain integer
cents; the interface converts only for display. The memo is regenerated from the
same versioned JSON as the dashboard and workbook.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "report_assets"


def number(value, default=None):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    return default


def dollars(cents):
    return number(cents, 0) / 100


def money(cents, compact=False):
    amount = dollars(cents)
    if compact and abs(amount) >= 1_000_000:
        formatted = f"${abs(amount) / 1_000_000:,.1f}m"
    else:
        formatted = f"${abs(amount):,.2f}"
    return f"({formatted})" if amount < 0 else formatted


def pct(value):
    return "Unavailable" if number(value) is None else f"{value:.1%}"


def period_text(value):
    return value if isinstance(value, str) else ", ".join(map(str, value or []))


def validate(pack):
    if not isinstance(pack.get("platform"), dict):
        raise ValueError("platform_results.json lacks platform metadata")
    scenarios = pack.get("scenarios")
    if not scenarios:
        raise ValueError("No completed credit scenarios available for artifacts")
    for scenario in scenarios:
        if not scenario.get("pool_rows") or not scenario.get("tranches"):
            raise ValueError(f"Scenario {scenario.get('name')} lacks pool/tranche cash flows")
        for tranche in scenario["tranches"]:
            if not tranche.get("rows"):
                raise ValueError(f"Scenario {scenario.get('name')} class {tranche.get('name')} lacks monthly cash flows")
    return pack


def verified_results(path, status_path):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("status") != "SUCCESS":
        raise ValueError("Research run is not SUCCESS; refusing to publish stale artifacts")
    if status.get("results_sha256") != digest:
        raise ValueError("Results SHA-256 differs from the successful run record")
    pack = validate(json.loads(raw))
    if status.get("built_at") != pack.get("generated_at"):
        raise ValueError("Successful run date differs from the results version")
    if not pack["platform"].get("valuation_date"):
        raise ValueError("An explicit cash-flow valuation date is required")
    if not pack.get("forecast_validation", {}).get("cashflow_validation", {}).get("scores"):
        raise ValueError("Withheld cash-flow validation scores are required")
    return pack, digest


def source_name(source):
    return source.get("title") or source.get("role") or source.get("kind") or source.get("accession") or "SEC filing"


def supplemental_html(pack):
    study = pack.get("supplemental_validation")
    if not study:
        return ""
    if study.get("primary_model_changed") is not False or study.get("scenario_assumptions_changed") is not False:
        raise ValueError("Supplemental study must preserve the frozen primary model and scenarios")
    escape = html.escape
    folds = study.get("expanding_folds", [])
    if not folds:
        raise ValueError("Supplemental validation lacks completed expanding folds")
    method_names = ("uncalibrated_expanding_logistic", "constant_baseline", "delinquency_transition_baseline", "smoothed_cohort_baseline")

    def brier(record, method):
        value = record.get("methods", {}).get(method, {}).get("events", {}).get("default", {}).get("brier")
        if number(value) is None:
            raise ValueError(f"Supplemental default Brier is missing for {method}")
        return value

    fold_rows = []
    worse = 0
    for fold in folds:
        scores = [brier(fold, name) for name in method_names]
        worse += scores[0] > scores[2]
        fold_rows.append(f'<tr><td>{escape(str(fold["fold"]))}</td><td>{escape(fold["origin_date"])} to {escape(fold["target_end"])}</td>' + ''.join(f'<td>{score:.7f}</td>' for score in scores) + '</tr>')
    comparison_rows = []
    primary_methods = ("unchanged_primary_model", *method_names[1:])
    for split, record in study.get("locked_test_supplemental_evaluations", {}).items():
        comparison_rows.append(f'<tr><td>{escape(split.replace("_", " "))}</td>' + ''.join(f'<td>{brier(record, method):.7f}</td>' for method in primary_methods) + '</tr>')
    segment_rows = []
    for split, segments in study.get("segment_stability", {}).items():
        by_feature = {}
        for segment in segments:
            event = segment["events"]["default"]
            gap = event["methods"]["unchanged_primary_model"]["calibration_gap"]
            if number(gap) is None:
                raise ValueError("Supplemental segment calibration gap is missing")
            previous = by_feature.get(segment["feature"])
            if previous is None or abs(gap) > abs(previous[1]):
                by_feature[segment["feature"]] = (segment, gap)
        for feature, (segment, gap) in by_feature.items():
            event = segment["events"]["default"]
            predicted = event["methods"]["unchanged_primary_model"]["predicted_rate"]
            segment_rows.append(f'<tr><td>{escape(split.replace("_", " "))}</td><td>{escape(feature.replace("_", " "))}</td><td>{escape(segment["segment"])}</td><td>{segment["test_rows"]:,}</td><td>{event["events"]:,}</td><td>{event["observed_rate"]:.3%}</td><td>{predicted:.3%}</td><td>{gap * 100:+.3f}</td></tr>')
    limits = ''.join(f'<li>{escape(item)}</li>' for item in study.get("limitations", []))
    return f'''<article class="card"><details><summary>Inspect supplemental validation after primary test review</summary><h3>Retrospective expanding folds and fixed segments</h3><p><strong>After-inspection study.</strong> The protocol was specified after reviewing the primary test results. Added comparisons are descriptive. The primary model and scenario assumptions remain unchanged.</p><p class="muted">First-observed default Brier score; lower is better. Each expanding fold fits fresh preprocessing and an uncalibrated logistic model using labels publicly available before its origin.</p><div class="table-scroll"><table><thead><tr><th>Fold</th><th>Target window</th><th>Fresh logistic</th><th>Constant</th><th>Delinquency transition</th><th>Smoothed cohort</th></tr></thead><tbody>{''.join(fold_rows)}</tbody></table></div><p>Fresh logistic default Brier is higher than the transition baseline in {worse} of {len(folds)} folds. This diagnostic does not select or replace the primary model.</p><h3>Descriptive comparisons on the original test sets</h3><div class="table-scroll"><table><thead><tr><th>Test set</th><th>Unchanged primary</th><th>Constant</th><th>Delinquency transition</th><th>Smoothed cohort</th></tr></thead><tbody>{''.join(comparison_rows)}</tbody></table></div><h3>Largest fixed-band default calibration gap</h3><p class="muted">One band per feature and test set with the largest absolute primary prediction-minus-observation gap. These conditional observations include repeated loans; small event counts limit inference. Gaps use percentage points and do not establish causal drift.</p><div class="table-scroll"><table><thead><tr><th>Test set</th><th>Feature</th><th>Band</th><th>Rows</th><th>Events</th><th>Observed</th><th>Predicted</th><th>Gap (pp)</th></tr></thead><tbody>{''.join(segment_rows)}</tbody></table></div><ul class="limits">{limits}</ul><p class="chart-note"><a href="extended_validation.json">Complete study, every band and its build identity</a>. Generated {escape(str(study.get("generated_at", ""))[:19].replace("T", " "))} UTC.</p></details></article>'''


def rate_review_html(pack):
    review = pack.get("rate_and_amendment_review")
    if not review:
        return ""
    escape = html.escape
    rate = review["rate_review"]
    checks = rate["checks"]
    matches = sum(check["status"] == "EXACT_MATCH" for check in checks)
    rows = ''.join(f'<tr><td>{escape(check["distribution_date"])}</td><td>{escape(check["sofr_adjustment_date"])}</td><td>{float(check["official_average30day_percent"]):.5f}%</td><td>{float(check["expected_coupon_percent"]):.5f}%</td><td>{float(check["observed_coupon_percent"]):.5f}%</td><td>{float(check["coupon_residual_percentage_points"]):+.6f}</td></tr>' for check in checks)
    inventory = sum(record["eligible_record_count"] for record in review["amendment_inventory"])
    document_count = len(review["primary_document_screens"])
    missing = '; '.join(f'{item["role"]}: HTTP {item["http_status"]}. {item["conclusion"]}' for item in review.get("unavailable_inventory_endpoints", []))
    sources = review["supplemental_source_verification"]["source_count"]
    return f'''<article class="card"><details><summary>Inspect historical coupon resets and amendment-search scope</summary><h3>Historical floating coupon check</h3><p>{matches} of {len(checks)} coupons match the official 30-day compounded SOFR average on the executed reset date plus the 0.69 percentage-point spread. This tests observed historical coupons; scenario floating rates remain an assumed constant.</p><div class="table-scroll"><table><thead><tr><th>Distribution date</th><th>SOFR adjustment date</th><th>Official average</th><th>Expected coupon</th><th>Observed coupon</th><th>Residual (pp)</th></tr></thead><tbody>{rows}</tbody></table></div><p class="chart-note">{escape(rate["limitations"])}</p><h3>Finite public amendment review</h3><p>{inventory} filer records in the defined execution-to-cutoff windows and {document_count} unique primary documents were reviewed. No post-execution transaction amendment was identified within that finite search. This does not establish absence of private or unfiled changes.</p><p class="muted">{escape(review["screen_scope_limit"])}</p><p>{escape(missing)}</p><p class="chart-note">{sources} supplemental archived records are verified separately from the frozen core archive. <a href="../docs/RATE_AND_AMENDMENT_REVIEW.md">Detailed review</a>, <a href="../data/rate_and_amendment_review.json">machine-readable evidence</a> and <a href="../data/rate_amendment_source_manifest.json">supplemental manifest</a>.</p></details></article>'''


def build_html(pack, output):
    escape = html.escape
    platform = pack["platform"]
    css = (ASSETS / "research.css").read_text(encoding="utf-8")
    js = (ASSETS / "research.js").read_text(encoding="utf-8")
    encoded = json.dumps(pack, ensure_ascii=False).replace("<", "\\u003c")
    sources = []
    for source in pack.get("source_provenance", []):
        url = source.get("url", "")
        if not url.startswith("https://"):
            continue
        sources.append(f'<tr><td><a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">{escape(source_name(source))}</a></td><td>{escape(str(source.get("period") or ""))}</td><td>{escape(str(source.get("sha256", "Unavailable")))}</td></tr>')
    limits = pack.get("limitations", []) + pack.get("forecast_validation", {}).get("limitations", [])
    # Preserve order while removing repetitive disclosures from component models.
    limits = list(dict.fromkeys(str(item) for item in limits))
    limits_html = "".join(f"<li>{escape(item)}</li>" for item in limits)
    replay_rows = []
    for record in pack.get("certificates", []):
        for row in record.get("replay_comparison", []):
            replay_rows.append((row.get("status") == "DIFFERENCE", record, row))
    replay_rows.sort(key=lambda item: (not item[0], item[1].get("collection_period_end", ""), item[2].get("name", "")))
    replay_html = []
    for different, record, row in replay_rows:
        status_class = "difference" if different else ""
        replay_html.append(f'<tr class="{status_class}"><td>{escape(record.get("collection_period_end", ""))}</td><td>{escape(row.get("name", ""))}</td><td>{money(row.get("computed_cents"))}</td><td>{money(row.get("reported_cents"))}</td><td>{money(row.get("residual_cents"))}</td></tr>')
    loan_controls = pack.get("loan_tape_reconciliation", {})
    comparisons = loan_controls.get("comparisons", [])
    latest_comparisons = [r for r in comparisons if r.get("deal_id") == platform.get("deal_id") and r.get("period_end") == platform.get("as_of")]
    loan_control_html = []
    for record in latest_comparisons:
        for check in record.get("checks", []):
            is_money = check.get("units") == "cents"
            display = money if is_money else lambda v: f"{number(v, 0):,}"
            css_class = "difference" if check.get("status") != "PASS" else ""
            label = check["check"].replace("_", " ")
            loan_control_html.append(f'<tr class="{css_class}"><td title="{escape(check.get("explanation", ""), quote=True)}">{escape(label)}</td><td>{display(check.get("observed"))}</td><td>{display(check.get("reported"))}</td><td>{display(check.get("residual"))}</td></tr>')
    loan_control_section = ''
    if loan_control_html:
        loan_control_section = f'<article class="card"><h3>Latest loan-tape controls</h3><p class="muted">{escape(str(platform.get("as_of")))}. {loan_controls.get("row_count", 0):,} loan-month records across the research panel. Strict source gate: {loan_controls.get("unresolved_comparisons", 0)} unresolved comparisons. Source definitions can differ; residuals are retained.</p><div class="table-scroll"><table><thead><tr><th>Quantity</th><th>Loan tape</th><th>Certificate</th><th>Tape minus certificate</th></tr></thead><tbody>{"".join(loan_control_html)}</tbody></table></div><p class="chart-note">Raw principal reductions can include noncash changes. First-event beginning-exposure forecast errors measure event exposure, not certificate charge-off cash. <a href="../data/panel_summary.json">Full period controls</a>, <a href="../data/source_exception_register.json">investigated exceptions</a> and <a href="../docs/SOURCE_RECONCILIATION.md">source reconciliation</a>. The latest collateral difference does not bound unresolved cash differences.</p></article>'
    reverse = pack.get("reverse_stress", {})
    reverse_rows = []
    for row in reverse.get("grid", []):
        reverse_rows.append(f'<tr><td>{escape(str(row.get("severity")))}</td><td>{money(row.get("principal_loss_cents"), True)}</td><td>{money(row.get("interest_shortfall_cents"), True)}</td><td>{"Yes" if row.get("maturity_failure") else "No"}</td><td>{"Yes" if row.get("breach") else "No"}</td></tr>')
    reverse_section = ''
    if reverse_rows:
        first = reverse.get("first_breach")
        notice = f'First observed breach: default-hazard multiplier {first["severity"]}.' if first else 'No breach occurs on the supplied grid.'
        reverse_section = f'<article class="card"><h3>Reverse stress: class {escape(str(reverse.get("tranche")))}</h3><p class="muted">{escape(notice)} Prepayment, recovery, recovery delay and interest collection assumptions remain adverse across the grid.</p><div class="table-scroll"><table><thead><tr><th>Default-hazard multiplier</th><th>Principal impairment</th><th>Unpaid interest</th><th>Maturity failure</th><th>Breach</th></tr></thead><tbody>{"".join(reverse_rows)}</tbody></table></div><p class="chart-note">{escape(str(reverse.get("interpretation", "")))}</p></article>'
    title = platform.get("deal_name", "CarMax Auto Owner Trust 2025-2")
    built = str(pack.get("generated_at", ""))[:19].replace("T", " ")
    cash_validation = pack.get("forecast_validation", {}).get("cashflow_validation", {})
    cash_rows = ''.join(f'<tr><td>{escape(row["deal_id"])}</td><td>{escape(row["quantity"].replace("_", " "))}</td><td>{row["months"]}</td><td>{money(row["baseline_mae_cents"], True)}</td><td>{money(row["model_mae_cents"], True)}</td></tr>' for row in cash_validation.get("scores", []))
    cash_limits = ''.join(f'<li>{escape(item)}</li>' for item in cash_validation.get("limitations", []))
    cash_section = f'<article class="card"><h3>Withheld servicing cash forecast</h3><p><strong>Mixed result:</strong> the fitted model improves unseen-deal default and interest errors, but materially worsens principal collections and pool runoff. Scenarios remain illustrative assumptions, not validated investment forecasts.</p><p class="muted">{escape(cash_validation.get("method", ""))}. Both models use information public at each forecast origin.</p><div class="table-scroll"><table><thead><tr><th>Deal</th><th>Quantity</th><th>Months</th><th>Baseline cash MAE</th><th>Model cash MAE</th></tr></thead><tbody>{cash_rows}</tbody></table></div><ul class="limits">{cash_limits}</ul><p class="chart-note">Errors are dollars against actual certificate quantities. Monthly forecasts, known source periods and assumptions are preserved in the downloadable research data.</p></article>' if cash_rows else ''
    gates_rows = []
    for label, gate in pack.get("research_gates", {}).items():
        detail = gate.get("evidence") or "; ".join(f'{key.replace("_", " ")}: {value}' for key, value in gate.items() if key != "status")
        gates_rows.append(f'<tr><td>{escape(label.replace("_", " "))}</td><td>{escape(gate.get("status", "Unavailable"))}</td><td>{escape(detail)}</td></tr>')
    gates_section = f'<article class="card"><h3>Research gates</h3><p class="muted">A successful build preserves results and exceptions. The financial validation gates below retain their own status.</p><div class="table-scroll"><table class="gates-table"><thead><tr><th>Research gate</th><th>Status</th><th>Evidence</th></tr></thead><tbody>{"".join(gates_rows)}</tbody></table></div></article>' if gates_rows else ''
    supplemental_section = supplemental_html(pack)
    rate_review_section = rate_review_html(pack)
    initial_yield_pct = number(pack["scenarios"][0].get("assumptions", {}).get("discount_rate"), .08) * 100
    content = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Structured Credit Research | {escape(title)}</title><style>{css}</style></head>
<body><header><a class="brand" href="#">KS <span>Credit Research</span></a><nav><a href="#scenario">Scenarios</a><a href="#evidence">Validation</a><a href="#sources">Sources</a></nav></header>
<main><section class="hero"><div><p class="eyebrow">AUTO LOAN ABS / INDEPENDENT RESEARCH</p><h1>Borrower risk.<br>Bond cash flows.</h1><p class="intro">{escape(title)}. Trace collateral performance through the payment waterfall, then inspect principal losses, interest shortfalls and repayment timing.</p><p class="hero-meta">Observed through <strong>{escape(str(platform.get('as_of', 'Unavailable')))}</strong> <span>USD throughout</span></p><p class="muted">{escape(str(pack.get("status", "Development research")).capitalize())}.</p></div><aside class="hero-card"><p class="eyebrow">RESEARCH QUESTION</p><h2>How much protection survives the downside?</h2><p>Change the scenario to compare collateral losses with tranche protection. Adjust the discount yield to inspect cash-flow value.</p><div class="downloads"><a href="outputs/credit_research/cashflow_workbook.xlsx">Cash-flow workbook</a><a href="pdf/credit_memo.pdf">Credit memo</a><a href="platform_results.json">Research data</a></div></aside></section>
<section id="scenario" class="scenario-panel"><div class="section-heading"><div><p class="eyebrow">01 / CREDIT SCENARIOS</p><h2>From collateral to tranche</h2></div><label>Scenario<select id="scenario-select" aria-label="Credit scenario"></select></label></div><p id="scenario-description" class="muted"></p><div class="metric-grid" id="metrics"></div>
<div class="chart-grid"><article class="card"><div class="chart-head"><h3>Collateral runoff and net loss</h3><span>USD millions</span></div><div id="pool-chart" class="chart"></div><p class="chart-note">Balances and cumulative net loss use the same dollar scale.</p></article><article class="card"><div class="chart-head"><h3>Monthly payments</h3><label>Class<select id="class-select" aria-label="Note class"></select></label></div><div id="cash-chart" class="chart"></div><p class="chart-note">Principal and interest paid to the selected class. USD millions.</p></article></div>
<article class="card valuation"><div><h3>Cash-flow value</h3><p>Valuation date: {escape(str(platform.get('valuation_date', 'Unavailable')))}. Effective annual discount yield; no independent market quote is available.</p></div><label>Discount yield <strong id="yield-display"></strong><input id="yield-input" type="range" min="0" max="30" step="0.25" value="{initial_yield_pct:g}" aria-label="Discount yield percent"></label><div><span>Model value per $100</span><strong id="model-price"></strong></div></article>
<article class="card"><h3>Class protection and principal timing</h3><div class="table-scroll"><table id="tranche-table"><thead><tr><th>Class</th><th>Opening principal</th><th>Opening protection</th><th>Principal paid</th><th>Principal loss</th><th>Unpaid interest</th><th>WAL (years)</th><th>Value / $100</th></tr></thead><tbody></tbody></table></div><p class="chart-note">Opening protection combines junior note principal, overcollateralization and reserve support as a share of collateral, using the model definition. WAL uses principal payment dates and actual elapsed days / 365.25. WAL is unavailable after principal loss or incomplete repayment. The research data separately reports average timing of repaid principal.</p></article>
<article class="note"><h3>Scenario interpretation</h3><p id="scenario-interpretation"></p><p>Borrower assumptions and structural mechanics are calculated in Python. This interface reprices saved cash flows when yield changes; rerun the research pipeline to change credit assumptions.</p></article>{reverse_section}</section>
<section id="evidence"><div class="section-heading"><div><p class="eyebrow">02 / VALIDATION</p><h2>What the evidence supports</h2></div></div>{gates_section}<div class="evidence-grid"><article class="card"><h3>Historical payment replay</h3><div id="historical-evidence"></div><p class="muted">Reported-data arithmetic and contractual replay are different checks. Differences remain visible.</p></article><article class="card"><h3>Chronological forecast evaluation</h3><div id="forecast-evidence"></div><p class="chart-note">Exposure MAE compares predicted and observed beginning principal associated with first-observed default/prepayment events. Brier score and AUC are dimensionless.</p></article></div>{cash_section}{supplemental_section}{loan_control_section}<article class="card"><details><summary>Inspect calculated payments against servicer reports</summary><div class="table-scroll"><table><thead><tr><th>Collection period</th><th>Quantity</th><th>Calculated</th><th>Reported</th><th>Difference</th></tr></thead><tbody>{''.join(replay_html)}</tbody></table></div></details></article><article class="card"><h3>Source and model limits</h3><ul class="limits">{limits_html}</ul></article></section>
<section id="sources"><div class="section-heading"><div><p class="eyebrow">03 / SOURCE RECORD</p><h2>Original evidence, preserved</h2></div></div><article class="card"><p class="muted">{len(sources)} archived source records. <a href="../data/source_manifest.json">Source manifest</a> and <a href="../data/source_verification.json">byte verification</a> preserve the accession, archive path and original content hashes.</p><details><summary>Inspect original sources and hashes</summary><div class="table-scroll"><table class="source-table"><thead><tr><th>Filing</th><th>Period</th><th>SHA-256 of original bytes</th></tr></thead><tbody>{''.join(sources)}</tbody></table></div></details></article>{rate_review_section}</section>
</main><footer><span>Kunal Singh / Structured Credit Research</span><span>Generated {escape(built)} UTC</span></footer><script id="research-data" type="application/json">{encoded}</script><script>{js}</script></body></html>'''
    output.write_text(content, encoding="utf-8")


def build_pdf(pack, output):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import simpleSplit
    from reportlab.platypus import Paragraph
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader

    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = 612, 792
    navy, muted, cream, gold = (colors.HexColor(c) for c in ("#102537", "#536575", "#F4F1E8", "#B89451"))
    cv = canvas.Canvas(str(output), pagesize=(width, height))
    cv.setTitle("CarMax 2025-2 | Structured Credit Research")
    cv.setAuthor("Kunal Singh")
    style = ParagraphStyle("Memo", fontName="Helvetica", fontSize=9.3, leading=13.1, textColor=navy)
    x, usable = 42, 528

    def text(value, y, size=9.3, color=navy, bold=False):
        cv.setFillColor(color)
        cv.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        cv.drawString(x, y, str(value))

    def para(value, y, font_size=9.3):
        local = ParagraphStyle("Local", parent=style, fontSize=font_size, leading=font_size * 1.4)
        p = Paragraph(html.escape(str(value)), local)
        _, h = p.wrap(usable, height)
        p.drawOn(cv, x, y - h)
        return y - h - 8

    def heading(label, y):
        text(label, y, 11, bold=True)
        return y - 17

    def footer(page):
        cv.setStrokeColor(colors.HexColor("#D9DFE2"))
        cv.line(x, 37, width - x, 37)
        text("Kunal Singh | Independent structured-credit research", 23, 7.5, muted)
        cv.drawRightString(width - x, 23, f"{page} / 2")

    def table(headers, rows, y, widths):
        cv.setFillColor(navy)
        cv.rect(x, y - 22, usable, 22, fill=1, stroke=0)
        positions = [x]
        for col_width in widths[:-1]:
            positions.append(positions[-1] + col_width)
        cv.setFont("Helvetica-Bold", 8.3)
        cv.setFillColor(colors.white)
        for idx, value in enumerate(headers):
            cv.drawString(positions[idx] + 5, y - 14, value)
        y -= 22
        for r, row in enumerate(rows):
            cv.setFillColor(cream if r % 2 == 0 else colors.white)
            cv.rect(x, y - 21, usable, 21, fill=1, stroke=0)
            cv.setFillColor(navy)
            cv.setFont("Helvetica", 8.2)
            for idx, value in enumerate(row):
                cv.drawString(positions[idx] + 5, y - 14, str(value))
            y -= 21
        return y - 12

    platform = pack["platform"]
    scenarios = pack["scenarios"]
    base = scenarios[0]
    adverse = scenarios[-1]
    base_total = sum(number(t.get("loss_cents", t.get("principal_loss_cents")), 0) for t in base["tranches"])
    adverse_total = sum(number(t.get("loss_cents", t.get("principal_loss_cents")), 0) for t in adverse["tranches"])
    exposed = [t.get("name", t.get("class")) for t in adverse["tranches"] if number(t.get("loss_cents", t.get("principal_loss_cents")), 0) > 0]
    text("AUTO LOAN ABS / CREDIT MEMO", 751, 8.5, muted, True)
    text(platform.get("deal_name", "CarMax Auto Owner Trust 2025-2"), 724, 21, bold=True)
    text(f"Observed {platform.get('as_of', 'Unavailable')} | Valuation {platform.get('valuation_date', 'Unavailable')} | Built {str(pack.get('generated_at',''))[:10]}", 704, 8.5, muted)
    cv.setStrokeColor(gold)
    cv.line(x, 690, width - x, 690)
    y = 670
    y = heading("Credit view", y)
    conclusion = pack.get("research_conclusion", {})
    if isinstance(conclusion, dict):
        conclusion = conclusion.get("summary") or conclusion.get("credit_view")
    if not conclusion:
        conclusion = f"Configured scenarios produce {money(base_total, True)} of note principal loss in {base['name']} and {money(adverse_total, True)} in {adverse['name']}. " + (f"The adverse case allocates principal loss to {', '.join(exposed)}." if exposed else "No note class loses principal in the most adverse configured case.")
    y = para(conclusion, y)
    reverse = pack.get("reverse_stress", {})
    if reverse.get("grid"):
        first = reverse.get("first_breach")
        finding = f"first observed breach at default-hazard multiplier {first['severity']}" if first else "no breach on the supplied grid"
        y = para(f"Reverse stress for class {reverse.get('tranche')}: {finding}. The grid fixes adverse prepayment, recovery and collection assumptions. It does not establish a continuous minimum.", y)
    y = para("The analysis evaluates structural cash-flow resilience. An investment return conclusion requires an independent market price, executable spread and liquidity assessment. Discounted values in the workbook use editable yield and purchase-price assumptions.", y)
    y = heading("Collateral and evidence", y - 4)
    active_loans = platform.get("active_target_loans", platform.get("loan_count", "unavailable"))
    y = para(f"The case uses public SEC collateral disclosures and distribution reports. The latest observed pool is {money(platform.get('latest_pool_cents'), True)}, versus an initial pool of {money(platform.get('initial_pool_cents'), True)}. The latest active loan count is {active_loans}. Source bytes, SHA-256 hashes and extraction provenance are preserved in the research pack.", y)
    unmapped = platform.get("unmapped_collateral_cents")
    if number(unmapped) is not None and unmapped != 0:
        y = para(f"The certificate exceeds mapped loan principal by {money(unmapped)}. Every scenario assigns this unreconciled amount immediate full loss with no recovery. This treatment does not bound other unresolved source cash differences.", y, 8.8)
    y = heading("Scenario comparison", y - 4)
    scenario_rows = []
    for case in scenarios:
        rows = case["pool_rows"]
        net_loss = sum(number(row.get("net_loss_cents"), 0) for row in rows)
        note_loss = sum(number(t.get("loss_cents", t.get("principal_loss_cents")), 0) for t in case["tranches"])
        shortfall = sum(number(t.get("interest_shortfall_cents"), 0) for t in case["tranches"])
        scenario_rows.append([case["name"][:23], money(net_loss, True), money(note_loss, True), money(shortfall, True)])
    y = table(["Scenario", "Pool net loss", "Note loss", "Unpaid interest"], scenario_rows, y, [180, 108, 108, 132])
    y = heading(f"Class outcomes: {adverse['name']}", y - 3)
    class_rows = [[t.get("name", t.get("class")), money(t.get("opening_balance_cents", t.get("initial_balance_cents")), True), "n.a." if not t.get("opening_balance_cents", t.get("initial_balance_cents")) else pct(t.get("credit_enhancement_pct")), money(t.get("loss_cents", t.get("principal_loss_cents")), True), "n.a." if number(t.get("wal_years")) is None else f"{t['wal_years']:.2f}", money(t.get("interest_shortfall_cents"), True)] for t in adverse["tranches"]]
    y = table(["Class", "Opening", "Protection", "Loss", "WAL (yrs)", "Unpaid int."], class_rows, y, [55, 92, 82, 92, 77, 130])
    if y < 55:
        raise ValueError("Credit memo page 1 exceeded available space")
    footer(1)
    cv.showPage()
    text("VALIDATION, ASSUMPTIONS AND MODEL LIMITS", 751, 8.5, muted, True)
    text("What the model establishes", 724, 21, bold=True)
    cv.setStrokeColor(gold)
    cv.line(x, 708, width - x, 708)
    y = 688
    y = heading("Historical reconciliation", y)
    arithmetic = pack.get("arithmetic_summary", {})
    interest_checks = [row for record in pack.get("certificates", []) for row in record.get("replay_comparison", []) if str(row.get("name", "")).startswith("interest.")]
    interest_matches = sum(row.get("residual_cents") == 0 for row in interest_checks)
    y = para(f"Reported-data checks: {arithmetic.get('PASS', 'unavailable')} / {arithmetic.get('total', 'unavailable')} pass. Class interest matches: {interest_matches} / {len(interest_checks)}. Historical replay differences: {pack.get('replay_difference_count', 'unavailable')}. Replay uses observed cash and balances; it tests structural mechanics separately from borrower forecasting.", y)
    oc_diffs = sorted({row.get("residual_cents") for record in pack.get("certificates", []) for row in record.get("replay_comparison", []) if row.get("name") == "oc_target" and row.get("residual_cents")})
    if oc_diffs:
        y = para("Calculated minus reported OC target: " + ", ".join(money(v) for v in oc_diffs) + f". Related payment differences remain visible. The strict tape/certificate gate has {pack.get('loan_tape_reconciliation', {}).get('unresolved_comparisons', 0)} unresolved comparisons; neither ingestion checks nor the small latest balance difference resolves them.", y, 8.8)
    validation = pack.get("forecast_validation", {})
    y = heading("Borrower forecast evaluation", y - 4)
    train = validation.get("training_periods", platform.get("train_periods", []))
    holdout = validation.get("holdout_periods", platform.get("holdout_periods", []))
    method = validation.get("method", "See research data for the fitted borrower model")
    y = para(f"{method}. Train: {period_text(train)}. Holdout: {period_text(holdout)}. Target: first-observed default disclosure, which can follow the effective default month. The same-originator unseen-deal test is separate from the later-month test.", y)
    metrics = validation.get("metrics", [])
    if metrics:
        metric_rows = []
        selected_metrics = [m for m in metrics if "default brier" in m.get("metric", "")]
        selected_metrics = selected_metrics[:2] if selected_metrics else metrics[:2]
        for item in selected_metrics:
            units = str(item.get("unit", ""))
            def fmt(v):
                if number(v) is None:
                    return "Unavailable"
                return money(v, True) if "cents" in units else f"{v:.6g}"
            label = str(item.get("metric", item.get("name", "Metric"))).replace("balance_mae_cents", "exposure MAE").replace("_", " ").replace("default", "observed-default")
            metric_rows.append([label[:43], fmt(item.get("baseline_mae", item.get("baseline"))), fmt(item.get("model_mae", item.get("model"))), "USD exposure" if "cents" in units else units[:14]])
        y = table(["Metric", "Baseline", "Fitted model", "Unit"], metric_rows, y, [230, 100, 105, 93])
    cash_validation = validation.get("cashflow_validation", {})
    unseen_cash = [row for row in cash_validation.get("scores", []) if row.get("deal_id") == platform.get("deal_id")]
    if unseen_cash:
        y = heading("Withheld servicing cash: unseen deal", y - 4)
        y = table(["Cash quantity / MAE", "Baseline", "Fitted model"], [[row["quantity"].replace("_", " "), money(row["baseline_mae_cents"], True), money(row["model_mae_cents"], True)] for row in unseen_cash], y, [230, 145, 153])
        y = para(f"Across {unseen_cash[0]['months']} withheld months, the fitted model improves default and interest errors but materially worsens principal collections and pool runoff. Scenarios are illustrative paths, not validated investment forecasts. The dashboard preserves both deals and monthly forecasts.", y, 8.8)
    y = heading("Assumptions and sensitivity", y - 4)
    assumptions = adverse.get("assumptions", {})
    details = []
    for key, value in assumptions.items():
        if isinstance(value, (str, int, float, bool)):
            label = key.replace("_", " ")
            rate_field = "rate" in key or "cpr" in key or "cndr" in key
            try:
                rate_value = float(value) if rate_field else None
            except (ValueError, TypeError):
                rate_value = None
            rendered = (f"{rate_value:.3%}" if "floating" in key else pct(rate_value)) if rate_value is not None else str(value)
            details.append(f"{label}: {rendered}")
    y = para(f"{adverse['name']}: " + "; ".join(details[:8]) + ". Credit scenarios require a Python rerun. Excel recalculates monthly discounted value, price per $100, weighted-average life and balance roll-forward differences from exported cash flows.", y)
    y = heading("Material limitations", y - 4)
    limits = list(dict.fromkeys(str(item) for item in pack.get("limitations", []) + validation.get("limitations", [])))
    # Avoid repeating the feature-timing, reporting-date and cash/price caveats
    # already stated on these pages. The complete list stays in the dashboard.
    selected_limits = [item for item in limits if not any(phrase in item.lower() for phrase in ("all predictors", "public reporting delays", "latest tape mapped", "executed 0.75", "executed0.75", "forecasts begin", "discount rate"))]
    for item in selected_limits[:2]:
        y = para("- " + item, y, 8.6)
    study = pack.get("supplemental_validation")
    if study:
        folds = study["expanding_folds"]
        worse = sum(fold["methods"]["uncalibrated_expanding_logistic"]["events"]["default"]["brier"] > fold["methods"]["delinquency_transition_baseline"]["events"]["default"]["brier"] for fold in folds)
        text(f"After-inspection study: transition default Brier beats fresh logistic in {worse}/{len(folds)} folds.", y - 4, 8.1, muted)
        y -= 15
    if not limits:
        y = para("Single-deal research does not establish unseen-deal forecast validity. Values depend on configured credit and discount assumptions. Archived public disclosures may contain reporting corrections or gaps.", y)
    y = heading("Primary sources and reproducibility", y - 4)
    memo_sources = [s for s in pack.get("source_provenance", []) if s.get("url", "").startswith("https://")]
    def source_priority(s):
        url = s["url"].lower()
        target = platform.get("deal_id", "") in s.get("title", "")
        if "dex41.htm" in url and target:
            return 0
        if s.get("role") == "certificate" and str(s.get("period", "")).startswith(str(platform.get("as_of", ""))[:7]) and target:
            return 1
        return 2 if target else 3
    memo_sources.sort(key=source_priority)
    source_urls = list(dict.fromkeys(s["url"] for s in memo_sources))
    for index, url in enumerate(source_urls[:2]):
        label = "Executed indenture: payment priorities (SEC)" if index == 0 else "Latest distribution certificate: observed balances and payments (SEC)"
        text(label, y - 8, 7.8, muted)
        cv.linkURL(url, (x, y - 11, x + usable, y + 1), relative=0, thickness=0)
        y -= 15
    if y < 55:
        raise ValueError(f"Credit memo page 2 exceeded available space (last content y={y:.1f})")
    footer(2)
    cv.save()
    reader = PdfReader(output)
    if len(reader.pages) != 2:
        raise ValueError("Credit memo must have exactly two pages")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "output" / "platform_results.json")
    parser.add_argument("--html", type=Path, default=ROOT / "output" / "research_report.html")
    parser.add_argument("--pdf", type=Path, default=ROOT / "output" / "pdf" / "credit_memo.pdf")
    parser.add_argument("--run-status", type=Path)
    args = parser.parse_args()
    pack, digest = verified_results(args.input, args.run_status or args.input.parent / "platform_run_status.json")
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    staged_html = args.html.with_suffix(".building.html")
    staged_pdf = args.pdf.with_suffix(".building.pdf")
    try:
        build_html(pack, staged_html)
        build_pdf(pack, staged_pdf)
        staged_html.replace(args.html)
        staged_pdf.replace(args.pdf)
    finally:
        staged_html.unlink(missing_ok=True)
        staged_pdf.unlink(missing_ok=True)
    qa = ROOT / "output" / "qa" / "artifacts"
    qa.mkdir(parents=True, exist_ok=True)
    verification = {"results_sha256": digest, "generated_at": pack["generated_at"], "run_status": "SUCCESS", "valuation_date": pack["platform"]["valuation_date"], "pdf_pages": 2, "outputs": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (args.html, args.pdf)}}
    (qa / "verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(f"Dashboard: {args.html}\nCredit memo: {args.pdf}")


if __name__ == "__main__":
    main()
