# Supplemental validation study

The full-panel study completed on October 2, 2026 at
`2026-10-02T08:11:28.623675+00:00`. Its results are saved in
`output/extended_validation.json`. All 3,825,715 source observations were
loaded. The primary model, its labels and split, and scenario assumptions were
not changed.

This protocol was specified **after viewing the primary test**. The added
comparisons are descriptive supplemental research, not a newly untouched
selection test. Code, protocol and panel SHA-256 identities are stored with the
output and matched the files after the run. All four study controls pass.
The complete software suite passes 92 tests, including seven new independent
availability, smoothing, fold and segment controls.

## Cohort benchmark

The new baseline estimates competing survival/default/payoff probabilities in
fixed cells of prior-disclosed credit score, loan age, remaining term and
disclosure lag. Missing values have a separate band. Training is the same
904,502 older-deal development observations used by the primary specification.
Each cell receives 100 pseudo-observations distributed using development-only
overall frequencies. Unseen cells fall back to those overall frequencies.
No test labels, current cash or future eligibility enter fitting.

The fixed primary test is scored against the cohort, constant and existing
delinquency-transition baselines. Outcomes still mean first-observed default
disclosure or voluntary payoff in the existing conditional eligible risk set.

| Diagnostic | Cohort | Unchanged primary |
| --- | ---: | ---: |
| Later-month default Brier | 0.003171 | 0.002522 |
| Unseen-deal default Brier | 0.001093 | 0.000867 |
| Later-month payoff first-event exposure MAE | $689,436 | $1,273,119 |
| Unseen-deal default first-event exposure MAE | $200,352 | $270,958 |

The dollars above measure beginning exposure of event-labelled loans. They are
not actual payoff or default cash. Different methods win different diagnostics;
this study does not choose a replacement primary model. The separate actual
certificate-cash scoring remains the relevant evidence for runoff error.

## Expanding chronological folds

Each fold fits a fresh imputer, scaler and uncalibrated multinomial logistic
model on older-deal outcomes publicly accepted before its fitting date.
Training collection months never extend beyond June 2025. No later-fold
calibration labels are used. Constant, transition and cohort benchmarks are
fitted independently within the same eligible training sample.

| Fitting date | Test collection months | Training observations | Test observations | Latest fitted-label acceptance |
| --- | --- | ---: | ---: | --- |
| 2024-09-01 | Sep-Nov 2024 | 162,876 | 220,273 | 2024-08-15 |
| 2025-01-01 | Jan-Mar 2025 | 461,320 | 195,677 | 2024-12-16 |
| 2025-04-01 | Apr-Jun 2025 | 662,212 | 178,807 | 2025-03-17 |
| 2025-09-01 | Sep-Nov 2025 | 904,502 | 151,482 | 2025-07-15 |

The fitting date is not a claim that all subsequent predictors were known on
that date. Each evaluated row uses information accepted before **its own
collection-month start**, under the unchanged disclosure-feature adapter.
This is a fixed-estimator sequence of monthly conditional predictions within
each fold, not a three-month whole-fleet cash forecast made on the fitting date.
All target windows precede the primary February-August 2026 test.

| Fold | Constant default Brier | Transition default Brier | Expanding logistic default Brier |
| --- | ---: | ---: | ---: |
| 1 | 0.001719 | 0.001410 | 0.001642 |
| 2 | 0.001990 | 0.001634 | 0.001736 |
| 3 | 0.002517 | 0.001928 | 0.002144 |
| 4 | 0.003279 | 0.002676 | 0.002847 |

The expanding logistic improves default Brier versus the constant benchmark
and loses to the transition benchmark in all four folds, despite higher
default AUC. This illustrates why discrimination and calibration/error must
be reported separately. It supplies no reason to retune the frozen primary
model on its existing test.

## Fixed-segment diagnostics

The output records 23 observed segment bands in each primary test split across
credit score, age, remaining term, disclosure lag, delinquency and APR. Each
record contains development/test population share, loan count, observed event
rate, predicted rate, signed calibration gap, Brier and AUC for each method.
Segments derive from prior publicly disclosed features.

Material examples in the older-deal later test are:

- For 4,176 observations at 61-90 days delinquent, the unchanged primary
  predicts 16.81% default against 18.61% observed.
- For 8,114 observations at 31-60 days delinquent, it predicts 1.63% against
  0.59% observed.
- In the unseen deal's 1,571 observations at 61-90 days delinquent, it predicts
  21.24% against 21.90% observed.

These are conditional disclosure-event rates, not economic defaults dated
independently by the issuer. Repeated loan observations, small event counts and
common-calendar shocks limit significance claims. Differences in segment
composition also reflect seasoning, selection and vintage. Providing these
diagnostics satisfies the reporting requirement; it does not certify uniform
stability or portability to another originator.

## Reproduction

```powershell
python scripts/run_extended_validation.py
python -m unittest discover -s tests -v
```

The runner refits the unchanged primary specification once for segment
probabilities and writes only the supplemental output. It records its fixed
after-look protocol and fails instead of silently accepting conflicting
protocol definitions. Source cash reconciliation, economic event timing,
reference-rate review and legal exceptions remain separate gates.
