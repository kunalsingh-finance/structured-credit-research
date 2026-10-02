"""Review official SOFR resets and a finite public SEC amendment inventory.

--acquire archives supplemental evidence in a SEPARATE manifest. The frozen
243-source performance corpus, loan panel and model snapshot are not modified.
Without --acquire this reruns the review from preserved primary-source bytes.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import gzip
from html import unescape
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from credit_research.ingest import verify_archive
from acquire_data import Downloader, DEFAULT_USER_AGENT, filing_records

FILERS = {
    2016948: ("CAOT-2024-2 issuing trust", "2024-04-24"),
    2063979: ("CAOT-2025-2 issuing trust", "2025-05-02"),
    1259380: ("CarMax Auto Funding LLC depositor", "2024-04-24"),
    1170010: ("CarMax Inc sponsoring parent", "2024-04-24"),
}
CUTOFF = "2026-10-02"
REVIEW_MANIFEST = ROOT / "data/rate_amendment_source_manifest.json"


def plain_html(raw):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="replace"))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquire", action="store_true")
    args = parser.parse_args()
    core_manifest = json.loads((ROOT / "data/source_manifest.json").read_text(encoding="utf-8"))["sources"]
    downloader = Downloader(DEFAULT_USER_AGENT, REVIEW_MANIFEST)
    all_sources = {s["url"]: s for s in core_manifest + downloader.manifest["sources"]}

    def retrieve(url, name, kind, **metadata):
        source = all_sources.get(url)
        if source is None:
            if not args.acquire:
                raise ValueError("Missing archived review source; rerun --acquire: " + url)
            source = downloader.archive(url, ROOT / "data/raw/review" / name, kind=kind, **metadata)
            all_sources[url] = source
        with gzip.open(ROOT / source["archive_path"], "rb") as stream:
            return source, stream.read()

    def reference(source):
        return {k: source[k] for k in ("url", "archive_path", "sha256_original_bytes", "sha256_archive",
                                      "original_byte_count", "archive_byte_count", "retrieved_at_utc",
                                      "acceptance_time", "accession") if k in source}

    inventory = []
    selected = {}
    for cik, (role, first_date) in FILERS.items():
        url = f"https://data.sec.gov/submissions/CIK{cik:010}.json"
        source, raw = retrieve(url, f"CIK{cik:010}.json.gz", "amendment_inventory_submissions", cik=cik)
        document = json.loads(raw)
        records = filing_records(document)
        history_review = []
        for historical in document["filings"].get("files", []):
            overlap = historical["filingTo"] >= first_date
            history_review.append(dict(historical) | {"overlaps_review_window": overlap})
            if overlap:
                oldsource, oldraw = retrieve("https://data.sec.gov/submissions/" + historical["name"],
                    historical["name"] + ".gz", "amendment_inventory_history", cik=cik)
                old = json.loads(oldraw)
                records.extend({k: v[i] for k, v in old.items()} for i in range(len(old["accessionNumber"])))
        eligible = [r for r in records if r["filingDate"] >= first_date and r["acceptanceDateTime"][:10] <= CUTOFF]
        inventory.append({"cik": cik, "role": role, "from_execution_date": first_date, "through_utc_date": CUTOFF,
                          "submission_source": reference(source), "total_returned_records": len(records),
                          "returned_filing_date_min": min(r["filingDate"] for r in records),
                          "returned_filing_date_max": max(r["filingDate"] for r in records),
                          "history_files_reviewed_for_window_coverage": history_review,
                          "eligible_record_count": len(eligible), "form_counts": dict(Counter(r["form"] for r in eligible)),
                          "eligible_records": eligible})
        for record in eligible:
            # Every trust primary, and depositor/parent current reports, periodic
            # reports and registration amendments. All forms are inventoried;
            # other deal offering/ownership documents are not treated as amended
            # transaction evidence solely because they contain generic wording.
            form = record["form"]
            if cik in {2016948, 2063979} or form in {"8-K", "10-K", "10-Q", "POS AM", "SF-3", "AW"} or form.endswith("/A"):
                selected.setdefault(record["accessionNumber"], (cik, record))

    screens = []
    manual_context = {
        "0002016948-25-000027": "Annual exhibit index incorporates original April 1, 2024 Indenture/SSA and trust agreement; amended/restated language refers to original trust/2004 depositor LLC agreements, not a new transaction amendment.",
        "0002016948-26-000029": "Annual exhibit index again incorporates original April 1, 2024 agreements, with no newly dated transaction amendment listed; original amended/restated descriptions are not post-execution amendments.",
        "0002063979-26-000027": "Annual exhibit index incorporates original May 1, 2025 agreements from the April 28, 2025 pre-closing 8-K. No newly dated transaction amendment is listed; this incorporation pointer is not proof of absolute absence of changes.",
    }
    target_expression = re.compile(r"(?:CarMax\s+Auto\s+Owner\s+Trust|CAOT)\s*[-–]?\s*(202[45])\s*[-–]\s*2", re.I)
    for index, (accession, (cik, record)) in enumerate(sorted(selected.items()), 1):
        primary = record["primaryDocument"]
        # Existing primary source from a joint depositor/trust filing is reusable.
        known = next((s for s in core_manifest if s.get("accession") == accession and s["url"].endswith("/" + primary)), None)
        url = known["url"] if known else f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{primary}"
        source, raw = retrieve(url, f"{accession}-{Path(primary).name}.gz", "amendment_screen_primary",
                               cik=cik, accession=accession, form=record["form"],
                               acceptance_time=record["acceptanceDateTime"], filing_date=record["filingDate"])
        text = plain_html(raw)
        mentions = [{"deal_id": "CAOT-" + match[1] + "-2", "text_offset": match.start(),
                     "context": text[max(0, match.start() - 180):match.end() + 650]}
                    for match in target_expression.finditer(text)]
        amendment_words = re.findall(r"(?i)\b(?:amendment|amended|supplemental indenture|waiver|benchmark replacement|conforming changes)\b", text)
        baseline = accession in {"0001193125-24-109815", "0001193125-25-111714"}
        only_pre_execution = bool(mentions) and all(record["filingDate"] <
            ("2024-04-24" if m["deal_id"] == "CAOT-2024-2" else "2025-05-02") for m in mentions)
        disposition = ("BASELINE_EXECUTION" if baseline else
                       "PRE_EXECUTION_OFFERING_FORM" if only_pre_execution else
                       "ORIGINAL_DOCUMENTS_INCORPORATED_NO_NEW_AMENDMENT" if accession in manual_context else
                       "TARGET_MENTION_REQUIRES_CONTEXT_REVIEW" if mentions and amendment_words else
                       "NO_TARGET_AND_AMENDMENT_CO_OCCURRENCE")
        screens.append({"accession": accession, "cik": cik, "form": record["form"],
                        "filing_date": record["filingDate"], "acceptance_time": record["acceptanceDateTime"],
                        "source": reference(source), "baseline_execution_filing": baseline,
                        "target_mentions": mentions, "amendment_keyword_occurrences": len(amendment_words),
                        "initial_disposition": disposition,
                        "context_review": manual_context.get(accession)})
        if index % 20 == 0:
            print(f"Screened {index}/{len(selected)} archived SEC primary documents", flush=True)

    rate_url = "https://markets.newyorkfed.org/api/rates/secured/sofrai/search.json?startDate=2024-04-01&endDate=2026-10-02"
    rate_source, raw = retrieve(rate_url, "sofr_averages_2024_2026.json.gz", "official_sofr_averages",
                               start_date="2024-04-01", end_date=CUTOFF)
    rates = json.loads(raw, parse_float=Decimal)["refRates"]
    by_date = {r["effectiveDate"]: r for r in rates if r["type"] == "SOFRAI"}
    dates = sorted(by_date)
    certificates = json.loads((ROOT / "data/actual_certificates.json").read_text(encoding="utf-8"))["certificates"]
    rate_checks = []
    prior = "2025-05-02"
    for certificate in certificates:
        if certificate["deal_id"] != "CAOT-2025-2":
            continue
        prior_business_dates = [d for d in dates if d < prior]
        reset_date = prior_business_dates[-2]
        rate = by_date[reset_date]["average30day"]
        observed = Decimal(certificate["replay_inputs"]["floating_note_rate"]) * 100
        expected = max(Decimal("0"), rate + Decimal("0.69"))
        source_label = certificate["source_rows"]["15"]["label"]
        displayed = Decimal(re.search(r"\|\s*(\d+\.\d+)\s*\|\s*%", source_label)[1])
        rate_checks.append({"deal_id": "CAOT-2025-2", "distribution_date": certificate["distribution_date"],
                            "accrual_start": prior, "accrual_end_exclusive": certificate["distribution_date"],
                            "sofr_adjustment_date": reset_date, "previous_government_business_date": prior_business_dates[-1],
                            "official_average30day_percent": str(rate), "spread_percent": "0.69",
                            "expected_coupon_percent": str(expected), "observed_coupon_percent": str(observed),
                            "coupon_residual_percentage_points": str(observed - expected),
                            "displayed_average_residual_percentage_points": str(displayed - rate),
                            "status": "EXACT_MATCH" if observed == expected and displayed == rate else "DIFFERENCE",
                            "official_revision_indicator": by_date[reset_date].get("revisionIndicator"),
                            "source_rate_label": source_label, "certificate_url": certificate["source_url"],
                            "certificate_original_sha256": certificate["source_sha256"]})
        prior = certificate["distribution_date"]
    assert len(rate_checks) == 17

    calendar_sources = []
    for url, filename, kind in [
        ("https://www.sifma.org/news/press-releases/sifma-fixed-income-market-close-recommendations-in-the-u-s-the-u-k-and-japan-for-u-s-columbus-day-and-japan-health-and-sports-day-holidays-2025", "sifma_columbus_day_2025.htm.gz", "official_government_securities_holiday_confirmation"),
        ("https://www.sifma.org/resources/general/holiday-schedule", "sifma_holiday_schedule_2026.htm.gz", "official_government_securities_holiday_schedule"),
        ("https://www.newyorkfed.org/markets/reference-rates/sofr-averages-and-index", "nyfed_sofr_average_methodology.htm.gz", "official_sofr_publication_methodology"),
    ]:
        source, raw = retrieve(url, filename, kind)
        calendar_sources.append(reference(source))

    supplemental = downloader.manifest["sources"]
    for source in supplemental:
        verify_archive(ROOT / source["archive_path"], source)
    manifest_bytes = REVIEW_MANIFEST.read_bytes()
    import hashlib
    verification = {"status": "PASS", "source_count": len(supplemental),
                    "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                    "verified_at_utc": datetime.now(timezone.utc).isoformat(),
                    "original_and_archive_bytes": "independently reread and verified",
                    "sources": [{"url": s["url"], "original_sha256": s["sha256_original_bytes"],
                                 "archive_sha256": s["sha256_archive"], "status": "PASS"} for s in supplemental]}
    (ROOT / "data/rate_amendment_source_verification.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    result = {"schema_version": 1, "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
              "review_cutoff_utc_date": CUTOFF, "core_manifest_frozen": "data/source_manifest.json",
              "supplemental_manifest": "data/rate_amendment_source_manifest.json",
              "supplemental_source_verification": verification,
              "amendment_inventory": inventory, "primary_document_screens": screens,
              "screen_scope_limit": "All indexed forms for four returned filers in execution-to-cutoff windows are inventoried; all trust primaries and specified depositor/parent narrative/registration amendment forms are reviewed. The named sponsor standalone submissions endpoint returned404; related joint filings were reviewed through issuer/depositor inventories. Private notices, unfiled agreements, other filers and future filings are outside scope. Keyword co-occurrence is a candidate, not proof of an amendment.",
              "unavailable_inventory_endpoints": [{"cik":1601902, "role":"CarMax Business Services LLC named sponsor/servicer",
                                                    "url":"https://data.sec.gov/submissions/CIK0001601902.json", "observed_on_utc_date":CUTOFF,
                                                    "http_status":404, "conclusion":"No standalone inventory returned. Not evidence of absence of filings or amendments; joint issuer/depositor filings remain reviewed.",
                                                    "identifier_source_accession":"0001193125-25-111714"}],
              "context_review": manual_context,
              "unreviewed_target_amendment_candidates": sum(s["initial_disposition"] == "TARGET_MENTION_REQUIRES_CONTEXT_REVIEW" for s in screens),
              "amendment_conclusion": "FINITE_PUBLIC_SEARCH_NO_TRANSACTION_AMENDMENT_IDENTIFIED" if not any(s["initial_disposition"] == "TARGET_MENTION_REQUIRES_CONTEXT_REVIEW" for s in screens) else "CONTEXT_REVIEW_PENDING",
              "rate_review": {"official_series": "New York Fed SOFRAI average30day, percent per annum",
                              "source": reference(rate_source), "returned_dates": len(dates),
                              "official_publication_and_calendar_sources": calendar_sources,
                              "first_date": dates[0], "last_date": dates[-1],
                              "executed_terms_source": [reference(s) for s in core_manifest if s.get("accession") == "0001193125-25-111714" and s["url"].endswith("dex991.htm")],
                              "terms": {"AccrualPeriod": "Prior adjusted Distribution Date through but excluding next; initial starts Closing Date 2025-05-02.",
                                        "SOFRAdjustmentDate": "Second U.S. Government Securities Business Day before first day of Accrual Period.",
                                        "CompoundedSOFR": "Published 30-calendar-day compounded SOFR average on adjustment date; preceding available government business day fallback if unavailable.",
                                        "SOFRDeterminationTime": "15:00 America/New_York on adjustment date.",
                                        "ClassA2bRate": "Benchmark plus 0.69 percentage points annually, floored at zero.",
                                        "CalendarMethod": "Observed official SOFRAI publication dates provide the historical government-securities publication calendar; second prior published business date is retained for each reset. SIFMA confirms the intervening October 13, 2025 and February 16, 2026 full closes; early closes are not full-day exclusions. This validates observed reset values, not a future holiday-calendar implementation."},
                              "limitations": "Official history downloaded on review date is not an archived intraday 15:00 snapshot for every historic fixing; benchmark-change notices and any unpublished adjustments remain subject to finite public amendment review. Historic exact match is not a future SOFR path forecast.",
                              "exact_coupon_matches": sum(c["status"] == "EXACT_MATCH" for c in rate_checks),
                              "checks": rate_checks}}
    (ROOT / "data/rate_and_amendment_review.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Inventory: {sum(i['eligible_record_count'] for i in inventory)} filer-records, {len(screens)} unique primary screens; SOFR exact:{result['rate_review']['exact_coupon_matches']}/17; supplemental hashes:{len(supplemental)} PASS", flush=True)


if __name__ == "__main__":
    main()
