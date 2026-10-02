# SEC source and loan-panel dictionary

The source inventory freezes public filings accepted on or before October 2,
2026. CarMax Auto Owner Trust 2024-2 contributes 29 consecutive collection
months, April 2024 through August 2026; CarMax Auto Owner Trust 2025-2 contributes
17, April 2025 through August 2026. Each period has an actual 10-D certificate
and an ABS-EE loan tape. Pre-offering hypothetical pools are excluded.

`data/source_manifest.json` identifies the URL, accession, report period,
verbatim SEC API acceptance timestamp, retrieval timestamp, original-byte size
and SHA-256, compressed archive size and SHA-256. `scripts/verify_sources.py`
independently decompresses and rereads every archived source. A hash verifies
byte fidelity, not the accuracy of the issuer's facts.

The official SEC ABS XML specification version 1.9 and its AutoLoan XSD are
archived. The observed root namespace is
`http://www.sec.gov/edgar/document/absee/autoloan/assetdata`; records are repeated
`assets` elements. Parsing checks that namespace, repeated loan-period IDs and
nonrepeatable field duplication. XSD repeatable zero-balance and modification
codes are retained as multiple codes. This is a schema-informed adapter, not a
claim of complete XSD conformance validation.

## Normalized panel

`data/loan_panel.sqlite` stores `loan_month` with primary key
`(deal_id, loan_id, period_end)`. Identifiers are scoped to a deal. `loan_amendment`
retains amended versions separately; the canonical panel freezes the first
accepted actual filing for each month. `ingested_source` supplies per-accession
source hashes, record counts and omitted-field counts. No amendment is silently
substituted into a historical observation.

| Panel column | Actual SEC XML field or transformation |
| --- | --- |
| `period_start`, `period_end` | `reportingPeriodBeginningDate`, `reportingPeriodEndingDate` |
| `acceptance_time` | Actual ABS-EE SEC submission API acceptance timestamp |
| `original_balance_cents` | `originalLoanAmount` |
| `begin_balance_cents`, `end_balance_cents` | `reportingPeriodBeginningLoanBalanceAmount`, `reportingPeriodActualEndBalanceAmount` |
| `principal_paid_cents`, `interest_paid_cents` | `actualPrincipalCollectedAmount`, `actualInterestCollectedAmount` |
| `other_principal_adjustment_cents` | `otherPrincipalAdjustmentAmount`, including signed reinstatements/returned principal |
| `chargeoff_cents`, `recovery_cents` | `chargedoffPrincipalAmount`, `recoveredAmount` |
| `scheduled_payment_cents`, `scheduled_principal_cents` | `reportingPeriodScheduledPaymentAmount`, `scheduledPrincipalAmount` |
| `credit_score` | `obligorCreditScore`; co-obligor averages can be fractional; `NONE` becomes NULL |
| `delinquency_days` | `currentDelinquencyStatus`; period-end information unavailable until acceptance |
| `age_months` | Reporting month minus `originationDate` month |
| `remaining_months`, `maturity_month` | `remainingTermToMaturityNumber`, `loanMaturityDate`; current reporting information |
| `orig_ltv_pct` | 100 times `originalLoanAmount / vehicleValueAmount`; a sales-price ratio, not an independently appraised LTV |
| `interest_rate_pct` | 100 times `reportingPeriodInterestRatePercentage`; source fraction0.0814 becomes8.14 percentage points |
| `payment_to_income_pct` | 100 times `paymentToIncomePercentage`; application income is not independently verified income |
| `state` | `obligorGeographicLocation`, current obligor address state |
| `zero_balance_code`, `zero_balance_month` | `zeroBalanceCode` (pipe-separated when multiple), `zeroBalanceEffectiveDate` |
| `liquidation_date` | NULL; a zero-balance effective month is not an exact collateral liquidation date |

All monetary columns use integer cents and preserve source signs. Real tapes
contain small negative credit balances and negative principal adjustments.
Omission remains SQL NULL, distinct from a source-reported0. Optional charge-off
and recovery fields are not filled with invented zeros in the normalized table.

## Outcome definitions

