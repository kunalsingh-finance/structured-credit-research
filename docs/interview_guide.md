# Presenting the Structured Credit Platform

Start with the research question: when auto-loan borrowers default or repay early, which bond takes the loss, and how does the timing of repayment change?

Use the current primary pack generated at `2026-10-02T13:17:08.124031+00:00`, SHA-256 `f560aaa291e553a66fe61460c832201e34c44d4c865b97615e215fb8b6088107`. The software suite passes 113 tests. Current-version artifact verification passes five stale-input rejection cases, 3,280 cached workbook formulas with no formula errors, numerical agreement and fresh rendered/browser checks. All nine rebuilt workbook previews and both PDF pages were inspected; browser scenario and yield controls work and emit no JavaScript errors. Passing software checks does not pass unresolved financial-source gates.

Open the research dashboard and choose the most adverse credit scenario. Identify the first class with principal loss, show interest shortfalls separately, and explain that two bonds can have different weighted-average lives even when neither loses principal. Then open the workbook and change the discount yield. Show that value changes through the monthly cash flows and that price assumptions affect the value gap.

Explain the model in this order:

1. **Evidence:** preserved SEC filing bytes, SHA-256 hashes, reporting periods, loan IDs and certificate controls.
2. **Borrower risk:** features available before each target period, chronological validation, explicit default and prepayment definitions, and a transparent baseline.
3. **Structure:** payment priorities, reserve support, interest arrears, sequential principal and the allocation of credit losses.
4. **Decision:** compare scenario losses and repayment timing with structural protection. Separate model value from an independent market quote.

Describe a reconciliation as a financial identity, not as a quality score. Beginning loan principal minus principal reductions must equal ending principal. Cash available must equal cash distributed plus retained reserve. For the scenario engine, a note's beginning economic balance equals principal paid plus economic principal impairment plus its ending economic balance. The contractual principal claim can remain unpaid after economic impairment; the model preserves that claim separately. Principal loss is neither a cash payment nor an official legal writeoff, and discounted value includes only principal and interest actually paid. Source reporting differences must remain visible.

Be precise about validation. Historical cash-flow replay uses observed collateral cash and tests structural mechanics. A forecast holdout tests predictions from information known before the target period. A held-out reporting month on the same deal does not establish that the borrower model generalizes to another originator or another economic cycle.

The borrower target is first-observed default disclosure. A reported effective default month can precede first observation; public availability and reporting delay determine which information the model could use. Explain this distinction before discussing discrimination or event-exposure errors.

Present the mixed cash-forecast result directly. Across seven withheld months for the unseen 2025 deal, the fitted model improves default cash MAE ($463,351 versus $607,572) and interest MAE ($121,737 versus $153,078). It materially worsens principal-collection MAE ($4.51 million versus $1.21 million) and ending-pool MAE ($8.22 million versus $1.62 million). These figures do not support overall model superiority. The credit scenarios remain illustrative assumptions; the validation does not establish an investment forecast or return.

The supplemental validation protocol was specified after inspecting the primary test. Its four expanding folds and fixed-band comparisons are descriptive. Fresh uncalibrated logistic models have higher default Brier scores than the delinquency-transition baseline in all four folds. Explain the result without selecting a new winning model: the borrower model and scenario assumptions remain frozen. Structural cash flows were regenerated after the independently supported A2 rounding correction. Segment calibration includes repeated loans and small event counts, so it does not establish causal drift or unqualified statistical significance.

Use the A2 correction as a concrete engineering example. Two one-cent principal tiers allocated separately to opening shares of 7:3 can incorrectly give both cents to A2a. Applying the aggregate two-cent distribution once gives one cent to each class under the stated half-up convention. The engine now computes a cumulative monthly allocation against opening weights, including reserve-extra regular principal. The correction follows the executed indenture's aggregate principal allocation and independent small-cent examples; it was not selected to erase the OC discrepancy.

Explain the legal-input sensitivity separately from source resolution. The executed 0.75% OC formula gives $10,579,345.66; certificates report $10,579,421.74, a $76.08 difference. The primary replay retains 118 differences across 16 post-stub periods. A hypothetical reported-dollar target matches all 592 comparisons after the A2 fix, but a matching counterfactual does not establish that the reported target governs. Each historical period resets to its reported opening balances, so those deltas cannot be presented as one state-propagated history.

The [conditional OC study](OC_SENSITIVITY.md) also propagates separate note states over identical Central, Downside and Severe collateral paths. At the common 8% discount assumption, the reported-target alternative changes Central aggregate note PV by +$7.89624870; Downside and Severe cash flows are unchanged. Principal-loss amounts, unpaid-interest claims and maturity flags do not change at either endpoint. These specific path results do not bound arbitrary collateral paths, intermediate targets, rates or trigger changes and do not establish investment materiality.

Keep the remaining source limitations concrete: 287 tape-to-certificate comparisons differ, latest mapped positive collateral is $512.01 below the certificate, and the OC rule still needs an authoritative explanation. The public dependency recheck at `2026-10-02T13:24:57.533894+00:00` found unchanged bytes at six covered endpoints and no new accessions in four inventories; the sponsor endpoint returned HTTP 404. That finite check does not prove that no other public or private correction exists.

Prepare to answer these questions:

- How did you define default, prepayment and recovery from the public loan disclosures?
- Which reporting fields can leak future information, and how did you prevent that?
- Why does your baseline sometimes beat the fitted model?
- What happens when collections cannot cover interest?
- How do reserve draws and interest arrears change later cash flows?
- Which contractual states are implemented, and which still require specialist document review?
- Why did rounding principal separately across tiers cause a bug, and how did you verify the correction independently?
- Why does matching every replay comparison under a reported-target counterfactual still leave the contractual gate unresolved?
- Does the model reach zero balance, or does it leave unpaid principal at the horizon?
- How much would results change under a slower recovery or lower recovery rate?
- Why is discounted value different from a quoted bond price?
- What would you validate before using this platform on a second deal?

Use the actual numbers in the generated memo. Avoid claiming a buy recommendation, a rating, trading returns, industry certification or unseen-deal forecast validity without the corresponding evidence.

For a short demo, spend one minute on the credit question, two minutes on a scenario and its class cash flows, one minute on the source and validation evidence, and one minute on a limitation you would resolve next. Keep the final minute for a technical question.
