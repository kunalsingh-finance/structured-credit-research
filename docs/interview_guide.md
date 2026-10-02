# Presenting the Structured Credit Platform

Start with the research question: when auto-loan borrowers default or repay early, which bond takes the loss, and how does the timing of repayment change?

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

The supplemental validation protocol was specified after inspecting the primary test. Its four expanding folds and fixed-band comparisons are descriptive. Fresh uncalibrated logistic models have higher default Brier scores than the delinquency-transition baseline in all four folds. Explain the result without selecting a new winning model: the primary model, original results and scenario assumptions remain unchanged. Segment calibration includes repeated loans and small event counts, so it does not establish causal drift or unqualified statistical significance.

Prepare to answer these questions:

- How did you define default, prepayment and recovery from the public loan disclosures?
- Which reporting fields can leak future information, and how did you prevent that?
- Why does your baseline sometimes beat the fitted model?
- What happens when collections cannot cover interest?
- How do reserve draws and interest arrears change later cash flows?
- Which contractual states are implemented, and which still require specialist document review?
- Does the model reach zero balance, or does it leave unpaid principal at the horizon?
- How much would results change under a slower recovery or lower recovery rate?
- Why is discounted value different from a quoted bond price?
- What would you validate before using this platform on a second deal?

Use the actual numbers in the generated memo. Avoid claiming a buy recommendation, a rating, trading returns, industry certification or unseen-deal forecast validity without the corresponding evidence.

For a short demo, spend one minute on the credit question, two minutes on a scenario and its class cash flows, one minute on the source and validation evidence, and one minute on a limitation you would resolve next. Keep the final minute for a technical question.
