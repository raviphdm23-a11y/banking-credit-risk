"""
regime_registry.py - the single source for the regulatory acceptance checklist rows.

WHY THIS EXISTS
---------------
Before this module the checklist metadata (which gate produces the evidence, which rows are must-haves, which
regime a context row belongs to, what closes a partial row, the readiness-panel names) was scattered over four
dictionaries in staged_run.py. The Indian (RBI) pack adds six rows, so the metadata now lives here and staged_run.py
reads it. R1-R14 are copied UNCHANGED from the previous literals; testing/test_rbi_regime.py compares them with a
frozen copy of those literals, so a drift is caught.

RULES
-----
* A row built on text we have NOT read is registered as `verified=False` and is never scored (no invented rules).
* Every Indian row carries its legal status (the RBI Draft is a consultation text, FREE-AI is a recommendations
  report) and the SHA-256 of the file it was read from, so a sealed run states exactly which text it was assessed
  against.
* Rows R15-R20 are conditions, not must-haves, while the source is a draft (decision 3 Nov 2026). In the
  regulatory-use reading R15 and R16 block (`must_have_strict`). `PROMOTE_WHEN_FINAL` lists the rows that become
  must-haves the day RBI issues a final text: flip FINAL_RBI_ISSUED to True and re-verify the wording first.

ASCII-only strings (Windows cp1252 console).
"""
PACK_VERSION = '2026-11-03'

# Flip only after RBI issues a final guidance AND the wording of rows R15-R20 has been re-verified against it.
FINAL_RBI_ISSUED = False
PROMOTE_WHEN_FINAL = ('R15', 'R16', 'R17', 'R18', 'R19', 'R20')

# The two RBI texts the Indian pack was built from (read in full on 2026-11-03).
RBI_SOURCES = {
    'IN_RBI_MRM_DRAFT_2026': {
        'title': 'RBI, Guidance on Regulatory Principles for Model Risk Management, 2026 (draft for consultation)',
        'file': 'important papers/papers/RBI folder/RBI_Draft_Guidance_Model_Risk_Management_2026-06-24.pdf',
        'sha256': 'b32a0e243c8bcf3b8e534dce1852d2bb33f04571e6ba40918c20656899cca1b4',
        'legal_status': 'draft for consultation (reference DoR.ORG.REC.XXXX/XX-XX-XXXX/2026-27, date "June xx, 2026")',
        'verified_on': '2026-11-03', 'read': 'in full from the PDF',
    },
    'IN_RBI_FREE_AI_2025': {
        'title': 'RBI FREE-AI Committee, Framework for Responsible and Ethical Enablement of AI in the Financial Sector (report, 13 Aug 2025)',
        'file': 'important papers/papers/RBI folder/RBI_FREE-AI_Committee_Report_2025-08-13.pdf',
        'sha256': '569d0385ebac89a629f647522cca5772f822dcc39270515d9426083b699419d8',
        'legal_status': 'committee report with recommendations; not a regulation',
        'verified_on': '2026-11-03', 'read': 'in full from the PDF',
    },
}

# Documents named in the plan but NOT yet read. Registered, never scored.
PENDING_SOURCES = {
    'IN_RBI_ECL_DIRECTIONS_2026': 'Asset Classification, Provisioning and Income Recognition Directions, 2026 (ECL; in force 1 Apr 2027)',
    'IN_RBI_IRAC_DEFAULT_DEFINITION': 'RBI asset-classification rules defining default (days past due, SMA/NPA)',
    'IN_RBI_BASEL3_CAPITAL': 'RBI Basel III capital adequacy Master Direction (use of external ratings)',
}

# regime keys that gate rows R11-R20 (declared at G0 by standard_run.default_regimes)
IN_REGIME_KEYS = ('IN_RBI_MRM_DRAFT_2026', 'IN_RBI_FREE_AI_2025')


def _row(rid, name, gate, regime=None, must_have=False, must_have_strict=False, action=None, owner=None,
         source='', status='binding', verified=True):
    return {'id': rid, 'name': name, 'gate': gate, 'regime': regime, 'must_have': must_have,
            'must_have_strict': must_have_strict, 'closing_action': action, 'owner': owner,
            'source': source, 'legal_status': status, 'verified': verified,
            'scope': 'IN' if regime in IN_REGIME_KEYS else 'ALL'}


