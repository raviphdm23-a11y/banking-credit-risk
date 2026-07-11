"""
backfill_case_macro_regime.py
────────────────────────────────
Backfills the missing `macro_regime` key onto existing rm_cases' stored
machine_json.

decision_orchestrator.orchestrate() never copied `macro_regime` from the
raw assessment findings into the M object that actually gets persisted
(see the same-session fix to decision_orchestrator.py), so every case
created before that fix has no macro_regime block at all - the Macro
Regime Score section on report-underwriter.html's ?case=<id> view is
blank for all of them.

Two backfill sources, in priority order:
  1. M['model_inputs_resolved'] - the EXACT resolved feature vector the
     model was scored on at assessment time (includes macro_regime_score
     and the 4 delta_* features). This is the faithful, historically-
     accurate source where it exists.
  2. Live lookup_country_macro() against the case's application.country_code
     - only used when model_inputs_resolved is missing entirely (older
     cases that predate that field too). This is CURRENT macro data, not
     what was actually in effect at assessment time - a labelled
     approximation, same spirit as this session's other synthetic-data
     backfills, not a fabricated-from-nothing value.

Idempotent - skips any case that already has a populated macro_regime.

Run: python operations/scripts/backfill_case_macro_regime.py
"""

import os
import sys
import json
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from backend.feature_meta import lookup_country_macro

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'bank.db')


def _mrs_label(mrs):
    if mrs <= 25: return 'Normal'
    if mrs <= 55: return 'Moderate Stress'
    return 'Severe Distress'


def _build_macro_regime(macro: dict) -> dict:
    """Identical shape/formula to assessment_engine.assess()'s macro_regime block."""
    mrs = float(macro.get('macro_regime_score', 0.0))
    label = _mrs_label(mrs)
    return {
        "score":                  round(mrs, 1),
        "label":                  label,
        "delta_gdp_pct":          round(float(macro.get('delta_gdp_pct', 0.0)), 2),
        "delta_unemployment_pct": round(float(macro.get('delta_unemployment_pct', 0.0)), 2),
        "delta_policy_rate_pct":  round(float(macro.get('delta_policy_rate_pct', 0.0)), 2),
        "delta_cpi_pct":          round(float(macro.get('delta_cpi_pct', 0.0)), 2),
        "interpretation": (
            "No significant regime shift detected — standard cycle conditions." if mrs <= 25
            else "Moderate macro stress — cyclical headwinds elevating default probability." if mrs <= 55
            else "Severe macro distress — COVID/crisis-era conditions; PD materially elevated."
        ),
    }


def run(db_path=DB):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT case_id, machine_json FROM rm_cases")
    rows = cur.fetchall()

    from_resolved, from_lookup, skipped, unresolved = 0, 0, 0, 0
    for case_id, mj in rows:
        M = json.loads(mj)
        if M.get('macro_regime'):
            skipped += 1
            continue

        mir = M.get('model_inputs_resolved') or {}
        if mir and 'macro_regime_score' in mir:
            macro_regime = _build_macro_regime(mir)
            from_resolved += 1
        else:
            country_code = (M.get('application') or {}).get('country_code') or 'IND'
            macro = lookup_country_macro(country_code, db_path)
            if not macro:
                unresolved += 1
                print(f"  ! {case_id}: no model_inputs_resolved and no country_macro "
                      f"match for '{country_code}' - skipping.")
                continue
            macro_regime = _build_macro_regime(macro)
            from_lookup += 1

        M['macro_regime'] = macro_regime
        cur.execute("UPDATE rm_cases SET machine_json=? WHERE case_id=?",
                     (json.dumps(M, default=str), case_id))
        print(f"  {case_id}: MRS={macro_regime['score']} [{macro_regime['label']}] "
              f"(source: {'model_inputs_resolved' if mir and 'macro_regime_score' in mir else 'country_macro lookup'})")

    conn.commit()
    conn.close()

    print(f"\nDone. Backfilled {from_resolved} from model_inputs_resolved, "
          f"{from_lookup} from live country_macro lookup, "
          f"{skipped} already had macro_regime, {unresolved} unresolved.")


if __name__ == "__main__":
    run()
