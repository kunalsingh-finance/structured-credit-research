# Structured Credit Risk and Cash-Flow Platform

An inspectable auto-ABS research project connecting public loan disclosures, borrower-event models, executed payment priorities and bond-level stress results. The case study is CarMax Auto Owner Trust 2025-2, with the older 2024-2 deal used for model development.

**Research status: development with unresolved source exceptions.** The platform runs on 3,825,715 actual loan-month observations across 46 consecutive deal-months. All 322 certificate accounting identities pass. Exact loan-tape cash reconciliation and contractual replay do not fully pass; the dashboard and strict gate preserve those differences.

## Inspect the work

- `output/research_report.html`: interactive collateral, forecast, waterfall, stress and source review.
- `output/outputs/credit_research/cashflow_workbook.xlsx`: formula-based payment valuation, WAL, scenario/class selection and audit schedules.
- `output/pdf/credit_memo.pdf`: two-page credit research memo with results and material limitations.
- [Interview guide](docs/interview_guide.md): project walkthrough, questions and defensible claims.
- [Validation record](docs/VALIDATION.md), [research gates](docs/RESEARCH_DESIGN.md), [data dictionary](docs/DATA_DICTIONARY.md) and [cash-flow mechanics](docs/CASHFLOW_ENGINE.md).
- [Supplemental model study](docs/SUPPLEMENTAL_VALIDATION.md) and [rate/amendment review](docs/RATE_AND_AMENDMENT_REVIEW.md): additional evidence, with retrospective and finite-search limits stated.

## What a reviewer can test

The source pipeline archives and hashes SEC originals, streams ABS-EE XML into SQLite, retains missing versus zero values and separates first-accepted versions from amendments. Public filing times control feature availability. A regularized multinomial model estimates conditional first-observed default disclosure and prepayment risk, with separate calibration and chronological/unseen-deal holdouts.

The stateful engine applies the executed agreement's payment priorities, tracks unpaid interest, reserve draws and releases, tests maturity failures, and explicitly models acceleration and optional-purchase branches. Every scenario checks cash, collateral, note-principal and reserve conservation. Pricing uses disclosed cash flows and an assumed discount rate.

## Main findings

| Result | Evidence |
| --- | --- |
| Internal certificate accounting | 322 of 322 exact-cent checks pass across 46 certificates |
| Loan/certificate comparisons | 287 of 322 comparisons remain unequal; blended cash/noncash source fields prevent an exact cash bridge |
| Historical payment replay | 16 post-stub 2025-2 months; 128 note-interest comparisons agree; 118 related principal/OC comparisons differ through the same $76.08 OC definition exception |
| Unseen-deal cash holdout, seven months | Default MAE $463,351 versus baseline $607,572; principal MAE $4,505,434 versus baseline $1,209,563 |
| Scenario note-principal impairment | Central $0; Downside $0; Severe $82,517,599.51 under specified assumptions |
| Opening collateral mismatch | $512.01 remains unexplained and is assigned immediate full loss as a separate adverse scenario assumption |

Better borrower-risk scores do not imply better runoff forecasts. Both deals' principal and ending-pool forecasts are worse than the constant-hazard baseline. Central and stress scenarios are illustrative research, not validated investment forecasts. The 8% discount rate and flat floating coupon are assumptions; market-price data is absent.

Four supplemental expanding-time folds, a smoothed cohort benchmark and fixed borrower segments retain mixed results: the fresh logistic has worse default Brier than the delinquency-transition baseline in every fold. This study was specified after inspecting the primary test and does not select or change the primary model. All seventeen observed floating coupons independently match official New York Fed averages plus the executed spread. A finite public amendment inventory and 177 separately hashed reference files are documented; no transaction amendment was identified within that scope, and an unavailable sponsor endpoint remains visible.

## Reproduce

Python 3.11+, dependencies in `requirements.txt`. Install in an environment you control:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Acquire the public sources using a real SEC-compliant identity, then build the full panel and research results:

```powershell
python scripts/acquire_data.py --help
python scripts/build_panel.py --help
python scripts/run_platform.py
```

Raw sources and the approximately 1.19 GB SQLite panel are excluded from Git. The saved source manifests contain URLs, acceptance times, original/archive SHA-256 hashes and byte counts. See the data dictionary for acquisition details. No credentials or fabricated contact identity belong in the repository.

A matching `--credit-cache` reuses model and cash-validation results only when panel, source, protocol, certificate and modeling-code identities agree. Failed builds invalidate the machine-readable results. Build success means generation succeeded; it does not mean research gates passed.

```powershell
python scripts/run_extended_validation.py
python scripts/run_platform.py --credit-cache --include-supplements --require-exact-reconciliation
```

The strict command currently exits **2** because the external reconciliation/replay differences remain. It never substitutes reported outputs into the model to force a pass.

The original small, offline evidence fixture is preserved:

```powershell
python scripts/run_research.py --output-dir output/bounded_fixture
```

Do not run the old runner into the main `output` directory after building the full dashboard. Use `python scripts/build_artifacts.py` for the full HTML/PDF, and the bundled Node/artifact-tool runtime for `scripts/build_workbook.mjs`; the workbook builder requires `@oai/artifact-tool` and its documented runtime. Yield and price inputs recalculate in Excel. Borrower-credit assumptions require a Python rebuild.

## Source and authorship

[Final prospectus](https://www.sec.gov/Archives/edgar/data/2063979/000119312525099841/d30805d424b5.htm), [executed sale/servicing agreement](https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex991.htm) and [executed indenture](https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex41.htm). Every machine output includes provenance to the relevant SEC filings.

This is an independent portfolio research project built with Codex assistance. It does not represent employment experience, issuer affiliation, an official rating or demonstrated investment alpha. The candidate should understand and reproduce the work before claiming personal mastery.

