# Validation record

Local checks used Python3.11 on Windows on October2,2026. The saved output is development research with unresolved source exceptions; build SUCCESS refers to successful generation, not passed research gates.

## Reproduction and software checks

```powershell
python -m unittest discover -s tests -v
python scripts/run_platform.py
python scripts/run_extended_validation.py
python scripts/run_platform.py --credit-cache --include-supplements --require-exact-reconciliation
python scripts/run_research.py --output-dir output/bounded_fixture
```

**113 tests pass.** They cover exact arithmetic, unsupported/missing inputs, cent/date validation, cash/debt/pool/reserve conservation, legal branch priorities, interest arrears, maturity failure, cleanup conditions, complete terminal runoff, source parsing and version semantics, first-event/censoring definitions, disclosure-time feature joins, recovery-flow queues and failed-build invalidation. Added controls cover tier-partition-independent A2 rounding, immutable source restoration, conditional OC study freshness and portable-release integrity.

Forecast-origin tests perturb unfiled loan balances/defaults and later actual cash. The forecasts remain unchanged while scoring outcomes change. A source certificate accepted after the origin is rejected. Cash predictions retain source acceptance, bridge length, payment date and all model assumptions.

The full platform run succeeds locally. Its strict exact-reconciliation option raises exit2 after saving the development evidence. Cache identity includes panel SHA, source/protocol/certificate identities, model code, cash-validation code and projection code. Release hashes identify every Python research module and runner.

The old offline two-certificate fixture remains isolated in `output/bounded_fixture`: 14/14 arithmetic checks pass, with 14 related replay differences. It is not substituted for the full data run. GitHub Actions is configured on Windows/Linux but has not run remotely.

## Source and contractual controls

- 243 public sources: original and compressed byte counts/SHA-256 verification pass; 11,853,294,034 original bytes and 794,902,963 archived bytes verified.
- 46 consecutive actual certificates/tapes: 29 older-deal and 17 target-deal periods; 3,825,715 canonical loan-month rows.
- 322/322 certificate arithmetic checks and 44/44 intermonth certificate pool-continuity identities agree exactly.
- Every panel row satisfies its source principal rollforward; independent original-XML audits also validate total-paid components on two periods.
- 287/322 loan-to-certificate comparisons remain unequal. Exact external reconciliation fails; blended cash/noncash definitions prevent a unique bridge from current public evidence.
- 16 target-deal post-stub replay periods: all 128 note-interest comparisons agree. 118 related principal/OC comparisons differ through the same $76.08 contractual-versus-reported OC exception.
- Latest positive loan exposure $744,970,252.15 versus certificate pool $744,970,764.16 leaves $512.01 unexplained. Positive loan count 47,562 agrees. Immediate full loss of that residual is only an adverse scenario convention.

Original-byte evidence, tested adjustments and issuer evidence needed are documented in [SOURCE_RECONCILIATION.md](SOURCE_RECONCILIATION.md) and [independent audit](INDEPENDENT_CASH_BRIDGE_AUDIT.md). No normalized adjustment silently repairs a source difference.

The A2 engine rounds the cumulative monthly principal payment using opening class weights. Regression checks show that splitting one payment across priority tiers cannot change its final allocation. A separate hypothetical reported-target replay matches all 592 historical comparisons across the same 16 certificates. The executed-formula primary replay retains its 118 differences. Under identical collateral paths and separately propagated note state, the alternate target changes Central aggregate note PV by $7.89624870 at 8%; Downside and Severe cash flows are unchanged. Principal losses, interest claims and maturity flags are unchanged at the two tested target endpoints. This study does not establish a bound across intermediate targets, other paths or yields, or determine the governing legal rule. See [OC_SENSITIVITY.md](OC_SENSITIVITY.md).

## Predictive evidence

The fixed retrospective split has 904,502 training, 151,482 calibration, 293,318 later-month and 377,266 unseen-deal eligible loan-month observations. Test data is excluded from model/calibrator fitting. The unseen deal shares the same originator; this does not establish other-originator portability.

