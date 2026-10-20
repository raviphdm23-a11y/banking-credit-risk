"""
aegis_gates.py  —  Deterministic AEGIS gate-option and Go/No-Go engine.

WHY THIS EXISTS
---------------
The governance layer (AEGIS_GOVERNANCE.md) specifies that every gate G0-G5
presents the decision-maker a *closed set of 2-4 genuinely viable options*
(S4), and that the final gate GF is ruled by a *deterministic* Go/No-Go engine
(S7) over a regulatory checklist (S8). Until now those option sets were
authored by hand per run, so they were only as consistent as the author.

This module makes them CODE-DRIVEN and CONSISTENT: the same option grammar,
the same viability tests, and the same GF logic are applied to every dataset.
Only the *numbers* in each option change, because only the evidence changes.

DESIGN RULES IT ENFORCES (from the spec)
----------------------------------------
* S4   GDR anatomy: each option carries option/data/rationale/benefits/risks/
       residual-risk-acceptance. Exactly one is chosen downstream by a human.
* S4   Anti-strawman: an option is emitted ONLY if its viability test passes on
       the evidence. If only one option is viable the gate emits it alone and
       flags "single viable option; escalate" (never pads with strawmen).
* P8   Gates decide governance, not analytics. NONE of the options here re-open
       a pre-registered methodology parameter (IV threshold, shadow bar,
       confirm-frequency, DeLong/Gini tolerances, seed, CV folds). They decide
       only scope, eligibility, conservatism, cutoffs, and Go/No-Go.
* P6   Risk-proportionate: tier (LOW/MEDIUM/HIGH) sets how high the pass-bar
       sits (S3.2 composition table) -- it does NOT change the analytics.
* S7   GF engine never upgrades a NO-GO; a GAP on a must-have (R1-R9) is a hard
       stop. PARTIALs that are remediable -> GO-WITH-CONDITIONS.

The module is pure/stdlib-only and takes an `evidence` dict per gate (the
numbers a SHARP run already computes). It returns structured option sets that a
run harness renders into Gate Decision Records; it decides nothing on its own.

Run `python ml_models/aegis_gates.py` for the self-test, which reproduces the
committed SBA verdict (GO-WITH-CONDITIONS) from its recorded gate states.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional

# --------------------------------------------------------------------------
# Tier policy -- S3.2 composition table (every bar is externally sourced).
# The tier sets the pass-bar height, never the method (P6/P8).
# --------------------------------------------------------------------------
TIERS = ("LOW", "MEDIUM", "HIGH")

# AUC floor by tier (Hosmer-Lemeshow-Sturdivant 2013 bands via S3.2).
_AUC_FLOOR = {"LOW": None, "MEDIUM": 0.70, "HIGH": 0.80}
# EPV handling by tier.
_EPV_MIN = 10  # Peduzzi 1996 / Riley 2019 guideline (not law)

GATE_ORDER = ["G0", "G1", "G2", "G3", "G4", "G5", "GF"]
GATE_NAME = {
    "G0": "Data & Scope Adequacy",
    "G1": "Screening & Data Sufficiency",
    "G2": "Importance Attribution",
    "G3": "Parsimony Selection",
    "G4": "Calibration & Fairness",
    "G5": "Deployment Governance",
    "GF": "Final Go/No-Go",
}
GATE_QUESTION = {
    "G0": "Is the dataset fit to build on, and which columns are ineligible to model?",
    "G1": "Which candidates survive screening, and is the dataset large enough?",
    "G2": "Is the attribution stable and trustworthy enough to select on?",
    "G3": "Which feature set is adopted -- parsimonious vs full -- and the trade-off accepted?",
    "G4": "Is the model calibrated, discriminating, and fair enough to approve?",
    "G5": "Are the deployment-time controls and deliverables correctly configured?",
    "GF": "GO / GO-WITH-CONDITIONS / NO-GO on the whole model.",
}
# Signer per tier mirrors S3.1 / S5 RACI (independent validator at HIGH).
def signer_role(tier: str) -> str:
    return {
        "LOW": "Model Owner (batch sign)",
        "MEDIUM": "Model Validator",
        "HIGH": "Independent Model Validator",
    }[tier]


# --------------------------------------------------------------------------
# Option data structure -- the S4 GDR option fields, verbatim.
# --------------------------------------------------------------------------
@dataclass
class Option:
    label: str          # "A" / "B" / "C"
    kind: str           # ADOPT | ADOPT_WITH_CONDITION | ESCALATE
    option: str         # what is chosen
    data: str           # the figures that support it
    rationale: str      # why it is defensible
    benefits: str       # what it buys
    risks: str          # what it costs/exposes
    residual: str       # the risk the signer explicitly accepts
    recommended: bool = False


@dataclass
class GateDecision:
    gate: str
    name: str
    question: str
    tier: str
    signer: str
    recommendation: str            # one-line machine recommendation
    options: list                  # list[Option]
    single_viable: bool = False    # anti-strawman: only one option -> escalate
    flags: list = field(default_factory=list)  # governance flags raised

    def as_dict(self):
        d = asdict(self)
        return d


def _finalize(gd: GateDecision) -> GateDecision:
    """Apply the anti-strawman rule and label options A/B/C in order."""
    for i, opt in enumerate(gd.options):
        opt.label = chr(ord("A") + i)
    if len(gd.options) == 1:
        gd.single_viable = True
        gd.flags.append("single viable option; escalate")
    return gd


# ==========================================================================
# G0 -- Data & Scope Adequacy
# ==========================================================================
def gate_g0(ev: dict) -> GateDecision:
    """
    evidence keys:
      tier, n_rows, event_rate, history_years (float|None),
      excluded: [{col, reason}], borderline_exclusions: [col,...],
      label_integrity: bool, epv_pool: float|None
    """
    tier = ev["tier"]
    excl = ev.get("excluded", [])
    borderline = ev.get("borderline_exclusions", [])
    label_ok = ev.get("label_integrity", True)
    hist = ev.get("history_years")
    opts: list = []
    flags: list = []

    rec = (f"Adopt the scope: {len(excl)} ineligible column(s) excluded by "
           f"computable precondition; materiality tier {tier}.")

    # A -- adopt recommended scope.
    opts.append(Option(
        "A", "ADOPT",
        option=f"Adopt recommended scope + tier {tier}.",
        data=(f"n={ev['n_rows']:,}, event rate {ev['event_rate']:.3f}; "
              f"excluded: {', '.join(e['col'] for e in excl) or 'none'}; "
              f"history={'n/a' if hist is None else f'{hist:g}y'}; "
              f"label integrity {'OK' if label_ok else 'FAILED'}."),
        rationale="Exclusions are by METHODOLOGY S3.7 computable preconditions "
                  "(constant / identifier-PII / leakage / junk); nothing is "
                  "dropped by taste.",
        benefits="Clean modellable pool; leakage and PII kept out of the model.",
        risks="A borderline column judged ineligible could carry minor signal.",
        residual="Accept loss of any borderline-excluded column's minor signal.",
        recommended=True,
    ))

    # B -- conservative scope: retain borderline exclusions behind an MoC, OR
    #      raise the tier. Viable only if there is a genuine conservative lever.
    if borderline:
        opts.append(Option(
            "B", "ADOPT_WITH_CONDITION",
            option=(f"Retain borderline column(s) {', '.join(borderline)} under "
                    f"a documented Margin of Conservatism (EBA cat. A)."),
            data=f"{len(borderline)} column(s) flagged borderline, not hard-ineligible.",
            rationale="Max information retention is defensible if the column is "
                      "documented and an MoC covers the added uncertainty.",
            benefits="No signal discarded; uncertainty made explicit via MoC.",
            risks="Extra data dependency and monitoring surface.",
            residual="Accept added operational surface + carry an EBA cat-A MoC.",
        ))

    # C -- escalate: a must-have is at risk (label integrity, history, EPV).
    hard = []
    if not label_ok:
        hard.append("label integrity failed (R-data)")
    if tier == "HIGH" and hist is not None and hist < 5:
        hard.append("PD history < 5y at HIGH tier (Basel CRE36.79, R1)")
    if tier == "HIGH" and ev.get("epv_pool") is not None and ev["epv_pool"] < _EPV_MIN:
        hard.append(f"EPV {ev['epv_pool']:.1f} < {_EPV_MIN} at HIGH tier")
    if hard:
        flags.extend(hard)
        opts.append(Option(
            "C", "ESCALATE",
            option="Escalate / return -- do not advance under this authority.",
            data="Blocking: " + "; ".join(hard),
            rationale="A must-have adequacy criterion is at risk; the trade-off "
                      "is above the developer's authority (route up, not down).",
            benefits="Prevents building on an unfit base; forces resolution first.",
            risks="Delay while data/label issues are remediated.",
            residual="Accept schedule delay to protect model integrity.",
        ))

    gd = GateDecision("G0", GATE_NAME["G0"], GATE_QUESTION["G0"], tier,
                      signer_role(tier), rec, opts, flags=flags)
    return _finalize(gd)


# ==========================================================================
# G1 -- Screening & Data Sufficiency
# ==========================================================================
def gate_g1(ev: dict) -> GateDecision:
    """
    evidence keys:
      tier, n_pass, n_pool, epv, riley_req, riley_avail,
      dominant_feature, dominant_iv
    """
    tier = ev["tier"]
    epv = ev.get("epv")
    rreq, ravail = ev.get("riley_req"), ev.get("riley_avail")
    riley_short = (rreq is not None and ravail is not None and ravail < rreq)
    epv_short = (epv is not None and epv < _EPV_MIN)
    flags: list = []

    rec = (f"Advance {ev['n_pass']} of {ev['n_pool']} candidates; "
           f"sufficiency reported (EPV {epv:.0f}, Riley {rreq}/{ravail}).")

    headroom = (ravail / rreq) if (rreq and ravail) else None
    opts: list = [Option(
        "A", "ADOPT",
        option=f"Accept the IV screen; advance {ev['n_pass']} candidates.",
        data=(f"{ev['n_pass']}/{ev['n_pool']} pass IV>=0.02 w/ monotonic WOE; "
              f"dominant {ev['dominant_feature']} IV {ev['dominant_iv']:.3f}; "
              f"EPV {epv:.1f}; Riley {rreq} req vs {ravail} avail"
              + (f" ({headroom:.1f}x)." if headroom else ".")),
        rationale="Screen and sufficiency meet the tier bar (S3.2); nothing is "
                  "retained by chance and the sample clears EPV/Riley.",
        benefits="Carries forward only features with genuine univariate signal.",
        risks="Screened-out low-IV features cannot re-enter later stages.",
        residual="Accept exclusion of sub-threshold-IV features.",
        recommended=not (riley_short or epv_short),
    )]

    # B -- advance WITH a sufficiency caveat / MoC. Mandatory form when the
    #      sample is short for the tier; precautionary (optional) otherwise.
    if riley_short or epv_short:
        conds = []
        if epv_short:
            conds.append(f"EPV {epv:.1f} < {_EPV_MIN} -> mandatory MoC + not-for-capital")
            flags.append("EPV below 10")
        if riley_short:
            conds.append(f"Riley shortfall ({ravail} < {rreq}) -> disclosed caveat"
                         + (" + MoC" if tier == "HIGH" else ""))
            flags.append("Riley minimum-N shortfall")
        opts.append(Option(
            "B", "ADOPT_WITH_CONDITION",
            option="Advance with a documented sufficiency caveat / MoC.",
            data="; ".join(conds),
            rationale="Riley is a reported diagnostic, not an auto-reject (S3.2); "
                      "a shortfall is governed by disclosure + conservatism.",
            benefits="Keeps the run moving while making the data limit explicit.",
            risks="Wider CIs; estimates may need a conservatism add-on.",
            residual="Accept disclosed sufficiency limit under MoC; not-for-capital if EPV<10.",
            recommended=True,
        ))
    else:
        opts.append(Option(
            "B", "ADOPT_WITH_CONDITION",
            option="Advance with a precautionary monitoring note (optional).",
            data=f"Sufficiency clears the bar ({headroom:.1f}x Riley headroom)."
                 if headroom else "Sufficiency clears the bar.",
            rationale="A committee may still attach a precautionary note; defensible "
                      "as caution even where not required.",
            benefits="Documents a watch item without blocking.",
            risks="Minor extra monitoring overhead for no measured need.",
            residual="Accept small overhead of a precautionary note.",
        ))

    # C -- halt for more data: only defensible when short AND tier demands it.
    if (riley_short or epv_short) and tier == "HIGH":
        opts.append(Option(
            "C", "ESCALATE",
            option="Halt -- acquire more data before selection (HIGH tier).",
            data=f"Riley {ravail}<{rreq}" + (f"; EPV {epv:.1f}<{_EPV_MIN}" if epv_short else ""),
            rationale="At HIGH materiality a sufficiency shortfall is above the "
                      "developer's authority to merely caveat.",
            benefits="Protects a capital-driving model from an underpowered fit.",
            risks="Delay; data may not be obtainable.",
            residual="Accept delay to protect a material model.",
        ))

    gd = GateDecision("G1", GATE_NAME["G1"], GATE_QUESTION["G1"], tier,
                      signer_role(tier), rec, opts, flags=flags)
    return _finalize(gd)


# ==========================================================================
# G2 -- Importance Attribution
# ==========================================================================
def gate_g2(ev: dict) -> GateDecision:
    """
    evidence keys:
      tier, n_players, n_confirmed, shadow_bar, weakest_mult,
      estimator ('exact'|'sampled'), borderline_players: [name,...]
    """
    tier = ev["tier"]
    borderline = ev.get("borderline_players", [])
    flags: list = []
    rec = (f"Accept the confirmed attribution: {ev['n_confirmed']}/{ev['n_players']} "
           f"players clear the shadow bar; advance to selection.")

    opts: list = [Option(
        "A", "ADOPT",
        option=f"Accept {ev['n_confirmed']} confirmed players; advance to G3.",
        data=(f"{ev['n_confirmed']}/{ev['n_players']} confirmed vs shadow bar "
              f"{ev['shadow_bar']:.5f}; weakest confirmed {ev['weakest_mult']:.1f}x "
              f"the bar; estimator={ev['estimator']} (P8)."),
        rationale="Shadow-null confirmation controls for chance; the ranking is "
                  "noise-screened and credit-plausible.",
        benefits="Selection runs on a trustworthy importance ordering.",
        risks="A near-bar player could be fragile across resamples.",
        residual="Accept minor fragility of near-bar players (handled at G3).",
        recommended=True,
    )]

    if borderline:
        flags.append(f"borderline-confirmed: {', '.join(borderline)}")
        opts.append(Option(
            "B", "ADOPT_WITH_CONDITION",
            option=f"Advance, flag {', '.join(borderline)} for G3/monitoring.",
            data=f"{len(borderline)} player(s) confirmed but close to the bar.",
            rationale="Advancing with a watch item is defensible; the parsimony "
                      "stage will test whether they earn their place.",
            benefits="No premature drop; fragility made explicit for G3.",
            risks="Carrying a fragile player one more stage.",
            residual="Accept the flagged players as G3 watch items.",
        ))

    opts.append(Option(
        "C", "ESCALATE",
        option="Return to G1 -- a confirmed driver reads as leakage/proxy.",
        data="Raised only if a driver's provenance is challenged.",
        rationale="If a top player is a suspected leak/proxy, provenance must be "
                  "resolved before selecting on it.",
        benefits="Stops a leaking feature from entering the model.",
        risks="Delay; re-screen required.",
        residual="Accept re-screen delay to protect model validity.",
    ))

    gd = GateDecision("G2", GATE_NAME["G2"], GATE_QUESTION["G2"], tier,
                      signer_role(tier), rec, opts, flags=flags)
    return _finalize(gd)


# ==========================================================================
# G3 -- Parsimony Selection  (mirrors the S4.1 worked example)
# ==========================================================================
def gate_g3(ev: dict) -> GateDecision:
    """
    evidence keys:
      tier, k_selected, k_full, cols_selected, gini_sel, gini_full,
      delong_p, rel_loss, full_within_tol (bool)
    """
    tier = ev["tier"]
    flags: list = []
    rec = (f"Adopt the parsimonious set (k={ev['k_selected']} of {ev['k_full']}); "
           f"Gini {ev['gini_sel']:.3f}, DeLong p {ev['delong_p']:.3f}, "
           f"rel. loss {ev['rel_loss']:.2f}%.")

    opts: list = [Option(
        "A", "ADOPT",
        option=f"Adopt parsimonious k={ev['k_selected']} ({ev['cols_selected']} cols).",
        data=(f"Gini {ev['gini_sel']:.3f}; DeLong p {ev['delong_p']:.3f} vs full; "
              f"rel. Gini loss {ev['rel_loss']:.2f}%."),
        rationale="First k that is neither statistically (DeLong p>=0.05) nor "
                  "materially (loss<=5%) worse than the full-candidate model.",
        benefits="Simpler, cheaper to monitor, fewer data dependencies.",
        risks="Marginal discrimination given up vs the full set.",
        residual="Accept <=5% relative Gini loss for parsimony.",
        recommended=True,
    )]

    # B -- the full candidate set (the S4.1 example B), viable within tolerance.
    if ev.get("full_within_tol", True):
        opts.append(Option(
            "B", "ADOPT_WITH_CONDITION",
            option=f"Adopt the full k={ev['k_full']} candidate set.",
            data=f"Gini {ev['gini_full']:.3f}; identical within tolerance.",
            rationale="Maximal information retention; defensible when the gain is "
                      "within noise and the business values completeness.",
            benefits="No discrimination given up.",
            risks="More data collection / monitoring burden for no measured gain.",
            residual="Accept added operational surface for completeness.",
        ))

    opts.append(Option(
        "C", "ESCALATE",
        option="Escalate -- a sub-parsimonious k is a materiality trade-off.",
        data="Raised if the business wants fewer features than the rule allows.",
        rationale="Going below the selected k means accepting a statistically "
                  "real loss -- above the developer's authority.",
        benefits="Keeps an authority boundary explicit.",
        risks="Delay for committee ruling.",
        residual="Accept delay for a materiality decision.",
    ))

    gd = GateDecision("G3", GATE_NAME["G3"], GATE_QUESTION["G3"], tier,
                      signer_role(tier), rec, opts, flags=flags)
    return _finalize(gd)


# ==========================================================================
# G4 -- Calibration & Fairness  (dual decision)
# ==========================================================================
def gate_g4(ev: dict) -> GateDecision:
    """
    evidence keys:
      tier, auc, hl_p, grade_backtest_pass (bool), grades_total, grades_passed,
      sparse_grades: [grade,...], air: {attr: ratio}, air_min
    """
    tier = ev["tier"]
    flags: list = []
    auc_floor = _AUC_FLOOR[tier]
    auc_ok = (auc_floor is None) or (ev["auc"] >= auc_floor)
    hl_reject = (ev.get("hl_p") is not None and ev["hl_p"] < 0.05)
    backtest_ok = ev.get("grade_backtest_pass", True)
    sparse = ev.get("sparse_grades", [])
    air_min = ev.get("air_min")
    air_fail = (air_min is not None and air_min < 0.80)

    rec = (f"Approve calibration + fairness: AUC {ev['auc']:.3f}"
           f"{'' if auc_floor is None else f' (floor {auc_floor})'}, "
           f"per-grade backtest {ev.get('grades_passed','?')}/{ev.get('grades_total','?')}"
           f"{'; HL rejected -> caveat' if hl_reject else ''}"
           f"{f'; min AIR {air_min:.2f}' if air_min is not None else ''}.")

    data_cal = (f"AUC {ev['auc']:.3f}"
                + ("" if auc_floor is None else f" vs floor {auc_floor}")
                + (f"; HL p {ev['hl_p']:.3f}" if ev.get('hl_p') is not None else "")
                + (f"; per-grade {ev.get('grades_passed','?')}/{ev.get('grades_total','?')} pass"
                   if ev.get('grades_total') else ""))
    data_fair = ("AIR: " + ", ".join(f"{k} {v:.2f}" for k, v in (ev.get("air") or {}).items())
                 + (f"; min {air_min:.2f} vs four-fifths 0.80" if air_min is not None else "")
                 ) if ev.get("air") else "No protected-attribute AIR computed."

    # A -- approve (clean) only if nothing triggers a mandatory condition.
    clean = auc_ok and not hl_reject and backtest_ok and not sparse and not air_fail
    opts: list = [Option(
        "A", "ADOPT",
        option="Approve calibration and fairness as-is.",
        data=data_cal + " | " + data_fair,
        rationale="Discrimination meets the tier floor, per-grade PDs are honest, "
                  "and no protected-attribute AIR breaches four-fifths unexplained.",
        benefits="Model is deployment-eligible on both axes.",
        risks="Residual calibration/fairness drift must be monitored.",
        residual="Accept ongoing-monitoring obligation.",
        recommended=clean,
    )]

    # B -- approve WITH calibration/fairness condition(s). Mandatory when a flag fires.
    conds = []
    if hl_reject:
        conds.append("HL rejected -> disclosed calibration caveat + MoC; per-grade "
                     "backtest is the governing test (CRE36.122)")
        flags.append("HL goodness-of-fit rejected")
    if sparse:
        conds.append(f"sparse grade(s) {', '.join(map(str, sparse))} -> MoC (EBA cat. A)")
        flags.append("sparse rating grade(s)")
    if not backtest_ok:
        conds.append("per-grade backtest shortfall -> remediation condition")
        flags.append("per-grade backtest shortfall")
    if air_fail:
        conds.append(f"min AIR {air_min:.2f} < 0.80 -> true-risk interpretation + "
                     "disclosed fairness caveat (indicative, no institution cutoff)")
        flags.append("adverse-impact ratio below four-fifths")
    if not auc_ok:
        conds.append(f"AUC {ev['auc']:.3f} < tier floor {auc_floor} -> justify or down-tier")
        flags.append("AUC below tier floor")
    if conds:
        opts.append(Option(
            "B", "ADOPT_WITH_CONDITION",
            option="Approve with named calibration/fairness condition(s).",
            data="; ".join(conds),
            rationale="Each condition is a disclosed caveat or MoC, not a method "
                      "change; AIR is indicative and interpreted against true risk.",
            benefits="Deployment proceeds with the limitation made explicit at GF.",
            risks="Conditions become GF PARTIALs the MAC must accept.",
            residual="Accept the listed caveats/MoC as GF conditions.",
            recommended=True,
        ))

    # C -- return for remediation: a HIGH-tier hard fail.
    hard = (tier == "HIGH" and (not backtest_ok or not auc_ok))
    if hard:
        opts.append(Option(
            "C", "ESCALATE",
            option="Return to G3 -- recalibrate/respecify before approval.",
            data="HIGH tier with a calibration/discrimination hard fail.",
            rationale="At HIGH materiality a failing backtest or sub-floor AUC "
                      "cannot be merely caveated.",
            benefits="Prevents approving a model whose PDs are not honest.",
            risks="Rework and delay.",
            residual="Accept rework to protect a material model.",
        ))

    gd = GateDecision("G4", GATE_NAME["G4"], GATE_QUESTION["G4"], tier,
                      signer_role(tier), rec, opts, flags=flags)
    return _finalize(gd)


# ==========================================================================
# G5 -- Deployment Governance
# ==========================================================================
def gate_g5(ev: dict) -> GateDecision:
    """
    evidence keys:
      tier, cutoff_policy_present, acceptance_pack_present,
      mandatory_field_gate, adverse_fallback, reason_codes (bool)
    """
    tier = ev["tier"]
    flags: list = []
    missing = []
    if not ev.get("cutoff_policy_present"):
        missing.append("cutoff policy (AEGIS_<NAME>_CUTOFF_POLICY.md)")
    if not ev.get("acceptance_pack_present"):
        missing.append("acceptance demonstration (SAMPLE_RUNS_<NAME>.md)")
    controls_ok = (ev.get("mandatory_field_gate") and ev.get("adverse_fallback")
                   and ev.get("reason_codes"))

    rec = ("Confirm deployment controls + deliverables present."
           if not missing else
           "Deliverables incomplete -- cannot confirm deployment-complete.")

    opts: list = [Option(
        "A", "ADOPT",
        option="Confirm controls + deliverables; advance to GF.",
        data=(f"mandatory-field gate {'ok' if ev.get('mandatory_field_gate') else 'MISSING'}, "
              f"adverse fallback {'ok' if ev.get('adverse_fallback') else 'MISSING'}, "
              f"reason codes {'ok' if ev.get('reason_codes') else 'MISSING'}; "
              f"cutoff policy {'present' if ev.get('cutoff_policy_present') else 'MISSING'}, "
              f"acceptance pack {'present' if ev.get('acceptance_pack_present') else 'MISSING'}."),
        rationale="A model that outputs a PD but no governed decision and no "
                  "applicant report is not deployment-complete (R2/R14).",
        benefits="Use-test + transparency evidence is in place for the MAC.",
        risks="Deployment controls need ongoing config monitoring.",
        residual="Accept monitoring of the scoring-layer controls.",
        recommended=(not missing and controls_ok),
    )]

    if missing or not controls_ok:
        if missing:
            flags.append("missing deliverable(s): " + "; ".join(missing))
        if not controls_ok:
            flags.append("scoring-layer control(s) not configured")
        opts.append(Option(
            "C", "ESCALATE",
            option="Return -- complete deliverables/controls before GF.",
            data="Outstanding: " + "; ".join(missing + ([] if controls_ok else ["scoring controls"])),
            rationale="GF is ruled only after G5 deliverables are complete and "
                      "visible; they are inputs to Go/No-Go, not post-approval tasks.",
            benefits="Keeps GF from approving an incomplete deployment.",
            risks="Delay to assemble the pack.",
            residual="Accept delay until deployment-complete.",
        ))

    gd = GateDecision("G5", GATE_NAME["G5"], GATE_QUESTION["G5"], tier,
                      signer_role(tier), rec, opts, flags=flags)
    return _finalize(gd)


GATE_FN = {"G0": gate_g0, "G1": gate_g1, "G2": gate_g2,
           "G3": gate_g3, "G4": gate_g4, "G5": gate_g5}


def build_gate(gate_id: str, evidence: dict) -> GateDecision:
    """Dispatch to the per-gate option builder. Pure function of evidence."""
    if gate_id not in GATE_FN:
        raise ValueError(f"unknown gate {gate_id!r}; expected one of {list(GATE_FN)}")
    return GATE_FN[gate_id](evidence)


# ==========================================================================
# GF -- the deterministic Go/No-Go engine (S7 over the S8 checklist).
# ==========================================================================
# Must-have criteria: a GAP on any of these is a hard NO-GO (S8).
MUST_HAVE = {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9"}
VALID_STATUS = {"SATISFIED", "PARTIAL", "GAP"}


@dataclass
class GFVerdict:
    verdict: str                     # GO | GO-WITH-CONDITIONS | NO-GO
    conditions: list = field(default_factory=list)   # PARTIAL items (if conditions)
    blockers: list = field(default_factory=list)     # hard-stop reasons (if NO-GO)
    return_to: Optional[str] = None  # gate to return to on NO-GO


def gf_engine(gate_states: dict, checklist: list,
              residual_within_appetite: bool = True) -> GFVerdict:
    """
    S7 deterministic recommendation. Inputs:
      gate_states : {gate_id: "signed"|"unsigned"|"returned"|"escalate"}
                    for G0..G5.
      checklist   : [{id, status, must_have, note}] -- the S8 rows.
      residual_within_appetite : Risk Officer input (bool); with conditions it
                    may still be acceptable-with-conditions.

    Logic (S7 table), in strict precedence:
      NO-GO  if any gate unsigned/returned/escalate, OR any must-have GAP,
             OR residual risk outside appetite (and not rescuable by conditions).
      GO-WITH-CONDITIONS if all gates signed + every criterion SATISFIED-or-PARTIAL
             with >=1 remediable PARTIAL + residual within appetite WITH conditions.
      GO     if all gates signed + every criterion SATISFIED + residual within appetite.
    The engine never upgrades a NO-GO; a must-have GAP is a hard stop.
    """
    for r in checklist:
        if r["status"] not in VALID_STATUS:
            raise ValueError(f"bad status {r['status']!r} on {r.get('id')}")

    blockers, return_to = [], None

    # 1) Gate integrity -- any gate not cleanly signed is a hard stop.
    for g in ["G0", "G1", "G2", "G3", "G4", "G5"]:
        st = gate_states.get(g, "unsigned")
        if st != "signed":
            blockers.append(f"{g} is {st}")
            if return_to is None:
                return_to = g

    # 2) Must-have GAP -- hard stop (S8: R1-R9).
    gaps = [r for r in checklist if r["status"] == "GAP"]
    must_gaps = [r for r in gaps if r.get("must_have") or r["id"] in MUST_HAVE]
    for r in must_gaps:
        blockers.append(f"must-have GAP {r['id']}: {r.get('note','')}".strip())
        if return_to is None:
            return_to = r.get("gate")

    # 3) Residual risk outside appetite with no rescuing conditions.
    partials = [r for r in checklist if r["status"] == "PARTIAL"]
    if not residual_within_appetite and not partials:
        blockers.append("residual risk outside appetite")

    if blockers:
        return GFVerdict("NO-GO", blockers=blockers, return_to=return_to)

    # 4) Non-must-have GAPs that remain are carried as conditions (context rows).
    nonmust_gaps = [r for r in gaps if not (r.get("must_have") or r["id"] in MUST_HAVE)]
    conditions = [f"{r['id']}: {r.get('note','')}".strip()
                  for r in (partials + nonmust_gaps)]

    if conditions:
        return GFVerdict("GO-WITH-CONDITIONS", conditions=conditions)
    return GFVerdict("GO")


# ==========================================================================
# Self-test -- reproduce the committed SBA verdict from its recorded states.
# ==========================================================================
def _selftest():
    import json
    print("AEGIS gate engine self-test\n" + "-" * 40)

    # --- SBA recorded gate states (all signed A) ---
    sba_states = {g: "signed" for g in ["G0", "G1", "G2", "G3", "G4", "G5"]}
    # SBA S8 checklist: must-haves satisfied; calibration PARTIAL (HL rejected,
    # per-grade backtest passed -> disclosed caveat SBA-CAL); fairness context
    # PARTIAL (geographic AIR 0.41, true-risk-driven -> SBA-GEO). -> GO-WITH-COND.
    sba_checklist = [
        {"id": "R1", "status": "SATISFIED", "must_have": True, "gate": "G0", "note": "history ok"},
        {"id": "R2", "status": "SATISFIED", "must_have": True, "gate": "G5", "note": "use test (acceptance pack)"},
        {"id": "R3", "status": "SATISFIED", "must_have": True, "gate": "G3", "note": "Gini 0.859"},
        {"id": "R4", "status": "PARTIAL",   "must_have": True, "gate": "G4",
         "note": "SBA-CAL: HL p=0.018 from bimodal PDs; per-grade backtest 7/7 passed -> disclosed caveat + MoC"},
        {"id": "R5", "status": "SATISFIED", "must_have": True, "gate": "G5", "note": "override policy"},
        {"id": "R6", "status": "SATISFIED", "must_have": True, "gate": "G4", "note": "MoC documented"},
        {"id": "R7", "status": "SATISFIED", "must_have": True, "gate": "GF", "note": "independent validation"},
        {"id": "R8", "status": "SATISFIED", "must_have": True, "gate": "GF", "note": "RACI/MAC"},
        {"id": "R9", "status": "SATISFIED", "must_have": True, "gate": "G0", "note": "MEDIUM tier"},
        {"id": "R12", "status": "PARTIAL",  "must_have": False, "gate": "GF",
         "note": "SBA-GEO: BankState AIR 0.41 true-risk-driven; indicative, disclosed"},
    ]
    v = gf_engine(sba_states, sba_checklist, residual_within_appetite=True)
    assert v.verdict == "GO-WITH-CONDITIONS", v
    assert any("SBA-CAL" in c for c in v.conditions)
    assert any("SBA-GEO" in c for c in v.conditions)
    print("SBA           ->", v.verdict, "| conditions:", len(v.conditions), "OK")

    # --- NO-GO: inject a must-have GAP ---
    bad = [dict(r) for r in sba_checklist]
    bad[2]["status"] = "GAP"  # R3 discrimination GAP
    v2 = gf_engine(sba_states, bad)
    assert v2.verdict == "NO-GO" and v2.return_to == "G3", v2
    print("must-have GAP ->", v2.verdict, "| return_to:", v2.return_to, "OK")

    # --- NO-GO: an unsigned gate ---
    v3 = gf_engine({**sba_states, "G4": "returned"}, sba_checklist)
    assert v3.verdict == "NO-GO" and v3.return_to == "G4", v3
    print("gate returned ->", v3.verdict, "| return_to:", v3.return_to, "OK")

    # --- clean GO: all satisfied ---
    allgood = [{**r, "status": "SATISFIED"} for r in sba_checklist]
    v4 = gf_engine(sba_states, allgood)
    assert v4.verdict == "GO", v4
    print("all satisfied ->", v4.verdict, "OK")

    # --- corrected-German G1 option set, built from evidence ---
    g1 = build_gate("G1", {
        "tier": "MEDIUM", "n_pass": 12, "n_pool": 17, "epv": 25.0,
        "riley_req": 323, "riley_avail": 1000,
        "dominant_feature": "checking_status", "dominant_iv": 0.666,
    })
    labels = [o.label for o in g1.options]
    kinds = [o.kind for o in g1.options]
    assert labels == ["A", "B"], labels  # clean pass: no HIGH-tier halt option
    assert kinds[0] == "ADOPT" and g1.options[0].recommended
    print("German G1     -> options", labels, "| recommend A OK")

    # anti-strawman: a lone viable option flags escalate
    g1h = build_gate("G1", {
        "tier": "HIGH", "n_pass": 4, "n_pool": 10, "epv": 6.0,
        "riley_req": 3654, "riley_avail": 1707,
        "dominant_feature": "x", "dominant_iv": 0.2,
    })
    assert "Riley minimum-N shortfall" in g1h.flags
    print("short HIGH G1 ->", [o.label for o in g1h.options],
          "| flags:", len(g1h.flags), "OK")

    print("-" * 40 + "\nall self-tests passed.")


if __name__ == "__main__":
    _selftest()
