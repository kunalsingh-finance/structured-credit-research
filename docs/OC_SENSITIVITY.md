# Conditional OC sensitivity

The executed OC formula remains the primary rule. This separate diagnostic measures the consequence of substituting the reported dollar target under identical collateral cash assumptions. It does not decide which target legally governs, reconcile the loan tapes or change any primary release gate.

Generated `2026-10-02T14:41:25.193798+00:00` from primary results `2026-10-02T14:39:27.073613+00:00`; primary SHA-256 `67e4fb89e51e132e32042fde3c3e0d9af631f5fa3863143b792d0b3ebd0ba7aa`. Machine evidence: [oc_sensitivity.json](../output/oc_sensitivity.json).

## Authoritative formula and hypothetical alternative

The [executed sale and servicing agreement, Appendix A](https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex991.htm) defines OC as 0.75% of cutoff Pool Balance. Original and compressed source bytes are independently rehashed before calculation. Integer rational half-up arithmetic gives **$10,579,345.66** on documented cutoff principal of **$1,410,579,421.74**. Certificates report **$10,579,421.74**, a **$76.08** increase.

The counterfactual varies only the OC target. It encodes the reported dollars as an equivalent decimal fraction while keeping initial pool, reserve minimum, cleanup threshold, coupons, fees, elections and collateral paths fixed. This hypothetical fraction is not an amendment or an alternative authoritative contract interpretation.

## Historical comparisons reset to each certificate

All 16 post-stub primary ledgers reproduce exactly, including 7 separately identified later months. Each comparison starts with that certificate's reported opening notes and reserve; state is reset for the next period. Primary comparisons retain 118 differences. With the hypothetical reported target, 0 differences remain.

For fixed opening balances and all other inputs, regular principal due is a clipped affine function of the OC target. Its change lies between zero and the target change. All historical comparisons satisfy that exact-cent local bound. This local due-amount result does not bound a state-propagated PV, credit loss or arbitrary trigger path. Historical period deltas cannot be summed to represent one propagated history.

The [executed indenture, Section 2.8(d)](https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex41.htm) allocates aggregate distribution principal across the five tiers and shares A2 principal ratably. The diagnostic independently checks cumulative A2 allocation using opening class weights and exact rational half-up arithmetic. Fractional-cent half-up allocation is an explicit modeled convention; the clause does not itself specify a fractional-cent convention. Reported distributions are comparisons, never calculation inputs beyond the expressly labeled target alternative.

## Propagated fixed scenario paths

Each alternative starts from the same September 15, 2026 note, reserve and collateral state. Cash flows, defaults, recovery timing, principal collections, interest collections and flat floating coupon are identical between alternatives. Note balances and interest claims then propagate independently. All primary monthly ledgers and controls reproduce exactly; both alternatives conserve cash, note principal, pool principal and reserves and reach a closed horizon.

PV discounts only paid cash at the common 8% effective annual assumption on actual distribution dates. Decimal calculations independently agree with primary prices and paid-principal WAL. Terminal economic impairment and unpaid claims are not discounted as cash receipts.

| Fixed path | Periods | Aggregate note PV change (USD) | Note cash change | Terminal principal-loss change | Maturity flags change |
| --- | ---: | ---: | ---: | ---: | --- |
| Central | 61 | 7.89624870 | -$14.30 | $0.00 | No |
| Downside | 64 | 0.00000000 | $0.00 | $0.00 | No |
| Severe | 67 | 0.00000000 | $0.00 | $0.00 | No |

The machine output reports each class's paid principal, interest, unpaid claims, principal loss, full-repayment WAL, paid-principal WAL and price effects separately. WAL remains unavailable for impaired or uncompleted classes. The two endpoints quantify consequences on these fixed paths; they do not establish a uniform bound across intermediate targets, arbitrary collateral paths, yield assumptions or other trigger states.

## Reproduce and inspect freshness

```powershell
python scripts/analyze_oc_sensitivity.py
python scripts/analyze_oc_sensitivity.py --verify-only
```

The script rejects unfinished primary generation, results/version mismatch, changed certificates, stale research code, corrupted executed-source bytes, unsupported scenario elections/expenses, failed exact primary reproduction and inputs changed during computation. Verification also rejects saved evidence or this report if it no longer matches the authoritative inputs. It runs no fitting, downloading or full-panel projection.

Exact source cash and eligibility differences and the governing OC discrepancy still require authoritative evidence. A small modeled effect under specified assumptions does not establish investment materiality or completed financial validation.
