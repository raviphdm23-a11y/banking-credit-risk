# Bibliography — references for later academic write-up

Private reference, not shown on frontend. Collects citable sources found while researching this project's
methodology, for reuse in the TAI paper revision / future academic write-up. Add to this file going forward
whenever new research is pulled in — don't let citations live only in conversation.

**Honesty note on confidence level:** entries below marked "found via web search, not read in full" were
identified from search-result abstracts/snippets on 2026-10-09, not the complete paper text. Verify details
(exact findings, page numbers, full author list) against the original source before citing in a submitted
paper — treat these as leads to the right paper, not confirmed, quote-ready citations yet.

---

## Probability calibration (added 2026-10-09, for the calibration step in `METHODOLOGY.md` Step 6)

Full context and results from applying these: `CALIBRATION_NOTES.md`.

1. **Niculescu-Mizil, A., & Caruana, R. (2005).** *Predicting Good Probabilities with Supervised Learning.*
   Proceedings of the 22nd International Conference on Machine Learning (ICML 2005).
   Foundational reference for calibrating supervised classifiers generally (not credit-specific). Found via
   web search, not read in full — standard, widely-cited reference per multiple secondary sources.

2. **Zadrozny, B., & Elkan, C. (2001/2002).** Work on isotonic regression for probability calibration
   (commonly cited as two papers: a 2001 ICML paper and a 2002 KDD paper extending it to multiclass).
   Standard foundational reference for isotonic calibration specifically. Found via web search, not read in
   full — exact titles/venues should be confirmed before citing.

3. **"Calibration of Machine Learning Classifiers for Probability of Default Modelling."**
   https://www.paperswithcode.com/paper/calibration-of-machine-learning-classifiers
   Benchmarks Platt scaling and isotonic regression across 18 real-world credit datasets (Logistic
   Regression, Random Forest, Gradient Boosting). Argues rank-ability metrics (AUC) alone are insufficient
   for evaluating credit models — calibration must be checked separately. Found via web search, author/venue
   not confirmed from the search snippet — check the paperswithcode listing for full citation details.

