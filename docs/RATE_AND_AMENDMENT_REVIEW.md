# Historical coupon and public amendment review

All 17 observed CAOT-2025-2 floating coupons exactly match the executed
reset rule using official New York Fed historical rates. The finite SEC
inventory and primary-document review identifies no post-execution
transaction amendment within the covered public filing scope. Neither finding
is a claim about unfiled/private notices or future benchmark paths.

The reproducible evidence is
[`data/rate_and_amendment_review.json`](../data/rate_and_amendment_review.json),
produced by `python scripts/review_rates_and_amendments.py`. Public acquisition
uses `--acquire`. Supplemental sources have their own
[manifest](../data/rate_amendment_source_manifest.json) and
[verification](../data/rate_amendment_source_verification.json): all 177
supplemental original/archive byte hashes and sizes pass independent rereading.
The previously verified 243-source performance manifest, loan panel, model
snapshot and certificate extraction remain unchanged.

## Executed rate rule and official data

The [executed 2025-2 Sale and Servicing Agreement, Appendix A](https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex991.htm)
defines Class A-2b Rate as the benchmark plus **0.69 percentage points** per
annum, floored at zero. Compounded SOFR is the published 30-calendar-day
compounded average. SOFR Adjustment Date is the second U.S. Government
Securities Business Day before the first day of the accrual period; the
determination time is 3:00 p.m. New York time. Accrual begins on the previous
adjusted distribution date, or May 2, 2025 for the initial period, and ends
immediately before the next distribution date.

