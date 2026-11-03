"""RBI rows in the application's governance module (backend/governance_store.regulatory_mapping).

Plain script (like the rest of testing/): prints PASS/FAIL, exits non-zero on failure. Uses a throwaway sqlite database.

    .\\venv310\\Scripts\\python.exe testing\\test_governance_rbi.py
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'backend'))
from backend import governance_store as gov

fails = []


def check(label, ok):
    print(('PASS  ' if ok else 'FAIL  ') + label, flush=True)
    if not ok:
        fails.append(label)


db = os.path.join(tempfile.mkdtemp(prefix='gov_rbi_'), 'g.db')
conn = sqlite3.connect(db)
gov.init_schema(conn)
SLOT = 'CORPORATE'
m = gov.regulatory_mapping(conn, SLOT)
rows = {r['requirement']: r for r in m['requirements']}
RBI = [k for k in rows if k.startswith('RBI:')]

check('seven original requirements are still present', all(k in rows for k in (
    'Governance & Accountability', 'Independent Validation', 'Documentation', 'Stress Testing', 'Ongoing Monitoring',
    'Human Oversight', 'Transparency')))
check('six RBI requirements are added', len(RBI) == 6 and m['total'] == 13)
check('every RBI row names its source and a legal status (draft or recommendation, never binding)',
      all(rows[k].get('source') and ('draft' in rows[k]['legal_status'] or 'recommend' in rows[k]['legal_status']) for k in RBI)
      and not any('binding' == rows[k]['legal_status'] for k in RBI))
check('RBI rows carry the RBI framework tags', all(any(f.startswith('RBI') for f in rows[k]['frameworks']) for k in RBI))
check('existing rows are retagged where the RBI text asks for the same thing',
      gov.RBI_MRM in rows['Independent Validation']['frameworks'] and gov.RBI_MRM in rows['Documentation']['frameworks']
      and gov.RBI_MRM in rows['Ongoing Monitoring']['frameworks'] and gov.RBI_FREE_AI in rows['Human Oversight']['frameworks'])
check('statuses use the existing vocabulary', all(r['status'] in ('SATISFIED', 'PARTIAL', 'GAP') for r in m['requirements']))
check('satisfied count covers all rows', m['satisfied'] == sum(1 for r in m['requirements'] if r['status'] == 'SATISFIED'))

# tier proposal: anti-dilution
p_log, p_xgb = gov.rbi_tier_proposal('logistic_regression'), gov.rbi_tier_proposal('xgboost')
check('tier proposal: low complexity does not dilute high materiality (logistic scorecard still HIGH)',
      p_log['proposed'] == 'HIGH' and p_log['complexity'] == 'LOW' and p_xgb['proposed'] == 'HIGH')
t = rows['RBI: Risk Tiering and Model Risk Framework']
check('tier row: the seeded wiki tier HIGH meets the proposal', 'Recorded tier HIGH' in t['evidence'] and t['status'] in ('SATISFIED', 'PARTIAL'))
conn.execute("UPDATE gov_wiki_entries SET risk_tier='LOW' WHERE slot_key=?", (SLOT,))
conn.commit()
rows2 = {r['requirement']: r for r in gov.regulatory_mapping(conn, SLOT)['requirements']}
check('tier row: a tier below the proposal is not SATISFIED', rows2['RBI: Risk Tiering and Model Risk Framework']['status'] != 'SATISFIED')
conn.execute("UPDATE gov_wiki_entries SET risk_tier='HIGH' WHERE slot_key=?", (SLOT,))
conn.commit()

# independent validation: the validator must not be a wiki author
iv = 'RBI: Independent Validation (independent of development)'
check('validation row: GAP with no sign-off', rows[iv]['status'] == 'GAP')
for p in gov.PILLARS:
    gov.sign_off(conn, SLOT, p, 'system', 'SIGNED_OFF', 'self check')
author = conn.execute("SELECT updated_by FROM gov_wiki_entries WHERE slot_key=?", (SLOT,)).fetchone()[0]
conn.execute("UPDATE gov_wiki_entries SET updated_by='Dev One' WHERE slot_key=?", (SLOT,))
conn.execute("INSERT INTO gov_wiki_versions (slot_key, version, edited_at, edited_by, change_description, fields_json) VALUES (?,2,'t','Dev One','edit','{}')", (SLOT,))
conn.commit()
for p in gov.PILLARS:
    gov.sign_off(conn, SLOT, p, 'Dev One', 'SIGNED_OFF', 'same person signed')
r3 = {r['requirement']: r for r in gov.regulatory_mapping(conn, SLOT)['requirements']}
check('validation row: all six signed by the wiki author is only PARTIAL (not independent)',
      r3[iv]['status'] == 'PARTIAL' and 'independence is not shown' in r3[iv]['evidence'])
for p in gov.PILLARS:
    gov.sign_off(conn, SLOT, p, 'Independent Reviewer', 'SIGNED_OFF', 'a different person signed')
r4 = {r['requirement']: r for r in gov.regulatory_mapping(conn, SLOT)['requirements']}
check('validation row: all six signed by someone other than the author is SATISFIED', r4[iv]['status'] == 'SATISFIED')
check('the existing Independent Validation row is unchanged in meaning (complete sign-off)', r4['Independent Validation']['status'] == 'SATISFIED')

# behavioural risks stay PARTIAL: 54(5) and 54(6) are not measured, and the row says so
b = rows['RBI: Behavioural Risk Controls (Draft para 54)']
check('behavioural row: never SATISFIED, and names the two unmeasured items',
      b['status'] != 'SATISFIED' and '54(5) spurious correlations: NO' in b['evidence'] and '54(6) output variability: NO' in b['evidence'])
# change management reads the application thresholds and the chain
c = rows['RBI: Change Management and Material-Change Thresholds']
check('change-management row quotes the application thresholds and the chain state',
      'PSI above' in c['evidence'] and 'intact' in c['evidence'])
check('audit chain is intact after all of the above', gov.verify_chain(conn)['intact'])
check('retention is stated as ten years', gov.RETENTION_YEARS == 10 and '10 years' in rows['RBI: Model Inventory, Documentation and Retention']['evidence'])
check('seeded regulatory references no longer cite an unverified "RBI IRB guidelines"',
      'RBI IRB' not in gov.DEFAULT_PROSE['regulatory_references'] and 'consultation draft' in gov.DEFAULT_PROSE['regulatory_references'])

print('\n%d failure(s)' % len(fails))
sys.exit(1 if fails else 0)