# R1-R14: identical to the literals that were in staged_run.py (gate, must-have, regime, closing action, name).
ROWS = [
    _row('R1', 'PD data history >= 5 years', 'G0', must_have=True, source='Basel CRE36.79',
         action='Verify the observation window of the PD data (data-owner statement or dated records)', owner='Data Steward / data owner'),
    _row('R2', 'Use test', 'G5', must_have=True, source='Basel CRE36.60',
         action='Complete the cutoff note and acceptance pack, and show the PDs feed real decisions', owner='Model Owner'),
    _row('R3', 'Risk differentiation', 'G3', must_have=True, source='Basel CRE36.18-21',
         action='Justify or down-tier if discrimination is below the tier floor or no k meets the tolerance', owner='Model Validator'),
    _row('R4', 'Calibration backtest', 'G4', must_have=True, source='Basel CRE36.122-123',
         action='Resolve failing grades and the HL result, or document them with an ongoing-monitoring plan', owner='Risk Officer'),
    _row('R5', 'Override governance', 'G5', must_have=True, source='Basel CRE36.44',
         action='Configure and document the override / refer controls', owner='Model Owner'),
    _row('R6', 'Margin of Conservatism', 'G4', must_have=True, source='EBA/GL/2017/16',
         action='Quantify the Margin of Conservatism by category (EBA A/B/C) and address the EPV shortfall', owner='Model Owner + Risk Officer'),
    _row('R7', 'Independent validation', 'GF', must_have=True, source='SR 26-2',
         action='Appoint a validator independent of the developer', owner='MAC Chair'),
    _row('R8', 'Governance and accountability', 'GF', must_have=True, source='SR 26-2',
         action='Separate developer, validator and approver roles and constitute the committee', owner='MAC Chair + CRO'),
    _row('R9', 'Risk-proportionate rigour', 'G0', must_have=True, source='SR 26-2',
         action='Assign the materiality tier at G0', owner='Data Steward'),
    _row('R10', 'Data governance / completeness', 'G0', source='BCBS 239',
         action='Explain or resolve blank patterns that track the outcome; lineage and completeness report', owner='Data Steward'),
    _row('R11', 'Model risk management principles (PRA SS1/23)', 'GF', regime='UK_PRA_SS1_23', source='PRA SS1/23',
         action='Map the lifecycle to the PRA SS1/23 principles and record the assessment', owner='Model Owner'),
    _row('R12', 'High-risk AI obligations (EU AI Act)', 'GF', regime='EU_AI_ACT_HIGH_RISK', source='EU AI Act, Annex III 5(b)',
         action='Record the Art 9/10/12/13/14 assessment for natural-person credit scoring', owner='Model Owner'),
    _row('R13', 'Human-oversight operability (EU AI Act Art 14)', 'GF', regime='EU_AI_ACT_HUMAN_OVERSIGHT', source='EU AI Act, Art. 14',
         action='Show that overseers can understand, decline and halt the model output', owner='Model Owner'),
    _row('R14', 'Adverse-action reasons (ECOA / Reg B)', 'GF', regime='US_ECOA_REG_B', source='ECOA / Reg B',
         action='Provide specific principal reasons for adverse action', owner='Model Owner'),
    # ---- Indian pack (RBI). Draft / recommendation text: conditions, not must-haves (R15, R16 block in the regulatory-use reading).
    _row('R15', 'Model risk framework, tier and use statement (RBI)', 'G0', regime='IN_RBI_MRM_DRAFT_2026',
         must_have_strict=True, status='draft', source='RBI Draft paras 9-20, 26; FREE-AI 4.4.44',
         action='Record a written intended-use statement, a board-approved framework reference, and a tier not below the anti-dilution proposal (or a recorded justification)',
         owner='Model Owner + MAC Chair'),
    _row('R16', 'Independent validation and validation report (RBI)', 'GF', regime='IN_RBI_MRM_DRAFT_2026',
         must_have_strict=True, status='draft', source='RBI Draft paras 7(8), 15, 29-33; FREE-AI 4.4.51',
         action='Appoint a validator independent of development, ownership and use, and place the validation report before the committee within three months',
         owner='MAC Chair'),
    _row('R17', 'Inventory, documentation, dependencies, retention (RBI)', 'G5', regime='IN_RBI_MRM_DRAFT_2026',
         status='draft', source='RBI Draft paras 21-24, 57; FREE-AI Rec 16, 23',
         action='Write the model inventory card, list upstream dependencies, and state a retention period of at least ten years after decommissioning',
         owner='Model Owner'),
    _row('R18', 'Behavioural risks: explainability, fairness, generalisation, spurious correlation, stability, data drift (RBI)', 'G5',
         regime='IN_RBI_MRM_DRAFT_2026', status='draft', source='RBI Draft para 54(1)-(7), 55',
         action='Close each open sub-item of para 54 (see the row note) or document it with a monitoring plan', owner='Model Validator'),
    _row('R19', 'Change management, material-change threshold, monitoring (RBI)', 'G5', regime='IN_RBI_MRM_DRAFT_2026',
         status='draft', source='RBI Draft paras 36-42; FREE-AI Rec 21',
         action='Declare the material-change criteria and a monitoring plan; revalidate if the run itself breaches them', owner='Risk Officer'),
    _row('R20', 'Human oversight, override, periodic human review (RBI)', 'G5', regime='IN_RBI_FREE_AI_2025',
         status='recommendation', source='RBI Draft paras 60-63; FREE-AI 4.4.62',
         action='Document the override path and a periodic human review of a sample of decisions', owner='Model Owner'),
]
_BY_ID = {r['id']: r for r in ROWS}


def ids(india=False):
    """Row ids in order. R15-R20 only when the Indian pack is declared."""
    return [r['id'] for r in ROWS if india or r['scope'] == 'ALL']


def row(rid):
    return _BY_ID[rid]


def checklist_gate():
    return {r['id']: r['gate'] for r in ROWS}


def must_have_rows():
    """Static must-haves (R1-R9). Rows R15-R20 join only after FINAL_RBI_ISSUED is set."""
    base = [r['id'] for r in ROWS if r['must_have']]
    return base + ([i for i in PROMOTE_WHEN_FINAL] if FINAL_RBI_ISSUED else [])


def regime_of(prefix_ids=('R11', 'R12', 'R13', 'R14')):
    return {i: _BY_ID[i]['regime'] for i in prefix_ids}


def in_regime_of():
    return {r['id']: r['regime'] for r in ROWS if r['scope'] == 'IN'}


def closing_actions():
    return {r['id']: (r['closing_action'], r['owner']) for r in ROWS if r['closing_action']}


def names():
    return {r['id']: r['name'] for r in ROWS}


def provenance():
    """What a sealed run records at G0 about the Indian pack."""
    return {'pack_version': PACK_VERSION, 'sources': RBI_SOURCES, 'pending_not_scored': PENDING_SOURCES,
            'final_rbi_issued': FINAL_RBI_ISSUED}
