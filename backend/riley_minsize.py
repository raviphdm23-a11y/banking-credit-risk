"""
Riley et al. minimum-sample-size for a BINARY prediction model.
Faithful re-implementation of the pmsampsize binary criteria (Riley 2019 Stat Med
Part II; Riley 2020 BMJ m441), with the C-statistic -> Cox-Snell R2 approximation
of Riley, Van Calster & Collins (2020, Stat Med).

Three binary criteria; required N = max(n1, n3, n4):
  B1  precise overall-risk estimate (margin +/-0.05 on prevalence)
  B3  shrinkage factor >= 0.9 (small overfitting)
  B4  small optimism (<=0.05) in apparent Nagelkerke R2

All formulas validated against the BMJ m441 worked examples (see validate()).
"""
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq


def max_r2cs(prev):
    """Maximum attainable Cox-Snell R2 for a binary outcome at prevalence `prev`.
    max(R2cs) = 1 - exp(2*[phi*ln phi + (1-phi)*ln(1-phi)]).
    Validated: prev 0.5->0.75, 0.3->0.71, 0.05->0.33 (BMJ m441)."""
    p = prev
    return 1.0 - np.exp(2.0 * (p * np.log(p) + (1 - p) * np.log(1 - p)))


def r2cs_from_cstat(cstat, prev, n_sim=1_000_000, seed=123456):
    """Approximate the Cox-Snell R2 from a target C-statistic (AUROC) and outcome
    prevalence, by the simulation approach of Riley, Van Calster & Collins (2020)
    — the same route pmsampsize uses for its `cstatistic=` option.

    Method: the C-statistic of a logistic model equals P(LP_case > LP_control).
    Assume the linear predictor LP ~ Normal in each outcome group with a common
    variance and a mean separation `delta`. Then C = Phi(delta/sqrt(2)), so
    delta = sqrt(2)*Phi^{-1}(C). Simulate a large population with that LP structure
    calibrated to `prev`, then compute the Cox-Snell R2 from the simulated
    log-likelihoods of the fitted-vs-null model.
    """
    rng = np.random.default_rng(seed)
    delta = np.sqrt(2.0) * norm.ppf(cstat)              # mean separation on LP scale
    n0 = int(round(n_sim * (1 - prev)))
    n1 = n_sim - n0
    # LP drawn so cases are shifted by delta relative to controls (unit sd each)
    lp0 = rng.normal(0.0, 1.0, n0)
    lp1 = rng.normal(delta, 1.0, n1)
    y = np.concatenate([np.zeros(n0), np.ones(n1)])
    lp = np.concatenate([lp0, lp1])
    # Logistic model p = 1/(1+exp(-(a+b*lp))). With the normal-LP construction the
    # true coefficient is b=delta and intercept a set to hit prevalence. Fit a,b by
    # 1-D calibration is unnecessary: use the Bayes-optimal p implied by the normal
    # densities, which is the model whose C-stat = target.
    # p(y=1|lp) = prev*f1(lp) / (prev*f1(lp) + (1-prev)*f0(lp))
    logf1 = -0.5 * (lp - delta) ** 2
    logf0 = -0.5 * (lp) ** 2
    # posterior odds in log space
    log_odds = np.log(prev / (1 - prev)) + (logf1 - logf0)
    p = 1.0 / (1.0 + np.exp(-log_odds))
    p = np.clip(p, 1e-12, 1 - 1e-12)
    ll_model = np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))
    pbar = y.mean()
    ll_null = np.sum(y * np.log(pbar) + (1 - y) * np.log(1 - pbar))
    lr = 2.0 * (ll_model - ll_null)
    r2cs = 1.0 - np.exp(-lr / n_sim)
    return float(r2cs)


def n_b1(prev, margin=0.05, z=None):
    """Criterion B1: sample size for a precise overall-risk estimate.
    n = (z/margin)^2 * prev*(1-prev). Validated: prev .5/.1/.2 -> 385/139/246."""
    if z is None:
        z = norm.ppf(0.975)  # 1.959964
    return (z / margin) ** 2 * prev * (1 - prev)


