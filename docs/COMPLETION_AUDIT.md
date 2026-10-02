# Completion audit against the original design

Audit date: October 2, 2026; main results inspected at their 12:18:59 UTC
generation, with supplemental diagnostics completed at 08:11:28 UTC.
The reference is the preserved
[INITIAL_RESEARCH_DESIGN.md](INITIAL_RESEARCH_DESIGN.md), not a revised scope.
This audit does not waive a requirement because the implementation is useful,
the data is public, or a model improves one score.

**Overall status: the original completion gates are not yet met.** A functioning
development research platform and populated deliverables exist. The added
internal model diagnostics, observed-coupon review and finite public amendment
inventory are completed. Final artifact freshness, numerical and visual QA
are completed separately from the failed source/legal gates.

## Completed development work

| Original requirement | Evidence and qualification |
| --- | --- |
| Consecutive actual sources and original-byte provenance | 46 deal-months, 3,825,715 loan-month observations, 243 original/archive hash chains verified. Accessions, report dates, acceptance times, source rows and hashes are retained. |
| Streaming, source-faithful ingestion | SEC namespace checks, duplicate rejection, deal-scoped loan IDs, signed cents and missing-versus-zero semantics. Every loan row satisfies the disclosed balance identity. |
| Reported accounting consistency | All 322 certificate identities and 44 inter-month collateral continuity checks pass. These are not tape-to-certificate cash reconciliation. |
| Independent later-month mechanical replay | Sixteen post-stub target months, including seven later months identified separately. All 128 note-interest comparisons match; 118 related principal/OC comparisons remain unequal. Inputs are observed collateral cash, so this is replay rather than forecasting. |
| Development-only fitting and a frozen later test | Fixed training through June 2025, separate September-November calibration, February-August 2026 later-month and same-originator unseen-deal tests. Predictors use prior publicly accepted records. No random split of adjacent loan rows. |
| Distinct reported outcomes and qualified recovery evidence | First-observed default counted once; payoff, maturity, repurchase and censoring distinguished. Reinstated exposure retained. Recoveries treated as flows and a complete-record twelve-month recovery benchmark disclosed. Observation time is not necessarily economic default time. |
| Discrimination, calibration and uncertainty | Event scores/calibration and fixed-model loan-cluster bootstrap intervals exist. Intervals exclude fitting, calibration and common-month macro uncertainty; no broader interval is implied. |
| Separate economic cash error | Public-origin fleets are projected across the undisclosed interval and scored against future certificate defaults, principal, interest and ending collateral. Source mismatch and modeling error are both present. |
| Expanding chronological diagnostics, distinct cohort benchmark and segment reporting | Actual full-panel supplemental study completed with four past-only expanding folds, a fixed-smoothed prior-feature cohort baseline, and 23 observed bands in each test split. These analyses were specified after primary-test inspection and do not alter the primary model. |
| Observed floating-coupon and adjustment-date review | All 17 target-deal coupons agree exactly with official New York Fed 30-day compounded SOFR averages plus the executed 69 bp spread, using the executed reset rule and applicable full-close dates. Ten issuer date labels remain erroneous. The historical API series is evidence of the observed rates, not an independently archived snapshot of every original fixing or a future-rate model. |
| Public post-execution amendment inventory | Four filer inventories contain 444 record occurrences; 171 unique primary documents were archived and screened. No subsequent transaction amendment was identified within the documented finite scope. The sponsor's standalone submissions endpoint returned HTTP 404; private documents, other filers and later filings are outside that conclusion. All 177 supplemental original/archive hash chains pass separately from the frozen performance corpus. |
| Auditable scenarios | Executed payment priorities, reserve support, interest arrears, maturity failure, explicit acceleration/cleanup branches, class loss, paid-principal WAL and a reverse-stress grid. Central/Downside/Severe each pass cash, pool, note-principal and reserve conservation and horizon closure. Unsupported or externally elected states are explicit. |
| Professional deliverables | Final HTML research interface, formula-based XLSX workbook, two-page PDF memo and interview guide match the final results version. Saved workbook has 3,280 cached formulas and no formula errors; four stale-input rejection cases leave outputs unchanged. Final controls and updated rendered views were inspected. |
| Current-state research documentation | README, validation record, data dictionary, cash-flow mechanics and supplemental-study records describe the real-data implementation and its limitations. The original design is preserved independently. New diagnostics are explicitly identified as supplemental studies specified after primary-test inspection. |

The JSON inspected was generated at `2026-10-02T12:18:59.985073+00:00`;
its SHA-256 is
`80394cb846a98088377fcbdc5fd6ac9471359eb20b7c3aa27cd3a6fa742c6686`.
Its eleven recorded research-code hashes matched the corresponding local files.
Both supplemental outputs and their content hashes are embedded in the main
pack. Its original strict source/replay gates remain `FAIL`.
Build success means generation succeeded, not that research gates passed.

