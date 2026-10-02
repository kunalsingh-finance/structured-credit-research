# Stateful cash-flow engine

The scenario engine uses integer USD cents and explicit collateral cash. It is
independent of reported payment outputs. It preserves the older bounded
`waterfall.replay` API and its original evidence.

## Governing evidence

The executed May 1, 2025 documents were filed May 2, 2025 in accession
`0001193125-25-111714`. Their original bytes are archived in `data/raw/legal`.

| Rule | Executed source location |
| --- | --- |
| Ordinary interest/principal priorities; class-A interest shortage allocated pro rata | Indenture 2.8(a), 2.8(c), 2.8(d) |
| Reserve shortfall draw, affiliate exclusions, empty-pool and acceleration sweep | Sale/servicing 4.6(b) |
| Full repayment reserve sweep, skipped reserve replenishment, full regular principal | Sale/servicing 4.1(d) |
| Excess reserve pays unfunded regular principal and then qualified tail claims | Sale/servicing 4.7(b), 4.7(d) |
| Separate remaining-reserve transfer to depositor on trust termination | Sale/servicing 4.7(e) |
| Cleanup eligibility, price and advance notice | Sale/servicing 9.1 |
| Acceleration priority differs by contractual default category | Indenture 5.4(b)(iv), 5.4(b)(v) |
| Coupons, accrued monthly interest, OC target, maturity principal floors | Sale/servicing Appendix A |

[Sale and servicing agreement](https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex991.htm)
and [indenture](https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex41.htm).

The executed definition independently confirms the OC percentage used by the
prospectus. It does not substitute the certificate's target dollars. Applied to
the documented initial pool, the calculation is $10,579,345.66; certificates
report $10,579,421.74. The $76.08 exception remains visible. The archived
purchase-price definition matches the documented $1,410,579,421.74 pool amount.
The final prospectus separately labels that amount as cutoff principal in its
loan-distribution tables, and the first actual certificate reports the same
opening collateral. The reported OC target equals this principal amount less
the initial $1.4 billion note balance. That identity does not establish an
amendment to the percentage rule. No reviewed amendment or alternative cutoff
balance resolves the difference.

## API and units

`ScenarioState(pool_balance, note_balances, reserve_balance,
prior_distribution_date)` supplies opening balances and the preceding payment
date. All amounts are integer cents; note maps contain precisely A1, A2a, A2b,
A3, A4, B, C and D. State also carries unpaid monthly interest, unpaid charges
on overdue interest, servicing claims and expense claims separately.

`CollateralPeriod(distribution_date, pool_end, principal_collected,
interest_collected, ...)` supplies a new collection period. `prepayments` are
already included in `principal_collected`; recoveries are separate period cash
flows. Pool conservation is checked before any distribution:

```text
Opening pool - Closing pool = Principal collected + Defaults + Repurchases
```

`distribute_period` returns a new immutable state and an inspectable ledger.
`run_scenario` reports monthly ledgers, cash conservation, maturity failures,
tranche recovery, paid-principal WAL and horizon closure. Terms are configurable
for small independent example checks; live deal terms are supplied explicitly.

The floating coupon is a nonnegative annual decimal fraction supplied by the
caller. It is not reconstructed from SOFR by the cash-flow engine. Fixed notes
other than A1 accrue monthly; A1 and A2b use actual payment-date days/360.
The current scenario API starts after the initial stub payment and requires
successive calendar months. An initial-issuance adapter is separate work.

## Branch and bookkeeping assumptions

An interest shortfall persists as a claim. Unpaid monthly interest and unpaid
charges on that interest are separate to avoid compounding the charge itself.
Payments clear overdue charges and then monthly-interest claims. Interest on
arrears is conditional on the documented lawful-interest assumption.

Acceleration must be an explicit election with either
`payment_or_bankruptcy` or `covenant_or_representation`. The engine does not
infer holder instructions, grace-period expiration, remedy eligibility or
collateral-sale consent. Both branches pay A1 principal first and then allocate
the remaining class-A principal pro rata. Their junior-interest priorities
differ.

Optional purchase requires an explicit election, the documented 10% threshold,
at least ten days notice, a supplied purchase amount covering collateral
principal plus accrued receivable interest and other appraised property, and
enough funds to pay all note and modeled expense claims. It does not assume the
servicer will call. Cleanup and acceleration cannot be combined without a
separately reviewed adapter.

`senior_expenses` contains only qualified capped second-tier costs. Eligibility
and aggregate caps must be independently established by an input adapter;
ordinary trustee expenses use the subordinate `trustee_fee` field. The
current scenario adapter sets unreimbursed advances, unrelated amounts,
successor servicing premiums and unclassified expenses explicitly to zero.
These omissions limit the claim to the documented modeled deal conditions,
not every possible transaction event.

## Runoff, loss and valuation

Every principal payment reduces a note balance. A default is a collateral
principal reduction, not a bond payment. Recoveries appear only when their
cash is supplied. After all modeled collateral and recovery cash has run off,
remaining note balances are economic terminal principal losses. Contractual
liabilities remain separately disclosed; this is not a legal writeoff.

`terminal=True` is the caller's declaration that every future recovery flow
has been included. Positive collateral or restricted reserve still prevents
horizon closure. A shorter unfinished horizon cannot manufacture a loss or a
safe reverse-stress point.

For a fully repaid note, WAL weights actual principal payments by elapsed
days/365.25 and divides by repaid principal. Impaired or unfinished notes have
no complete contractual WAL. Their separately labeled recovered-principal WAL
and principal recovery fraction describe cash actually received. Terminal
losses never enter principal-paid WAL or discounted cash-flow prices.

Reverse stress evaluates every supplied severity point. It identifies the
first observed loss, unpaid-interest or legal-maturity breach on that ordered
grid and, when available, the immediately preceding closed nonbreaching point.
It does not assume monotonicity or claim an exact continuous/multidimensional
minimum.

## Validation

The independent example checks cover cash and principal conservation,
ordinary-replay equivalence, reserve draw and affiliate exclusion, class-A
interest shortages, arrears, maturity floors, sequential/A2 allocation,
full-payoff reserve sweep, both acceleration priorities, accelerated class-A
allocation, cleanup conditions, terminal loss/WAL treatment, incomplete
horizons and nonmonotonic reverse stress. Tests require exact cents; no
tolerance removes an unexplained discrepancy.