4. **2025 arXiv preprint, German Credit dataset calibration study.**
   Found via web search (arxiv.org/pdf/2509.23665, titled "Calibration Meets Reality: Making Machine
   Learning Predictions Trustworthy" per the search result list). Reports post-hoc calibration gave a 76%
   reduction in Expected Calibration Error (ECE) for XGBoost on the German Credit dataset. Preprint — not
   confirmed peer-reviewed. Verify exact title/authors against the arXiv page before citing.

5. **Vienna University of Technology (TU Wien) thesis — Austrian corporate defaults.**
   https://repositum.tuwien.at/handle/20.500.12708/228112
   Found Logistic Regression and Random Forest are often reasonably calibrated without correction, but
   XGBoost and neural networks clearly benefit from calibration; beta calibration gave the lowest Brier
   scores for the more complex model classes. Author name and exact title not confirmed from the search
   snippet — retrieve from the TU Wien repository page before citing.

6. **MDPI study on the HMEQ dataset.**
   https://www.mdpi.com/2227-9091/14/7/152
   Reported XGBoost with strong accuracy and good calibration (ECE=0.0117) vs. Random Forest with less
   well-calibrated estimates (ECE=0.0475) in their specific setup — a useful counterpoint showing calibration
   need depends on training details (their setup likely didn't use `scale_pos_weight` the way this project
   does). Journal: appears to be *Risks* or similar MDPI finance/risk journal based on the URL pattern (volume
   14, issue 7) — confirm exact journal name/issue before citing.

7. **Mortgage-default thesis comparing Platt scaling vs. isotonic regression.**
   Found via web search; exact title/institution/URL not captured in the search snippet — re-search before
   citing. Finding: isotonic regression worked better for tree-based algorithms, Platt scaling better for
   logistic regression. This finding directly motivated choosing isotonic regression for this project's
   XGBoost-only pipeline.

8. **Machado, M. R., Charpentier, A., Flachaire, E., & Gallic, E. (2024).**
   https://ideas.repec.org/p/aim/wpaimx/2404.html (AMSE Working Paper 2024, aim/wpaimx/2404)
   Argues calibration should be measured during model tuning rather than bolted on afterward; proposes a
   "Local Calibration Score" for datasets where risk-score heterogeneity deviates from the underlying
   probability distribution, arguing traditional calibration metrics lose reliability in that case. Relevant
   given this project's own findings on GMSC's `DebtRatio`/`RevolvingUtilizationOfUnsecuredLines` measurement
   quality issues (`GMSC_FINDINGS.md`).

---

## Dataset provenance (from earlier in this project — add full citations here as each is re-confirmed)

- **PAK.csv**: PAKDD 2009 Data Mining Competition (NeuroTech Ltd. / Center for Informatics, Federal
  University of Pernambuco). One documented placing: Linhart, Harari, Abramovich & Buchris (Tel Aviv
  University), 3rd place, AUC 0.655 — published in *"PAKDD Data Mining Competition 2009: New Ways of Using
  Known Methods."* Full citation (venue, year, publisher) not yet confirmed — see `PAK_FINDINGS.md` for what
  was established. The 1st-place result/score was never found; do not cite 0.655 as a winning benchmark.
- **HMEQ.csv**: SAS SAMPSIO sample library; associated with Baesens, Roesch & Scheule's *Credit Risk
  Analytics* textbook per `HMEQ_FINDINGS.md` — full textbook citation (publisher, year, ISBN) not yet
  retrieved.
- **German Credit**: UCI Machine Learning Repository "Statlog (German Credit Data)" — classic dataset,
  original creator Prof. Hans Hofmann, Universität Hamburg. Exact UCI citation not yet retrieved.
- **GMSC.csv**: Kaggle "Give Me Some Credit" competition (2011). Competition host/sponsor citation not yet
  retrieved.

*(These four need a proper verification pass — same rigor as the calibration entries above — before this
section is paper-ready. Flagging as not-yet-done rather than guessing full citations.)*

---

## Methodology v3 additions (added 2026-10-10, from the external review)

These came in with the v3 revision. The review's own reference list is in
`EXPERT_REVIEW_OF_METHODOLOGY.md` section 6; this section records the ones now load-bearing in
`METHODOLOGY.md` and implemented in code. **Same caveat as above: verify initials, year and venue against
the original before submission.**

### Shapley / importance — the estimand and its critiques

1. **Williamson, B. D., & Feng, J. (2020).** *Efficient nonparametric statistical inference on population
   feature importance using Shapley values.* ICML. — **SPVIM. This is the correct citation for this
   project's construction** (refit per subset, value function = cross-validated performance). v2 cited SAGE
   for this and that claim is withdrawn. Also supplies an inference framework with valid confidence
   intervals, which is the principled alternative to the shadow-null route taken here.
2. **Covert, I., Lundberg, S., & Lee, S.-I. (2020).** *Understanding global feature contributions with
   additive importance measures.* NeurIPS. — SAGE. Cite **for contrast**: SAGE marginalises absent features
   out of a single fitted model rather than refitting. Note the first author's initial is **I.** (Ian) — v2's
   bibliography had "Covert, S."
3. **Kumar, I. E., Venkatasubramanian, S., Scheidegger, C., & Friedler, S. (2020).** *Problems with
   Shapley-value-based explanations as feature importance measures.* ICML. — The attribution-vs-selection
   critique underpinning `METHODOLOGY.md` §1. A referee in this area will cite it, so cite it first.
4. **Aas, K., Jullum, M., & Løland, A. (2021).** *Explaining individual predictions when features are
   dependent: More accurate approximations to Shapley values.* Artificial Intelligence, 298. — Marginal vs
   conditional Shapley with dependent features; the backing for grouped players (§5.3).
5. **Lundberg, S. M., & Lee, S.-I. (2017).** *A unified approach to interpreting model predictions.* NeurIPS.
6. **Lundberg, S. M., et al. (2020).** *From local explanations to global understanding with explainable AI
   for trees.* Nature Machine Intelligence, 2(1). — TreeSHAP; exact and polynomial-time for tree ensembles,
   which is why it is a mandatory benchmark comparator (§7.2).

### Selection, stability, and inference on cross-validation

7. **Kursa, M. B., & Rudnicki, W. R. (2010).** *Feature selection with the Boruta package.* Journal of
   Statistical Software, 36(11). — The shadow/permuted-feature device now used for the empirical null
   (§5.4). Already a live dependency of this codebase via `feature_screening.boruta_screen`.
8. **Meinshausen, N., & Bühlmann, P. (2010).** *Stability selection.* JRSS-B, 72(4). — §7.3.
9. **Bengio, Y., & Grandvalet, Y. (2004).** *No unbiased estimator of the variance of K-fold
   cross-validation.* JMLR, 5. — Why v2's fold-level t-test was invalid.
10. **Dietterich, T. G. (1998).** *Approximate statistical tests for comparing supervised classification
    learning algorithms.* Neural Computation, 10(7). — Same point, earlier and more general.
11. **Nadeau, C., & Bengio, Y. (2003).** *Inference for the generalization error.* Machine Learning, 52.
12. **Benjamini, Y., & Yekutieli, D. (2001).** *The control of the false discovery rate in multiple testing
    under dependency.* Annals of Statistics, 29(4). — Only needed if BH is retained anywhere; in v3 it is a
    reported diagnostic, and the shadow-null bar dissolves the multiplicity problem entirely.

### Credit-scoring domain

13. **Lessmann, S., Baesens, B., Seow, H.-V., & Thomas, L. C. (2015).** *Benchmarking state-of-the-art
    classification algorithms for credit scoring: An update of research.* EJOR, 247(1). — **The
    benchmark-conventions reference for this literature.** Replaces the Hosmer-Lemeshow AUC bands v2 used.
14. **Baesens, B., et al. (2003).** *Benchmarking state-of-the-art classification algorithms for credit
    scoring.* JORS, 54(6).
15. **Thomas, L. C., Edelman, D. B., & Crook, J. N.** *Credit Scoring and Its Applications.* SIAM.
16. **Siddiqi, N.** *Credit Risk Scorecards.* Wiley. — Already used for the IV bands; cite formally, and for
    the monotonic-WOE binning convention now implemented in `binning.woe_bin`.
17. **Hand, D. J., & Henley, W. E. (1997).** *Statistical classification methods in consumer credit scoring:
    a review.* JRSS-A, 160(3). — Reject inference / accept-only samples (§3.2).
18. **Crook, J., & Banasik, J. (2004).** *Does reject inference really improve the performance of application
    scoring models?* Journal of Banking & Finance, 28(4). — §3.2; the basis for retracting v2's PAK income
    conclusion.
19. **Hand, D. J. (2009).** *Measuring classifier performance: a coherent alternative to the area under the
    ROC curve.* Machine Learning, 77(1). — The AUC critique motivating partial AUC and Gini-first reporting.
20. **DeLong, E. R., DeLong, D. M., & Clarke-Pearson, D. L. (1988).** *Comparing the areas under two or more
    correlated receiver operating characteristic curves: a nonparametric approach.* Biometrics, 44(3). —
    Implemented in `selection.delong_test`; the fast form follows **Sun & Xu (2014)**, IEEE Signal Processing
    Letters, which should be cited alongside if the implementation is described.
21. **Dumitrescu, E., Hué, S., Hurlin, C., & Tokpavi, S. (2022).** *Machine learning for credit scoring:
    Improving logistic regression with non-linear decision-tree effects.* EJOR, 297(3).
22. **Gunnarsson, B. R., et al. (2021).** *Deep learning for credit scoring: Do or don't?* EJOR, 295(1).

### Fairness and regulatory

23. **Hardt, M., Price, E., & Srebro, N. (2016).** *Equality of opportunity in supervised learning.* NeurIPS.
24. **Chouldechova, A. (2017).** *Fair prediction with disparate impact.* Big Data, 5(2).
25. **Barocas, S., Hardt, M., & Narayanan, A.** *Fairness and Machine Learning.* fairmlbook.org.
26. Regulatory instruments cited by name in `METHODOLOGY.md` §3.1 (no academic citation needed, but quote
    accurately): **US ECOA / Regulation B** prohibited bases; **EU AI Act Annex III** treating
    creditworthiness assessment as high-risk. Confirm current article/annex numbering before submission.

### Statistical conventions no longer used

27. **Cohen, J. (1988).** *Statistical Power Analysis for the Behavioral Sciences.* — Cited in v2 for the
    `d >= 0.8` threshold. **That rule is withdrawn in v3** (review M3). Keep the reference only if the paper
    narrates the withdrawn approach as part of the methodological history, which §8 item 4 suggests it
    should.
28. The AUC interpretation bands commonly attributed to **Hosmer & Lemeshow** are **removed** in v3 in favour
    of item 13 — they are a clinical rule of thumb, not a credit-scoring benchmark.

## Sample-size / data sufficiency (added 2026-10-17, for `METHODOLOGY.md` §4.6 / AEGIS G1 Riley diagnostic)

Primary sources for the Riley minimum-N diagnostic. **29 and 31 were read in full** (BMJ m441 PDF and the
pmsampsize CRAN manual) during implementation and the formulas were validated against their worked examples;
30, 32, 33 identified from those sources' reference lists / search — confirm page ranges before submission.

29. **Riley, R. D., Ensor, J., Snell, K. I. E., et al. (2020).** *Calculating the sample size required for
    developing a clinical prediction model.* **BMJ 368:m441.** doi:10.1136/bmj.m441. **Read in full.** Source
    of the three binary criteria (B1 risk-precision, B3 shrinkage ≥0.9, B4 optimism ≤0.05); required N = max.
    Worked Example 1 (pre-eclampsia, P=30, φ=0.05, R²cs=0.05 → N=5,249, 263 events, 8.75 EPP) reproduced
    exactly by `backend/riley_minsize.py`.
30. **Riley, R. D., Snell, K. I. E., Ensor, J., et al. (2019).** *Minimum sample size for developing a
    multivariable prediction model: PART II — binary and time-to-event outcomes.* **Statistics in Medicine
    38(7):1276–1296.** doi:10.1002/sim.7992. The underlying derivation of the binary/shrinkage criteria.
31. **Ensor, J. (2023).** *pmsampsize: Sample Size for Development of a Prediction Model.* CRAN package manual
    (v1.1.3). **Read in full.** Confirms binary = three criteria (shrinkage, optimism, overall-risk precision),
    final N = largest; and that the `cstatistic=` option approximates R²cs by **seeded simulation** (seed
    123456), not a closed form — the route re-implemented and validated here (C=0.89, φ=0.174 → R²cs 0.291 vs
    the manual's paired csrsquared 0.288).
32. **Riley, R. D., Van Calster, B., & Collins, G. S. (2020).** *A note on estimating the Cox-Snell R² from a
    reported C statistic (AUROC) to inform sample size calculations for developing a prediction model with a
    binary outcome.* **Statistics in Medicine 39(21):2957–2966.** The C-statistic → R²cs approximation used
    for the forward-consistent G1 engine.
33. **van Smeden, M., Moons, K. G. M., de Groot, J. A. H., et al. (2019).** *Sample size for binary logistic
    prediction models: beyond events per variable criteria.* **Statistical Methods in Medical Research
    28(8):2455–2474.** Motivates moving beyond the fixed EPV≥10 rule — the rationale for reporting Riley
    alongside EPV. (EPV comparator itself: **Peduzzi et al. (1996)**, *J. Clin. Epidemiol.* 49(12):1373–1379.)