Later-month first-observed default Brier is 0.002522 versus 0.003180 constant baseline; unseen-deal Brier is 0.000867 versus 0.001094. AUC is approximately 0.978 and 0.981. These are conditional disclosure-event scores, not verified economic default-date forecasts. Of 4,526 first-observed defaults in the full panel, 1,032 have earlier effective months and 19 occur at a corpus boundary.

Actual servicing-cash MAE, February-August2026, seven months per deal:

| Deal / quantity | Constant baseline | Calibrated model |
| --- | ---: | ---: |
| 2024-2 defaults | $1,103,932 | $831,886 |
| 2024-2 principal collections | $882,335 | $4,028,682 |
| 2024-2 interest collections | $96,596 | $89,490 |
| 2024-2 ending pool | $2,261,214 | $6,414,071 |
| 2025-2 defaults | $607,572 | $463,351 |
| 2025-2 principal collections | $1,209,563 | $4,505,434 |
| 2025-2 interest collections | $153,078 | $121,737 |
| 2025-2 ending pool | $1,617,794 | $8,221,060 |

The fitted model improves default/interest MAE and worsens principal/runoff MAE in both deals. Seven serial months permit descriptive comparison, not broad statistical superiority. Cash errors include disclosure-timing, source-taxonomy and projection error. Four supplemental past-only expanding folds, a smoothed cohort benchmark and 23 borrower-segment bands per frozen split are now reported. Their protocol was specified after primary test inspection; the primary model/scenarios remain unchanged. The expanding logistic loses default Brier to the transition baseline in all four folds. Exact effective-time labeling remains qualified. See SUPPLEMENTAL_VALIDATION.md.

## Scenario and artifact checks

Central, Downside and Severe scenarios close collateral/recovery horizons and pass exact cash, pool, note-principal and reserve conservation. Terminal note-principal impairment is respectively $0, $0 and $82,517,599.51. The ordered reverse-stress grid first breaches D at severity2 under a joint shock; this is not a uniquely identified default-only threshold.

Valuation origin is September15,2026. Discount8% and the latest disclosed floating coupon held flat are assumptions. No executable quote, SOFR path validation, investment alpha or official rating is claimed.

The separate reference-rate review reconstructs all17 observed floating coupons exactly from official New York Fed30-day compounded averages plus the executed0.69% spread and adjustment-date rule. Ten stale7/14/2024 labels are issuer-label errors. The amendment review covers444 records across four returned filer inventories and171 unique primary-document screens; three candidates reference original agreements. No transaction amendment was identified within the finite covered scope. A sponsor submissions endpoint returned404 and remains a disclosed scope gap. All177 supplemental original/archive hash chains pass separately from the frozen243-source core. See [RATE_AND_AMENDMENT_REVIEW.md](RATE_AND_AMENDMENT_REVIEW.md).

Artifact builders require a matching SUCCESS status file, results SHA-256 and generation timestamp. Final verification is recorded in `output/artifact_verification.json`: 3,280 cached formulas, zero saved formula errors, five input validations, retained chart, two PDF pages and five rejected stale-input cases, including a stale conditional OC study. Fresh previews of all nine workbook sheets, both memo pages and browser controls were inspected. Native Microsoft Excel was not invoked. The workbook's price/yield/class/scenario controls recalculate saved schedules; changing borrower-credit assumptions requires a Python rebuild.

The portable ZIP preserves the saved research status and excludes the large raw panel and authoring runtimes. Its standard-library packager verifies every included file, embedded dashboard results and local link against the release manifest. See [RELEASE.md](RELEASE.md) for inspection and independent integrity checks.

## Authorship

Codex assisted with research, implementation, validation and documentation. The work is a portfolio research project. It does not claim candidate mastery, production ownership, employment experience or fully passed research gates.