## Internal research and delivery checks closed

| Necessary work | Acceptance evidence |
| --- | --- |
| Final artifacts match final results | HTML, PDF and workbook were rebuilt from the final machine results, with matching source hashes. Formula/numerical and cached-file checks pass; updated pages/views and browser controls were inspected. Both external failures and mixed cash forecasts remain prominent. |

The final HTML/PDF and workbook builders record the same results hash
and generation timestamp above. [Artifact verification](../output/artifact_verification.json)
records completed checks and their scope; native Microsoft Excel was not invoked. The
rate and amendment findings are documented in
[RATE_AND_AMENDMENT_REVIEW.md](RATE_AND_AMENDMENT_REVIEW.md). Their completion
does not resolve the OC discrepancy or establish that no unfiled amendment
exists.

The completed supplemental study did not tune the frozen primary model or select a
winning method from the existing test. A method may satisfy the comparison
gate while performing worse. If methods are subsequently changed using these
results, that is further development and requires a new genuinely withheld
evaluation before calling the changed model independently validated.

The supplemental controls pass for public-feature availability, fitted-label
availability, targets before the primary test and probability conservation.
Training sizes expand from 162,876 to 904,502 observations. The complete suite
passes 92 tests. The uncalibrated expanding logistic loses to the delinquency
transition benchmark on default Brier in all four folds, despite higher AUC.
Fixed-segment calibration gaps remain visible. Thus the expanding-comparison
and segment-reporting requirements are completed as descriptive diagnostics;
uniform stability or superiority has not been asserted. See
[SUPPLEMENTAL_VALIDATION.md](SUPPLEMENTAL_VALIDATION.md).

## External evidence needed for unresolved gates

| Gate and current result | Evidence needed to close it |
| --- | --- |
| Exact loan-to-certificate source reconciliation: 287 of 322 comparisons differ | Eligible-loan balance ledger, separate cash/noncash principal reductions, unclipped receipts/reversals, reinstatement/rechargeoff recognition and dated liquidation-cost/interest/principal allocations. Public disclosed fields have not established a unique exact bridge. |
| Latest mapped collateral: $512.01 below certificate principal | Issuer balance/eligibility adjustment evidence or corrected disclosure. Assigning this amount an adverse loss in scenarios does not reconcile it or bound unrelated source errors. |
| Contractual OC: calculated target $76.08 below reported target | Governing amendment, issuer correction or other authoritative explanation. Initial principal is independently supported. Retaining the executed percentage and displaying the difference is honest; substituting the reported target is not resolution. |
| Conflicting certificate dates/percentage labels and missing retired-class cells | Corrected exhibits or authoritative explanation. Source facts and derived chronology remain separately recorded. |
| Exact economic default/recovery timing | Earlier histories and issuer recognition/reinstatement information. The existing model estimates first-observed disclosure risk in its eligible set; translating it into economic defaults remains a scenario assumption. |

The original requirement to check source cash, defaults and recoveries before
modeling has not passed. The existing fits are therefore exploratory qualified
research performed ahead of that unresolved prerequisite. Good software tests,
exact internal arithmetic or an artifact export cannot retroactively pass it.
See [SOURCE_RECONCILIATION.md](SOURCE_RECONCILIATION.md) and
[INDEPENDENT_CASH_BRIDGE_AUDIT.md](INDEPENDENT_CASH_BRIDGE_AUDIT.md).

## What the present results support

In the seven-month unseen-deal cash study, fitted default MAE is approximately
$463,351 versus $607,572 for the constant-hazard baseline, while principal MAE
is approximately $4,505,434 versus $1,209,563. Ending-collateral forecasts are
also worse than that baseline. These are descriptive, metric-specific results
on two deals from one originator, not universal predictive superiority.

Under the specified assumptions, Central and Downside allocate no terminal
note principal impairment; Severe allocates $82,517,599.51. That answers an
illustrative structural stress question. It does not establish that the
assumptions predict an economic cycle or that a security is attractive.

The workbook can calculate value and price thresholds under an explicit
discount assumption. The original design permits documented price assumptions;
a market quote is not required merely to show scenario value. An executable
relative-value or buy recommendation would additionally require independent
market price/spread and liquidity evidence. No such recommendation is made.

## Completion decision

The internal software, diagnostic and documented public-review work is
completed; final artifact QA is the remaining delivery check. Keep development
research status because the external strict source/replay gates remain failed.
Do not convert an issuer-information dependency into a passed gate. The current
deliverables are reviewable research work, not a completed fully validated
release under the original design, an official rating or verified investment
alpha.
