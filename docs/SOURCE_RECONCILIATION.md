# Source reconciliation and exception register

The complete panel contains 3,825,715 actual loan-month observations across
46 consecutive collection periods. All 243 archived sources pass independent
original-byte and compressed-byte SHA-256/size verification. Every loan row
exactly satisfies the issuer's balance identity:

`beginning balance - ending balance = reported principal + chargeoff + other principal adjustment`.

Those checks establish faithful ingestion and internal balance arithmetic.
They do not establish a cash/noncash split or equality with the trustee's
certificate. The strict tape-to-certificate gate remains failed: 287 of 322
comparisons differ. No residual is inserted as a synthetic loan, collection,
loss, fee or adjustment to force a match. The machine-readable
[exception register](../data/source_exception_register.json) preserves all
46 periods, candidate bridges, exact cents, source URLs and original hashes.
The independent review is in
[INDEPENDENT_CASH_BRIDGE_AUDIT.md](INDEPENDENT_CASH_BRIDGE_AUDIT.md).

## What the disclosed fields can establish

The issuer's [EX-103 explanatory exhibit](https://www.sec.gov/Archives/edgar/data/2063979/000206397926000045/exhibit103november2021.xml)
has the same original SHA-256 in all 46 monthly filings:
`f627c94c8f12c3399f37f929f19d783a9a71a405432d3b8937821e2d497dc787`.
Its field descriptions are more specific than the generic
[SEC ABS XML specification 1.9](https://www.sec.gov/info/edgar/specifications/absxml-1.9.zip)
and AutoLoan XSD comments. The adapter retains the issuer's reported values,
including signed values that conflict with descriptive zero-flooring language.

- EX-103 item 3(f)(15) defines other adjustment as the balance identity's
  residual. Since the October 2021 servicing conversion, the field reports
  net principal increases, principally returned principal payments or
  reinstated chargeoffs. Other net principal reductions enter reported
  principal collections.
- Items 3(f)(18–21) report payments/interest/principal/other collections after
  specified reversals; negative net amounts are described as floored at zero.
  Item 3(f)(20) expressly includes some noncash principal reductions, such as
  bankruptcy reductions. Their separate amounts are not disclosed.
- Items 3(i)(1–2) distinguish chargeoffs during the period from receipts after
  an earlier chargeoff. Recovery is a period flow. Item 3(k)(1) gives net
  disposition proceeds without stating that the field resets monthly.
- XSD item 3(f)(24) permits multiple zero-balance codes and has only month
  precision for the effective date. Code 1 combines maturity and payoff;
  code 4 represents chargeoff. Neither the XSD nor EX-103 provides a separate
  noncash adjustment, clipped-reversal or certificate-allocation ledger.

Both the [2024-2 executed Sale and Servicing Agreement](https://www.sec.gov/Archives/edgar/data/1259380/000119312524109815/d801955dex991.htm)
and the [2025-2 executed agreement](https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex991.htm)
were checked for their own deal. Section 4.3 applies the Simple Interest
Method to eligible receipts, including liquidation and repossessed-vehicle
sales. Appendix A defines Available Collections with specified inclusions
and exclusions, including Supplemental Servicing Fees and advance
reimbursement. The ordinary monthly servicing fee is separately paid under
section 3.8; net physical remittances under section 4.8 must still be accounted
for as separate gross transfers. These provisions do not authorize subtracting
the ordinary servicing fee from tape interest to force agreement.

## Strict gate results

| Comparison | Exact matches | Unresolved differences |
| --- | ---: | ---: |
| Positive-balance outstanding loan count | 22 | 24 |
| Positive beginning principal | 1 | 45 |
| Positive ending principal | 0 | 46 |
| Reported tape principal versus certificate principal collections | 0 | 46 |
| Reported tape interest versus certificate finance-charge collections | 0 | 46 |
| Raw chargeoffs versus certificate new-default principal | 7 | 39 |
| Recovery flows versus certificate recoveries | 5 | 41 |

The certificate's own seven arithmetic identities pass in every period
(322 checks). Forty-four inter-month certificate principal continuity checks
also pass. Those are separate checks and do not replace the failed source gate.

## Investigated examples

Amounts below are dollars; residual always means tape/candidate minus
certificate. The August 2026 target has 47,562 positive-balance loans, exactly
the certificate count. Removing customer credits is an economic eligibility
rule, not a scale adjustment.

| August 2026, CAOT-2025-2 | Tape or candidate | Certificate | Residual |
| --- | ---: | ---: | ---: |
| Positive ending principal | 744,970,252.15 | 744,970,764.16 | -512.01 |
| Positive beginning principal | 775,781,740.46 | 775,782,240.33 | -499.87 |
| Principal collected | 29,509,614.88 | 29,502,058.28 | +7,556.60 |
| Interest collected | 6,124,232.81 | 6,173,785.69 | -49,552.88 |
| Raw chargeoff flows | 1,659,526.54 | 1,309,417.89 | +350,108.65 |
| First-observed-default chargeoff flows | 1,319,924.87 | 1,309,417.89 | +10,506.98 |
| Chargeoffs plus all other principal adjustments | 1,301,276.29 | 1,309,417.89 | -8,141.60 |
| Recovery flows | 350,666.99 | 345,715.96 | +4,951.03 |

Negative ending customer credits total -133.20. Their exclusion explains the
difference between signed and positive-balance aggregates; it does not resolve
the remaining -512.01. The collateral mapping remains a source exception even
though the outstanding count matches.

For September 2024, CAOT-2024-2, raw chargeoffs of 3,112,202.98 plus adjustments
of -607,939.62 produce 2,504,263.36, still 6,665.40 below certificate defaults
of 2,510,928.76. First-observed-default chargeoffs total 2,617,571.45 and
effective-month chargeoffs total 1,996,745.65; neither reconciles. Mixing
returned payments and reinstatements into a new-default loss amount has no
documented allocation rule.

The finance-charge gap is already -1,288,645.42 in the first April 2024 month,
when reported chargeoff/recovery flows, liquidation interest and advances are
zero or omitted as inapplicable. In August 2026, certificate Simple Interest
Advances and Unreimbursed Servicer Advances are zero; liquidation interest is
1,110.66, well below the 49,552.88 interest gap. Neither advances nor aggregate
recoveries nor the ordinary servicing fee yields a supported exact bridge.
EX-103 documents potentially relevant differences but does not quantify the
cause of each individual residual.

## Exceptions and what would close them

| ID | Finding and current treatment | Required evidence to resolve |
| --- | --- | --- |
| POOL-001 | Positive-only eligibility handles credits, but eligible principal/count do not consistently map to the certificate. Preserve raw signed and positive totals. | Issuer loan-ID eligible-pool ledger, balance adjustments and credit handling at the same month end. |
| CASH-001 | Principal includes unspecified noncash reductions and reversal treatment. The cash partition cannot be identified from the disclosed fields. | Separate gross receipts, reversals, bankruptcy/noncash reductions and certificate principal allocation by loan. |
| CASH-002 | Interest reversal clipping and eligible cash allocation are not separately quantified; tested fee/advance/recovery substitutions do not reconcile. | Unclipped interest receipts/reversals and issuer finance-charge allocations, with exclusions and liquidation interest. |
| LOSS-001 | Repeated chargeoff flows, reinstatements and recognition/effective-month differences prevent an exact new-default bridge. | New-default, reinstatement and rechargeoff ledger with exact recognition dates and reasons for principal adjustments. |
| CASH-003 | Period recovery flows do not equal certificate allocated liquidation cash; retained repo proceeds overlap them. | Dated post-default receipts/reversals, disposition costs and principal/interest allocation tied to certificate rows 17b, 18b and 77. |
| REPO-001 | Disposition field is observed as retained history. August has 379 unchanged amounts totaling 4,375,741.27; it is excluded as an additive monthly cash flow. Net change of 284,198.64 is not a complete cash allocation. | Dated sales and receipt ledger before those values can enter a new monthly cash bridge. |
| EVENT-001 | First observed default is a disclosure label, sometimes later than the effective month. Reinstated exposure remains in the panel and latest active pool. | Earlier histories or exact issuer legal recognition dates and reinstatement ledger. |
| SOURCE-001 | September 2024 contains -3,599.68 signed recovery in an ACTIVE group despite EX-103's described zero floor. Preserve the original value. | Issuer correction or explanation of negative recovery and reinstatement reporting. |
| CERT-001 | Two 2025 headers repeat stale dates. Dated exhibit filenames and actual 10-D periods supply chronology while original labels remain visible. | Corrected issuer exhibits to remove conflicting source labels. |
| CERT-002 | Three 2024-2 retired A2 cells contain original U+FFFD. Aggregate note interest is exactly reported total deposits minus principal; individual class values remain missing. | Corrected class-interest cells for complete class-level reconciliation. |

## Default timing and reinstatements

The read-only [event audit](../data/default_observation_audit.json) finds 4,526
first-observed defaults. Of those, 3,494 have an effective month equal to the
observed month, and 1,032 have an earlier effective month; 19 are first-tape
boundary observations. First April tapes include 9 code-4 rows for 2024-2 and
10 for 2025-2 despite zero reported chargeoff flows. These cannot be presumed
new legal defaults in that month.

No first-default row and no code-4 row has positive ending balance. This is
consistent with Appendix A's rule that a legal Defaulted Receivable has zero
principal at month end. The label uses chargeoff/code 4 and does not use a
transient repossession indicator. After the first observed event, the corpus
contains 1,204 additional positive-chargeoff rows, 1,528 positive-balance rows,
and 197 nonpositive-to-positive transitions across 186 loans. Those later
balances remain cash exposure; later chargeoffs are not new first defaults.
Code 1 outcomes distinguish early payoff from scheduled maturity, require
positive beginning exposure and current effective month, and exclude prior
default and repurchase combinations. Explicit zero chargeoff does not block
an otherwise valid prepayment. Missing rows never imply payoff.

Features still require `acceptance_time <= forecast month start`. The reported
observation period and issuer effective date do not replace actual public
availability. A historical month reported later can be an outcome but cannot
supply contemporaneous predictors.

## Reproduction and use limitation

Run `python scripts/audit_default_observations.py` for the read-only event
audit, then `python scripts/analyze_source_bridges.py` for the exception
register. `scripts/build_panel.py` produces the source summary and
`scripts/verify_sources.py` verifies the full original/archive hash chain.
These commands require the separately acquired raw corpus and panel, which
are intentionally not bundled in Git. The small archived certificate fixtures
remain portable for parser tests.

Research model comparisons and certificate replay can proceed with these
qualified source labels. Exact investable cash forecasts and security-level
conclusions remain gated on issuer ledger/correction evidence. An adverse
scenario for the latest 512.01 principal residual assigns that exposure
immediate full loss under an explicit adverse convention. It is not a
mathematical present-value bound across every possible waterfall path and does
not bound unrelated interest, recovery, default-timing or prior collateral
source errors.
