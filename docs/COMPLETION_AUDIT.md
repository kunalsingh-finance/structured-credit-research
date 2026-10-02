# Completion audit against the original design

Audit date: October 2, 2026; main results inspected at their 13:17:08 UTC
generation, with supplemental diagnostics completed at 08:11:28 UTC.
The reference is the preserved
[INITIAL_RESEARCH_DESIGN.md](INITIAL_RESEARCH_DESIGN.md), not a revised scope.
This audit does not waive a requirement because the implementation is useful,
the data is public, or a model improves one score.

**Overall status: the original completion gates are not yet met.** A functioning
development research platform and populated deliverables exist. The added
internal model diagnostics, observed-coupon review and finite public amendment
inventory are completed. The cumulative A2 principal-rounding correction and
separate conditional OC sensitivity are completed. Current-version artifact
freshness, numerical and visual QA pass separately from the failed source/legal
gates; their evidence is bound to the current results version.

## Completed development work

| Original requirement | Evidence and qualification |
| --- | --- |
| Consecutive actual sources and original-byte provenance | 46 deal-months, 3,825,715 loan-month observations, 243 original/archive hash chains verified. Accessions, report dates, acceptance times, source rows and hashes are retained. |
| Streaming, source-faithful ingestion | SEC namespace checks, duplicate rejection, deal-scoped loan IDs, signed cents and missing-versus-zero semantics. Every loan row satisfies the disclosed balance identity. |
| Reported accounting consistency | All 322 certificate identities and 44 inter-month collateral continuity checks pass. These are not tape-to-certificate cash reconciliation. |
| Independent later-month mechanical replay | Sixteen post-stub target months, including seven later months identified separately. All 128 note-interest comparisons match; 118 related principal/OC comparisons remain unequal. Cumulative A2 allocation removes a partition-dependent rounding error. A separately labeled reported-target counterfactual matches all 592 comparisons; that does not establish which OC target governs. Inputs are observed collateral cash, so this is replay rather than forecasting. |
| Development-only fitting and a frozen later test | Fixed training through June 2025, separate September-November calibration, February-August 2026 later-month and same-originator unseen-deal tests. Predictors use prior publicly accepted records. No random split of adjacent loan rows. |
| Distinct reported outcomes and qualified recovery evidence | First-observed default counted once; payoff, maturity, repurchase and censoring distinguished. Reinstated exposure retained. Recoveries treated as flows and a complete-record twelve-month recovery benchmark disclosed. Observation time is not necessarily economic default time. |
| Discrimination, calibration and uncertainty | Event scores/calibration and fixed-model loan-cluster bootstrap intervals exist. Intervals exclude fitting, calibration and common-month macro uncertainty; no broader interval is implied. |
| Separate economic cash error | Public-origin fleets are projected across the undisclosed interval and scored against future certificate defaults, principal, interest and ending collateral. Source mismatch and modeling error are both present. |
| Expanding chronological diagnostics, distinct cohort benchmark and segment reporting | Actual full-panel supplemental study completed with four past-only expanding folds, a fixed-smoothed prior-feature cohort baseline, and 23 observed bands in each test split. These analyses were specified after primary-test inspection and do not alter the primary model. |
| Observed floating-coupon and adjustment-date review | All 17 target-deal coupons agree exactly with official New York Fed 30-day compounded SOFR averages plus the executed 69 bp spread, using the executed reset rule and applicable full-close dates. Ten issuer date labels remain erroneous. The historical API series is evidence of the observed rates, not an independently archived snapshot of every original fixing or a future-rate model. |
| Public post-execution amendment inventory | Four filer inventories contain 444 record occurrences; 171 unique primary documents were archived and screened. No subsequent transaction amendment was identified within the documented finite scope. The sponsor's standalone submissions endpoint returned HTTP 404; private documents, other filers and later filings are outside that conclusion. All 177 supplemental original/archive hash chains pass separately from the frozen performance corpus. |
| Auditable scenarios | Executed payment priorities, reserve support, interest arrears, maturity failure, explicit acceleration/cleanup branches, class loss, paid-principal WAL and a reverse-stress grid. Central/Downside/Severe each pass cash, pool, note-principal and reserve conservation and horizon closure. Unsupported or externally elected states are explicit. |
| Conditional legal-input sensitivity | All sixteen primary historical ledgers and the three full scenario ledgers reproduce exactly. Verified executed sources and independent rational A2 arithmetic support the calculation. The reported-dollar OC alternative changes Central aggregate note PV by $7.89624870 at 8%; Downside and Severe cash flows are unchanged. Terminal principal losses, unpaid-interest claims and maturity flags are unchanged at both endpoints. This conditional path analysis does not resolve the governing rule or bound arbitrary paths. |
| Professional deliverables | HTML research interface, formula-based XLSX workbook, two-page PDF memo and interview guide match the current results version. Saved workbook has 3,280 cached formulas and no formula errors; five stale-input rejection cases leave outputs unchanged. All nine rebuilt workbook previews, both PDF pages, browser controls and the OC evidence card were inspected; browser errors are absent. Acceptance is recorded separately in artifact_verification.json. |
| Current-state research documentation | README, validation record, data dictionary, cash-flow mechanics and supplemental-study records describe the real-data implementation and its limitations. The original design is preserved independently. New diagnostics are explicitly identified as supplemental studies specified after primary-test inspection. |

