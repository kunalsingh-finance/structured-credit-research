# Research design and acceptance gates

## Decision and final deliverable

The completed project should answer: under documented borrower-performance and funding assumptions, which auto-ABS bond classes remain protected, how long is principal outstanding, and what price would make a downside exposure acceptable?

A credit memo is the main professional work product. The model, source inventory, reconciliation workbook and validation pack substantiate its conclusions. The interface makes that evidence inspectable.

## Separate three kinds of evidence

| Evidence | Question | Current state |
| --- | --- | --- |
| Reported-data consistency | Do the certificate's own figures obey its accounting identities? | Two manually extracted development samples |
| Historical contractual replay | Do independently encoded terms reproduce published distributions given observed collateral cash? | Bounded pre-acceleration research implementation; unresolved OC difference |
| Predictive validation | Do estimates made with information available at the time predict later credit and cash-flow outcomes? | Not implemented |

Observed ending collateral and reported cash are legitimate inputs to a historical replay. They are future information for a forecast made before the collection period. Never call a replay a forecast backtest.

## Initial scope and provenance

CarMax Auto Owner Trust 2025-2 has a final prospectus and actual monthly SEC certificates. The fixture contains August and November 2025, separated by two omitted months. No continuity claim is made.

The numbers are manual extractions. Store accession, URL, collection dates, distribution date, source-row mappings and local fixture hashes. An original-document hash must remain unavailable until original bytes are archived. Manual extraction is a research limitation, not an automated ingestion claim.

Principal purchase amounts, finance-charge purchases, advances, arrears and miscellaneous expenses are zero in the two cases. The collection identity groups liquidation receipts with reported recoveries only because the figures agree in these samples; future adapters must reconcile that taxonomy explicitly. Reserve earnings and reserve releases are separate from collection-account income and residual cash.

## Governing-document exception

The prospectus defines target overcollateralization as 0.75% of cutoff collateral. The servicing certificates display a different target amount. Compute the prospectus formula and show the discrepancy. Do not replace it with the published target merely to make the replay pass. Review the executed agreement and subsequent amendments before deciding which rule governs.

Date and percentage labels in the certificates also conflict with their surrounding facts. Keep the source facts and document those exceptions. The reported floating coupon is an observed input. Its rate-date labels remain unresolved until reference-rate and agreement review.

## Bounded replay

The implementation covers fully funded ordinary distributions before final maturities, without acceleration, delinquent interest, unusual fees, repurchases or cleanup calls. It computes servicing, coupons, principal priority tiers, regular principal, sequential allocation with pro rata allocation within A2, reserve maintenance and residual cash.

A1 and A2b use actual distribution-date intervals over360; other coupons use monthly30/360. A2b's numeric reported rate is an input. Prior distribution dates are explicit; November's business-day adjustment cannot be replaced by a fixed30-day interval.

Missing inputs and unsupported branches must produce an explicit error or incomplete status. Every dollar arithmetic operation uses integer cents or exact decimal rates; no tolerance conceals an unexplained difference.

## Data and credit-model gates

Download a small complete source set before scaling. Preserve observed filing acceptance times, report periods, versions and amendments. Do not use pre-offering hypothetical servicing periods as actual post-close performance.

Streaming parsing must verify the actual XML namespace against the SEC schema, count records, detect duplicates and retain missing versus zero semantics. Loan identifiers are scoped to deal. Check aggregate outstanding balance, counts, cash, defaults and recoveries against certificates before modelling.

Default, paid-off, repurchased, missing and censored outcomes require distinct definitions. Repeated charged-off rows cannot become repeated first-default events. Recoveries are period flows, not automatically cumulative recoveries.

Use expanding time splits, development-only fitting and a frozen later test. Withhold deals or vintages for generalization checks; do not split adjacent rows of one loan randomly. Compare default/prepayment hazards with simple cohort and transition baselines. Report discrimination, calibration, uncertainty, segment stability and economic cash-flow error separately.

## Release gates

A completed research release needs consecutive real-data ingestion, resolved or explicitly bounded legal rules, independent later-month replay, a separately evaluated credit model, an auditable scenario engine and a memo whose conclusions match the evidence.

Until then, use development status and state exactly which pieces work. Do not claim production readiness, an official rating, investment alpha or guaranteed hiring outcomes.