def n_b3(r2cs, P, S=0.9):
    """Criterion B3: shrinkage factor >= S (default 0.9).
    n = P / [ (S-1) * ln(1 - R2cs/S) ]. Validated: R2cs .05, P30 -> 5249."""
    return P / ((S - 1.0) * np.log(1.0 - r2cs / S))


def n_b4(r2cs, P, prev, delta=0.05):
    """Criterion B4: small optimism (<=delta) in apparent Nagelkerke R2.
    R2nag = R2cs/max_R2cs ; S4 = R2nag/(R2nag+delta) ;
    n = P / [ (S4-1) * ln(1 - R2cs/S4) ]. Validated: R2cs .2, max .33, P20 -> ~1079."""
    r2nag = r2cs / max_r2cs(prev)
    S4 = r2nag / (r2nag + delta)
    return P / ((S4 - 1.0) * np.log(1.0 - r2cs / S4))


def riley_min_n(prev, P, cstat=None, r2cs=None, S=0.9):
    """Full binary calculation. Supply either an anticipated C-statistic (preferred,
    forward-consistent) or a Cox-Snell R2 directly. Returns per-criterion n, the
    governing max, implied EPP, and the R2cs used."""
    if r2cs is None:
        if cstat is None:
            raise ValueError("supply cstat or r2cs")
        r2cs = r2cs_from_cstat(cstat, prev)
    nb1 = n_b1(prev)
    nb3 = n_b3(r2cs, P, S)
    nb4 = n_b4(r2cs, P, prev)
    import math
    N = max(nb1, nb3, nb4)
    N = int(math.ceil(N))
    return {
        "prev": prev, "P": P, "cstat": cstat, "r2cs": r2cs,
        "max_r2cs": max_r2cs(prev),
        "n_B1_risk": int(math.ceil(nb1)),
        "n_B3_shrinkage": int(math.ceil(nb3)),
        "n_B4_optimism": int(math.ceil(nb4)),
        "N_required": N, "events_required": int(math.ceil(N * prev)),
        "EPP_at_required": round(N * prev / P, 2),
    }


def validate():
    print("=== VALIDATION against BMJ m441 / Stat Med worked examples ===\n")
    print("max_r2cs:  prev 0.5 -> %.4f (exp 0.75) | 0.3 -> %.4f (0.71) | 0.05 -> %.4f (0.33)"
          % (max_r2cs(0.5), max_r2cs(0.3), max_r2cs(0.05)))
    print("B1 risk :  prev 0.5 -> %.1f (exp 385) | 0.1 -> %.1f (139) | 0.2 -> %.1f (246)"
          % (n_b1(0.5), n_b1(0.1), n_b1(0.2)))
    print("B3 shrink: R2cs 0.05, P30 -> %.1f (exp 5249)" % n_b3(0.05, 30))
    print("B4 optim : R2cs 0.20, prev 0.05(max~0.33), P20 -> %.1f (exp ~1079)" % n_b4(0.20, 20, 0.05))
    # BMJ Example 1 full: pre-eclampsia, P=30, prev 0.05, csrsquared 0.05 -> N 5249, EPP 8.75
    r = riley_min_n(0.05, 30, r2cs=0.05)
    print("\nBMJ Example 1 (P=30, prev .05, R2cs .05): N=%d (exp 5249), events=%d (exp 263), EPP=%.2f (exp 8.75)"
          % (r["N_required"], r["events_required"], r["EPP_at_required"]))
    print("  per-criterion: B1=%d  B3=%d  B4=%d" % (r["n_B1_risk"], r["n_B3_shrinkage"], r["n_B4_optimism"]))
    # C-stat route sanity: manual example csr 0.288 vs cstat 0.89 at prev 0.174 should be close
    r2_from_c = r2cs_from_cstat(0.89, 0.174)
    print("\nC-stat->R2cs sanity (manual eg: cstat 0.89, prev 0.174): R2cs~%.3f (manual pairs it with csrsquared 0.288)"
          % r2_from_c)


if __name__ == "__main__":
    validate()
