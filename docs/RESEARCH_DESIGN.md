# Research design and acceptance gates

The initial research scope and financial acceptance gates are documented in [INITIAL_RESEARCH_DESIGN.md](INITIAL_RESEARCH_DESIGN.md). This document records the implementation against that scope; it does not relax a failed control.

## Decision and deliverables

Research question: under documented borrower-performance and funding assumptions, which auto-ABS classes remain protected, how long is principal outstanding, and how does assumed purchase price change value?

The deliverables are a two-page credit memo, an inspectable cash-flow workbook, a local interactive report, source manifests and reproducible Python/SQL analysis. The platform is a development research implementation. An executable investment recommendation requires market prices and stronger aggregate cash forecasting.

## Evidence separated

| Evidence | Actual implemented evidence | Current gate |
| --- | --- | --- |
| Certificate consistency | 46 consecutive certificates; 322 exact-cent arithmetic identities and 44 intermonth pool-continuity comparisons | Pass |
| Loan tape accounting | 3,825,715 parsed loan-month rows; namespace/version/NULL controls; independent raw-stream audits | Internal principal identities pass |
| Loan-to-trust cash bridge | 322 tape/certificate comparisons, including balances, counts, principal, interest, defaults and recoveries | 287 differences remain; exact external reconciliation fails |
| Contractual replay | Executed terms, 16 post-stub target-deal periods, chronological later months included | Note interest agrees; 118 related comparisons differ through $76.08 OC exception |
| Conditional borrower model | Older-deal training/calibration; later-month and unseen-deal holdouts, transition baseline, calibration and conditional cluster intervals | Implemented; supplemental cohort/expanding/segment study is explicitly after inspection; economic default-time labeling remains qualified |
| Cash forecasting | Latest publicly available origin fleet projected over the undisclosed bridge; seven future target months per deal | Mixed results; principal/runoff worse than pooled baseline |
| Scenario accounting | Competing events, annuity schedules, delayed recovery flows and stateful waterfall | Cash, pool, note-principal, reserve and horizon checks pass |
| Investment valuation | PV and WAL from actual payment dates; editable workbook discount and purchase-price assumptions | Assumption analysis only; market quote absent |

An observed-cash replay is not a forecast. Conditional loan-event beginning-exposure error is not certificate chargeoff-cash error. Neither a source hash nor an internal accounting identity proves the external cash allocation is correct.

## Source and observation policy

The corpus contains 29 actual collection periods for CAOT-2024-2 (April2024-August2026) and 17 for CAOT-2025-2 (April2025-August2026). Original SEC bytes and compressed archives are independently hashed. Each row retains acceptance time, accession, report period and source version. Canonical data uses first-accepted filings; amendments are retained separately.

Signed raw amounts, missing operands, noncash adjustments and repeated charged-off rows remain source facts. Default is the first observed positive chargeoff/code4 event, not necessarily its effective legal date. Repurchase, voluntary prepayment, scheduled maturity and censored/unknown transfers are distinct. Reinstated loans remain in current positive collateral; their redefault hazard is an explicit assumption.

The issuer's EX103 blends cash and noncash principal reductions and clips some negative payment/recovery amounts. Public fields do not uniquely identify all trust cash allocations. [SOURCE_RECONCILIATION.md](SOURCE_RECONCILIATION.md) and [INDEPENDENT_CASH_BRIDGE_AUDIT.md](INDEPENDENT_CASH_BRIDGE_AUDIT.md) preserve the tested bridges and remaining issuer-evidence requirement.

## Credit and cash models

The frozen retrospective protocol fixes older-deal training through June2025, calibration September-November2025, and February-August2026 tests on both deals. Predictors come from an earlier filing accepted before the target collection month. Outcomes and risk-set eligibility are conditional on observed beginning exposure. No random adjacent-row split or current-period payment predictor is used.

A regularized multinomial model competes default disclosure, prepayment and survival; a development-only calibrator adjusts probabilities. Constant and delinquency-transition baselines remain visible. Loan-cluster intervals condition on fitted models and observed months, excluding common macro, fitting and calibration uncertainty. First-observation recovery cohorts report twelve-month realized cash, not ultimate recovery.

The independent cash diagnostic projects the publicly known prior ending fleet over the unknown bridge. Its model and constant baseline share contractual-term/APR annuity and collection-factor assumptions. Only event hazards differ. Future certificate cash grades the prediction; it is not substituted into its inputs. Recovery calibration excludes 2026 outcomes. Better default/interest errors alongside poorer principal/runoff errors prevent a general model-superiority claim.

## Contract and scenario boundaries

Executed agreements govern encoded priorities. Reserve eligibility, interest arrears, maturity floors, two acceleration categories and cleanup conditions have explicit tests. Issuance stub, automatic remedy election and qualified fee-cap determination are outside the current adapter. The separate rate review reconstructs all seventeen observed floating coupons from official New York Fed averages and executed reset terms; a future rate path is not forecast. Missing and unsupported conditions fail explicitly.

The executed 0.75% cutoff OC formula remains $76.08 below the reported target. The difference is quantified throughout replay; reported targets never overwrite the formula. The latest mapped collateral is $512.01 below certificate principal. Its immediate full-loss treatment is an adverse convention, not a general bound on every possible price or the other cash discrepancies.

WAL is unavailable for retired, impaired or incomplete classes; paid-principal WAL is a separate measure. Terminal economic impairment is not paid cash or an official legal writeoff. The reverse stress evaluates an ordered joint-shock grid; it does not assume monotonicity or claim a precise break-even between grid points.

## Original release gate retained

> A completed research release needs consecutive real-data ingestion, resolved or explicitly bounded legal rules, independent later-month replay, a separately evaluated credit model, an auditable scenario engine and a memo whose conclusions match the evidence.

The exact loan-to-certificate and replay gates remain failed. The expanded software and artifacts are inspectable, but the full original research scope is not represented as fully validated. `run_platform.py --require-exact-reconciliation` returns exit2 while those differences remain. Development status stays visible in all outputs.

