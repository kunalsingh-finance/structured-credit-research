# Independent loan-to-certificate cash audit

This audit leaves the original acceptance gates in `RESEARCH_DESIGN.md`
unchanged. An exact loan balance identity is established; an exact conversion
of all published loan fields into trust cash is not established. The source
exceptions remain open and the platform retains development status.

## Independent arithmetic

The archived original XML was streamed independently of the normalized panel
for CAOT-2025-2 August 2026 and CAOT-2024-2 September 2024. Integer cents were
used without tolerances or balance/cash adjustments.

| Control | August 2026, target deal | September 2024, older deal |
| --- | ---: | ---: |
| XML loan records | 79,101 | 85,552 |
| Failures of beginning minus ending principal = principal collected + charged-off principal + other principal adjustment | 0 | 0 |
| Failures of total actual paid = principal + interest + other amounts collected | 0 | 0 |

These tests show that parsing and the tape's own accounting equations agree.
They do not establish that the fields are identical to the certificate's trust
cash categories. The separate full-panel ingestion audit extends the balance
identity check to all 3,825,715 loan-month records across 46 periods.

The source-event audit separately found 4,526 first-observed default events:
1,032 have an issuer zero-balance effective month earlier than the first
observed event month, and 19 are corpus-boundary rows. These facts do not
change frozen training labels. The fitted outcome is first-observed default
disclosure in its eligible risk set, not an independently verified hazard of
economic default at an exact time. Recovery lag measured from that event has
the same timing qualification.

The following are raw signed field sums. Differences equal XML minus the
certificate; no first-default or recovery-timing filter is applied in this
table.

| Quantity | August 2026 XML | Certificate | Difference |
| --- | ---: | ---: | ---: |
| Principal collected | $29,509,614.88 | $29,502,058.28 | $7,556.60 |
| Interest collected / finance-charge collections, row 17a | $6,124,232.81 | $6,173,785.69 | -$49,552.88 |
| Charged-off principal / defaulted receivables | $1,659,526.54 | $1,309,417.89 | $350,108.65 |
| Recovered amount / recoveries | $350,666.99 | $345,715.96 | $4,951.03 |
| Other principal adjustment | -$358,250.25 | No separate corresponding row | Unallocated |

| Quantity | September 2024 XML | Certificate | Difference |
| --- | ---: | ---: | ---: |
| Principal collected | $40,684,973.07 | $40,680,145.98 | $4,827.09 |
| Interest collected / finance-charge collections, row 17a | $11,543,407.43 | $12,557,075.21 | -$1,013,667.78 |
| Charged-off principal / defaulted receivables | $3,112,202.98 | $2,510,928.76 | $601,274.22 |
| Recovered amount / recoveries | $765,939.53 | $765,217.95 | $721.58 |
| Other principal adjustment | -$607,939.62 | No separate corresponding row | Unallocated |

For August, the signed ending tape balance is $744,970,118.95. Excluding its
17 negative balances gives positive principal of $744,970,252.15, against
certificate collateral of $744,970,764.16: the positive-exposure residual is
**$512.01**. The 47,562 positive balances exactly match the certificate's
outstanding loan count. The signed balance residual, $645.21, answers a
different arithmetic question and must not be substituted for $512.01.

Inspection results, original-byte source metadata and certificate rows are
retained in `output/independent_cash_bridge_2025-2_2026-08.json` and
`output/independent_cash_bridge_2024-2_2024-09.json`.

## Published field meanings limit cash inference

All 46 archived issuer EX-103 explanatory exhibits have identical original
SHA-256 hashes. Their descriptions establish the following distinctions:

- Item 3(f)(20), Actual Principal Collected, includes certain noncash principal
  reductions, including bankruptcy reductions. Item 3(f)(15) reports only net
  increases in principal after the October 2021 servicing-system conversion;
  it mixes returned principal payments and reinstated charged-off principal.
- Items 3(f)(18), (19), (20), (21), and 3(i)(2) describe negative net amounts
  being reported as zero in specified circumstances. The magnitude of a
  clipped reversal cannot be recovered from a reported zero alone.
- Recovered Amount describes post-charge-off receipts. Repossessed Proceeds
  describes proceeds from disposition net of fees and expenses. These fields
  are not independent cash streams to add together.

There is a description-versus-data exception: September 2024 includes a
negative Recovered Amount of -$3,599.68, despite EX-103 describing a zero floor
for negative net recoveries. The raw amount is retained. The explanatory text
does not authorize clamping contrary source values.