The [New York Fed SOFR Averages methodology](https://www.newyorkfed.org/markets/reference-rates/sofr-averages-and-index)
describes rolling compounded averages and their business-day publication.
The archived [official SOFRAI API response](https://markets.newyorkfed.org/api/rates/secured/sofrai/search.json?startDate=2024-04-01&endDate=2026-10-02)
contains 626 observations from April 1, 2024 through October 1, 2026. The
API schema is separately archived. Rates are compared as exact decimals in
percentage units, before conversion to the engine's decimal-fraction coupon.
Every certificate URL and original SHA-256 appears beside its rate check in
the sourced JSON.

| Distribution | Accrual begins | SOFR adjustment date | Official 30-day average % | Coupon % |
| --- | --- | --- | ---: | ---: |
| 2025-05-15 | 2025-05-02 | 2025-04-30 | 4.35068 | 5.04068 |
| 2025-06-16 | 2025-05-15 | 2025-05-13 | 4.33228 | 5.02228 |
| 2025-07-15 | 2025-06-16 | 2025-06-12 | 4.30385 | 4.99385 |
| 2025-08-15 | 2025-07-15 | 2025-07-11 | 4.33962 | 5.02962 |
| 2025-09-15 | 2025-08-15 | 2025-08-13 | 4.34270 | 5.03270 |
| 2025-10-15 | 2025-09-15 | 2025-09-11 | 4.37208 | 5.06208 |
| 2025-11-17 | 2025-10-15 | 2025-10-10 | 4.23367 | 4.92367 |
| 2025-12-15 | 2025-11-17 | 2025-11-13 | 4.14202 | 4.83202 |
| 2026-01-15 | 2025-12-15 | 2025-12-11 | 3.98385 | 4.67385 |
| 2026-02-17 | 2026-01-15 | 2026-01-13 | 3.70735 | 4.39735 |
| 2026-03-16 | 2026-02-17 | 2026-02-12 | 3.65819 | 4.34819 |
| 2026-04-15 | 2026-03-16 | 2026-03-12 | 3.67223 | 4.36223 |
| 2026-05-15 | 2026-04-15 | 2026-04-13 | 3.63980 | 4.32980 |
| 2026-06-15 | 2026-05-15 | 2026-05-13 | 3.64285 | 4.33285 |
| 2026-07-15 | 2026-06-15 | 2026-06-11 | 3.59301 | 4.28301 |
| 2026-08-17 | 2026-07-15 | 2026-07-13 | 3.62539 | 4.31539 |
| 2026-09-15 | 2026-08-17 | 2026-08-13 | 3.63650 | 4.32650 |

All 17 coupon residuals and all 17 displayed benchmark residuals are exactly
zero. The historical publication dates provide the relevant business-day
sequence. SIFMA's [October 13, 2025 full-close confirmation](https://www.sifma.org/news/press-releases/sifma-fixed-income-market-close-recommendations-in-the-u-s-the-u-k-and-japan-for-u-s-columbus-day-and-japan-health-and-sports-day-holidays-2025)
explains the October 10 fixing before an October 15 accrual start. Its
[2026 U.S. holiday schedule](https://www.sifma.org/resources/general/holiday-schedule)
confirms February 16's full close, producing the February 12 fixing before a
February 17 start. Early closes are not excluded as full holidays.

Ten early certificates retain the stale rate-label date `7/14/2024` despite
their actual 2025/2026 distributions. Their numerical benchmark and coupon
match the correct reset dates above. The stale label remains an issuer source
exception; it is not used to fetch a 2024 fixing. Historical numeric validation
is therefore resolved while the literal label defect remains visible.

This review uses the official history downloaded on the review date, not an
independently archived 3:00 p.m. snapshot for each old fixing. The API revision
indicator is retained for each used rate. It validates the observed historical
series and coupon arithmetic, not a future floating-rate path, a complete
future holiday implementation or undisclosed benchmark conforming changes.

## Finite post-execution amendment search

The cutoff is October 2, 2026 UTC. Every returned indexed form is inventoried
within the following execution-to-cutoff windows. Older SEC submissions files
were inspected for overlapping date ranges; no omitted history file overlaps
the requested windows.

| SEC submissions filer | Window begins | Window records | Forms most relevant to transaction changes |
| --- | --- | ---: | --- |
| [CAOT-2024-2, CIK2016948](https://data.sec.gov/submissions/CIK0002016948.json) | 2024-04-24 | 61 | 29 10-D, 29 ABS-EE, two 10-K, closing 8-K |
| [CAOT-2025-2, CIK2063979](https://data.sec.gov/submissions/CIK0002063979.json) | 2025-05-02 | 36 | 17 10-D, 17 ABS-EE, one 10-K, closing 8-K |
| [CarMax Auto Funding LLC, CIK1259380](https://data.sec.gov/submissions/CIK0001259380.json) | 2024-04-24 | 161 | 31 8-K; registration/other forms also inventoried |
| [CarMax Inc., CIK1170010](https://data.sec.gov/submissions/CIK0001170010.json) | 2024-04-24 | 186 | 22 8-K, two 10-K, eight 10-Q; remaining forms inventoried |

The 444 filer-record occurrences include joint filings appearing in multiple
inventories. After accession deduplication, 171 primary documents were
archived and screened: all post-execution trust primaries, plus depositor and
parent 8-K/10-K/10-Q, registration-amendment-related forms and every amended
form in the window. The JSON preserves all eligible metadata records, selected
primary URLs, original hashes, target-name contexts and candidate dispositions.
It does not treat a generic amendment word as proof of a changed transaction.

There are no 10-D/A, ABS-EE/A or 8-K/A forms in either trust inventory window.
Other amended filings do occur elsewhere in the broader inventory, including
registration/ownership filings, and are retained. No subsequent current
report or newly dated transaction amendment was identified for either target
trust in the covered primary-document review.

The target/amendment keyword candidates were reviewed in context:

- Closing 8-Ks are baseline execution filings. The original Amended and
  Restated Trust Agreements are part of the initial transactions.
- The April 28, 2025 offering 8-K predates the 2025-2 execution and describes
  agreements to be dated May 1. It is not a post-execution amendment.
- [2024-2's May 23, 2025 annual report](https://www.sec.gov/Archives/edgar/data/2016948/000201694825000027/a2024-210xk052325.htm)
  and [May 27, 2026 annual report](https://www.sec.gov/Archives/edgar/data/2016948/000201694826000029/a2024-210xk052726.htm)
  incorporate the original April 1, 2024 agreements. Their amended/restated
  wording concerns original trust and older depositor LLC documents.
- [2025-2's May 27, 2026 annual report](https://www.sec.gov/Archives/edgar/data/2063979/000206397926000027/a2025-210xk052726.htm)
  incorporates original May 1, 2025 agreements through the April 28 pre-closing
  8-K. That original incorporation pointer contains no newly dated transaction
  amendment; it also does not prove absolute absence of later changes.

The closing issuer reports name CarMax Business Services LLC as sponsor under
CIK1601902. Its standalone
[submissions endpoint](https://data.sec.gov/submissions/CIK0001601902.json)
returned HTTP404 during this review. That is an explicit inventory scope gap,
not evidence of no sponsor filings. Related joint filings were reviewed through
the trust/depositor inventories. Private communications, unfiled agreements,
other filers and post-cutoff filings remain outside this finite public search.

The defensible conclusion is **no public post-execution transaction amendment
identified within the stated search scope**, with the sponsor endpoint gap
retained. All three post-execution annual-report candidates have explicit
context review and none remains unreviewed. This public search and the exact
historical rate check close the project's two internal review omissions;
unidentified collateral/cash/loss bridges in
[SOURCE_RECONCILIATION.md](SOURCE_RECONCILIATION.md) still require issuer ledger
or corrected-disclosure evidence.