The JSON inspected was generated at `2026-10-02T13:17:08.124031+00:00`;
its SHA-256 is
`f560aaa291e553a66fe61460c832201e34c44d4c865b97615e215fb8b6088107`.
Its eleven recorded research-code hashes matched the corresponding local files.
Both supplemental outputs and their content hashes are embedded in the main
pack. Its original strict source/replay gates remain `FAIL`.
Build success means generation succeeded, not that research gates passed.

## Internal research and delivery checks closed

| Necessary work | Acceptance evidence |
| --- | --- |
| Final artifacts match final results | HTML, PDF and workbook were rebuilt from current machine results with matching source hashes. Numerical/cached-file checks and fresh visual/browser evidence pass against the current version in the artifact record. External failures and mixed cash forecasts remain prominent. |
| A2 rounding correction | Principal allocation uses fixed opening A2 weights and one cumulative monthly rounded target across principal tiers and reserve-extra regular principal. Three independent small-cent regressions cover partition invariance, reserve splitting and class caps. An independent review checked 132,650 rational rounding, monotonicity, cap and conservation states. |
| Conditional OC consequence analysis | The standalone study independently verifies original/compressed executed-source bytes, primary code/results freshness, exact ledger reproduction, aggregate A2 allocation and Decimal PV/WAL. Its seven focused controls reject stale/incomplete inputs and unsupported states. The generated study and report pass freshness verification against the current primary SHA. |

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
passes 113 tests. The uncalibrated expanding logistic loses to the delinquency
transition benchmark on default Brier in all four folds, despite higher AUC.
Fixed-segment calibration gaps remain visible. Thus the expanding-comparison
and segment-reporting requirements are completed as descriptive diagnostics;
uniform stability or superiority has not been asserted. See
[SUPPLEMENTAL_VALIDATION.md](SUPPLEMENTAL_VALIDATION.md).

The separate [conditional OC sensitivity](OC_SENSITIVITY.md) was specified
after primary-result inspection. It preserves the executed formula and all
strict primary gates. Each historical comparison resets to the certificate's
reported opening balances; those period deltas are not one propagated history.
Scenario comparisons propagate two independent note states on identical
collateral paths from September 15, 2026. Central paid note cash decreases by
$14.30, residual distributions decrease by $62.15 and reserve releases increase
by $76.45 under the reported-dollar target. Note PV increases by $7.89624870
because principal timing changes; only paid cash is discounted. The largest
class price change is D's +0.000001978871 per $100, and its Central contractual
WAL changes by -0.000001358129 years. Downside and Severe cash flows are identical.
No class's terminal principal loss, unpaid-interest claim or maturity flag
changes between endpoints. These results do not prove a uniform bound over
intermediate targets, arbitrary collateral paths, rates or trigger changes.

## External evidence needed for unresolved gates

| Gate and current result | Evidence needed to close it |
| --- | --- |
| Exact loan-to-certificate source reconciliation: 287 of 322 comparisons differ | Eligible-loan balance ledger, separate cash/noncash principal reductions, unclipped receipts/reversals, reinstatement/rechargeoff recognition and dated liquidation-cost/interest/principal allocations. Public disclosed fields have not established a unique exact bridge. |
| Latest mapped collateral: $512.01 below certificate principal | Issuer balance/eligibility adjustment evidence or corrected disclosure. Assigning this amount an adverse loss in scenarios does not reconcile it or bound unrelated source errors. |
| Contractual OC: calculated target $76.08 below reported target | Governing amendment, issuer correction or other authoritative explanation. Initial principal is independently supported. The conditional reported-target alternative quantifies consequences on fixed paths; substituting that target still does not resolve the rule or pass the primary gate. |
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
completed, including current-version artifact QA. Keep development
research status because the external strict source/replay gates remain failed.
Do not convert an issuer-information dependency into a passed gate. The current
deliverables are reviewable research work, not a completed fully validated
release under the original design, an official rating or verified investment
alpha.

## Current public dependency recheck

At `2026-10-02T13:24:57.533894+00:00`, the
[separate dependency recheck](../output/release_dependency_recheck.json)
retrieved the four covered SEC submissions inventories, the target EX-103 and
the latest target servicing certificate. All six returned exactly the same
original bytes as the frozen review sources. No new accession appeared in
those four current inventories. The sponsor endpoint again returned HTTP 404;
its inventory remains a scope gap. The newly retrieved bytes are archived
separately with original and compressed hashes.

This check found no changed evidence within those endpoints. It does not
establish that no other public or private allocation evidence exists. A unique
exact cash bridge has not been established from the archived disclosed fields;
issuer/servicer allocation records, corrected disclosures or an authoritative
public bridge remain necessary to close the original financial gates. The
independent follow-up audit confirmed the current results hash and all eleven
recorded research-code hashes. The A2 correctness fix and conditional OC study
close internal calculation and consequence-analysis omissions; they supply no
issuer allocation ledger, corrected disclosure or authoritative OC explanation.

Run `python scripts/recheck_release_dependencies.py` to repeat this finite
check without changing the performance corpus, fitted model or scenarios.
Unavailable endpoints remain unverified; newly indexed or changed sources
require independent review and cannot automatically pass a release gate.