The SEC auto-loan XSD provides decimal amounts and optional fields; it does not
provide a separate principal noncash-reduction amount or negative-interest
reversal amount. Schedule AL Item 3(f)(15) requires other balance adjustments,
while Items 3(f)(18)-(22) distinguish payment, interest, principal, other cash
and advances. The issuer's specific descriptions are necessary to interpret
the actual file. Schema conformance alone cannot establish cash equivalence.

The exact total-paid component identity in the two inspected tapes supplies
no numerical separation of the blended noncash, reclassification and reversal
components. It does not prove those components caused any particular dollar
gap, or that they were nonzero in each individual loan. Those causal amounts
must remain unknown unless another independently reported field or ledger
establishes them.

## Contractual cash categories

The executed 2025 sale and servicing agreement supplies independently reviewed
cash definitions. The source-ingestion audit also reviewed the executed 2024
agreement and confirmed the same allocation wording.

- Section 4.3 applies receipts, including liquidation and repossession/sale
  amounts, to interest and principal using the Simple Interest Method. It
  excludes supplemental servicing fees and purchased-receivable receipts.
- Available Collections includes eligible obligor receipts, liquidation
  proceeds, account earnings, purchase amounts, specified refunds and
  advances, subject to exclusions and advance reimbursements. Liquidation
  Proceeds is net of eligible collection/disposition costs and required
  payments to obligors.
- Section 3.8 pays the ordinary monthly servicing fee separately. Section 4.8
  permits net physical remittance but requires separate accounting for
  deposits and distributions. Adding or subtracting the ordinary servicing
  fee from XML interest is therefore not a documented reconciliation rule.
- The August 2026 certificate separately reports zero simple-interest advances
  and zero unreimbursed advances. Those rows cannot explain that month's
  $49,552.88 interest difference.

The archived certificate distinguishes finance-charge collections (17a),
liquidation proceeds allocated to finance charge (17b), principal collections
(18a), and liquidation proceeds allocated to principal (18b). Their reported
sum agrees with reported recoveries in the inspected cases. No loan-level
allocation ledger has been established for those certificate categories.

## Repossession amounts are retained history

A loan-ID join of July and August 2026 raw XML demonstrates that August's
$4,697,374.78 repo-proceeds sum is mostly retained disposition information:
379 unchanged nonzero entries total $4,375,741.27. There are 37 newly nonzero
entries totaling $285,338.24 and five changed existing entries with a net
change of -$1,139.60. The net change is $284,198.64.

New disposition entries can report the same cash in Recovered Amount; one
example reports $8,000 in both fields. Neither summing all repo amounts nor
adding them to recoveries produces an independent monthly cash measure. The
join evidence is in `output/independent_repo_repeat_2025-2_2026-08.json`.

## Completion implication

The original strict cash bridge has **not passed**. Balance arithmetic and
outstanding counts can be verified independently. Event timing, repeated
charge-offs, sign conventions and disposition history must still be analyzed
before identifying which further differences are mechanically resolvable.

From the currently archived loan fields, the cash split is not uniquely
established: noncash principal reductions, returned-payment/reinstatement
adjustments, negative interest/recovery reversals and net liquidation-cost
allocations are not fully disaggregated. An exact trust-cash reconstruction
requires additional issuer/servicer allocation evidence, a documented public
bridge or a corrected filing. This is an external information limitation,
not permission to replace loan cash with expected certificate output, waive
the gate, or claim all discrepancies are bounded by the $512.01 opening
collateral sensitivity. It does not establish that no additional public
evidence could exist.

This source audit also does not satisfy the separate predictive-method gates:
a frozen chronological split is not an expanding-window exercise, and
descriptive scores on seven later months per deal do not establish segment
stability or generalization to a different originator. Those requirements
remain distinct from successful parsing, software tests and conservation.

## Primary sources

- [August 2026 target loan tape](https://www.sec.gov/Archives/edgar/data/2063979/000206397926000045/cart20252.xml)
- [August 2026 target EX-103](https://www.sec.gov/Archives/edgar/data/2063979/000206397926000045/exhibit103november2021.xml)
- [August 2026 target certificate](https://www.sec.gov/Archives/edgar/data/2063979/000206397926000047/a2025-2ex991091526.htm)
- [September 2024 older-deal EX-103](https://www.sec.gov/Archives/edgar/data/2016948/000201694824000029/exhibit103november2021.xml)
- [Executed 2025 sale and servicing agreement](https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex991.htm), Sections 3.8, 4.2-4.4, 4.8 and Appendix A.
- [SEC XML technical specification and schemas](https://www.sec.gov/info/edgar/specifications/absxml-1.9.zip)
- [Schedule AL, official CFR, auto-loan Item 3](https://www.govinfo.gov/link/cfr/17/229?link-type=pdf&sectionnum=1125&year=mostrecent), pages 606-608 of the 2025 edition.