The official zero-balance enumeration is1 prepaid or matured,2 third-party
sale,3 repurchased or replaced,4 charged off,5 servicing transfer,99 unavailable.

- First default is the first observed positive charge-off amount or code4 for a
  loan. Repeated charged-off rows and later reinstatements are not new first
  defaults. The observation period and issuer effective month remain separate.
- Prepayment requires code1, a current-month effective date, positive beginning
  balance, a nonpositive ending balance and maturity after the reporting month.
  Prior defaults and code3/4 combinations are excluded. `prepayment_cents`
  records the principal collected on the payoff row, which includes that row's
  scheduled component; it is not a separately reported partial-prepayment flow.
- Maturity uses code1 at or after scheduled maturity. Repurchase uses code3.
  Sale, transfer, unavailable codes, missing rows and end of the observation
  window are censoring/other termination evidence, not inferred prepayments.
- Recovery amounts are monthly flows, per the issuer's explanatory exhibit.
  They may recur over many post-default months. Do not subtract them as if they
  were cumulative totals or count repeated charge-off balances as fresh losses.

Features for a forecast at a month start must come from an earlier filing with
`acceptance_time <= month_start`. The reporting period itself is not public
availability. Contemporaneous ending balances, delinquency and actual payments
are outcomes, never predictors for that same month.

## Certificate extraction and reconciliation

`data/actual_certificates.json` preserves numbered source rows, exact amounts,
source hashes and payout-class details. It does not overwrite the two original
manual fixtures. All46 certificates pass the seven existing exact accounting
identities (322 checks). Those checks concern the certificate's own arithmetic;
they do not establish agreement with every loan-tape cash field.

Some June/July2025 certificate headers repeat May15 as their distribution
date. The parser retains `source_reported_distribution_date`, uses the dated
SEC exhibit filename for chronology, and flags that source-label exception.
Those same headers also repeat the April collection period and determination
date. `source_header` preserves all three labels; the actual SEC10-D report
period and corresponding ABS-EE record dates supply collection chronology.
January–March2026 2024-2 retired A2 interest cells contain a literal U+FFFD
replacement character. Those class amounts remain missing; aggregate interest
is reconstructed from reported total note deposits less reported principal.

`data/panel_summary.json` shows raw aggregate values and every comparison
residual. Outstanding pool balances sum strictly positive loan balances;
negative customer credit balances are not outstanding receivables. Counts
include strictly positive ending balances. No scaling forces a match.

For August2026, the 2025-2 tape has47,562 positive-balance loans, exactly the
certificate's count. Its positive ending principal is$744,970,252.15 versus
$744,970,764.16 in the certificate: an unresolved difference of-$512.01.
The source-explanatory exhibit also states that tape principal can include
non-cash reductions and that negative adjustments include returned payments
and reinstatements. Tape interest, charge-off and recovery totals therefore
remain individually compared with the certificate's cash/loss taxonomy.
Unexplained differences stay visible and limit investment-use conclusions.

The full investigation is recorded in
[`SOURCE_RECONCILIATION.md`](SOURCE_RECONCILIATION.md) and the machine-readable
`data/source_exception_register.json`. All 3,825,715 rows satisfy the exact
issuer balance identity. Nevertheless, 287 of 322 strict aggregate
tape/certificate comparisons differ. In particular, the reported principal
field has no disclosed cash/noncash split and repeated disposition proceeds
cannot be added as fresh monthly cash. The event timing audit finds 1,032 of
4,526 first-observed defaults carry an earlier effective month; 19 occur at
the first-tape boundary. Later positive-balance reinstatements remain exposure
and never create a second first-default event. No labels are silently
retimed to make certificate losses match.

Historical target coupons have now been independently compared with official
New York Fed compounded SOFR averages under the executed reset rule: all 17
match exactly. The stale rate-date labels remain preserved. The finite public
amendment search and its named sponsor endpoint gap are documented in
[`RATE_AND_AMENDMENT_REVIEW.md`](RATE_AND_AMENDMENT_REVIEW.md); supplemental
evidence uses a separate manifest so the core source freeze remains intact.
