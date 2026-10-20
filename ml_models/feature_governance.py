"""
feature_governance.py - Stage 0 of METHODOLOGY.md v3 (section 3).

Feature eligibility and data-governance review. Runs BEFORE any statistics.

Two orthogonal classifications are produced per column:

  eligibility   permissible | prohibited | proxy_risk | unclear
                Regulatory admissibility as an input to a consumer credit
                decision (US ECOA/Regulation B; the EU AI Act Annex III treats
                creditworthiness assessment as high-risk; national equality
                law). See METHODOLOGY.md v3 section 3.1.

  availability  origination | behavioural | near_target | external_score
                When the value is observable relative to the credit decision,
                and whether it is partially definitional of the target or the
                output of another model. See METHODOLOGY.md v3 section 3.3.

PROJECT DECISION (data owner, 2026-10-09): prohibited and proxy_risk columns
are RETAINED in the analysis, with mandatory warning and disclosure. This
module therefore NEVER drops a column. It tags, warns, and emits the standard
disclosure text. The justification (public research benchmarks; comparability
with published literature on the same datasets; no model here is intended for
deployment) is reproduced verbatim by `disclosure_block()`.

Deliberately ASCII-only in all emitted strings - the project runs on Windows
consoles with a cp1252 default codec, which raises UnicodeEncodeError on
non-ASCII output.
"""
import re
import warnings

import pandas as pd

PERMISSIBLE = 'permissible'
PROHIBITED = 'prohibited'
PROXY_RISK = 'proxy_risk'
UNCLEAR = 'unclear'

ORIGINATION = 'origination'
BEHAVIOURAL = 'behavioural'
NEAR_TARGET = 'near_target'
EXTERNAL_SCORE = 'external_score'

INELIGIBLE_TAGS = (PROHIBITED, PROXY_RISK)

# ---------------------------------------------------------------------------
# Eligibility rules. Ordered - first match wins. Patterns are matched
# case-insensitively against the full column name (fullmatch) or as a
# substring, per the mode field ('full' or 'sub').
# ---------------------------------------------------------------------------
_ELIGIBILITY_RULES = [
    # --- directly prohibited: sex / marital status / age / national origin ---
    (r'sex', 'full', PROHIBITED, 'Sex - prohibited basis (ECOA/Reg B).'),
    (r'gender', 'full', PROHIBITED, 'Sex/gender - prohibited basis (ECOA/Reg B).'),
    (r'personal_status_sex', 'full', PROHIBITED,
     'Combined sex and marital status - prohibited basis (ECOA/Reg B).'),
    (r'marriage|marital.*status|personal_status.*', 'full', PROHIBITED,
     'Marital status - prohibited basis (ECOA/Reg B).'),
    (r'age', 'full', PROHIBITED,
     'Age - prohibited basis (ECOA/Reg B, narrow exceptions only).'),
    (r'birth.*date|date.*birth|dob|yob|year_?of_?birth', 'full', PROHIBITED,
     'Date/year of birth implies age - prohibited basis (ECOA/Reg B). Note `YOB` is a '
     'standard credit-scoring abbreviation and is frequently stored as a two-digit year, '
     'which is easy to mistake for an ordinary numeric feature.'),
    (r'spouse.*inc.*|.*spouse.*salary.*|sinc', 'full', PROHIBITED,
     'Spouse income reveals marital status - prohibited basis (ECOA/Reg B).'),
    (r'foreign_worker|citizenship|immigra', 'sub', PROHIBITED,
     'National origin / immigration status - prohibited basis (ECOA/Reg B).'),
    (r'race|ethnic|religio', 'sub', PROHIBITED,
     'Race / ethnicity / religion - prohibited basis (ECOA/Reg B).'),
    (r'nacionality|nationality', 'full', PROHIBITED,
     'Nationality - national-origin proxy, prohibited basis (ECOA/Reg B).'),

    # --- proxy risk: not directly prohibited, recognised proxies -----------
    (r'education.*', 'full', PROXY_RISK,
     'Education - recognised proxy for race/national origin and age.'),
    # Geography patterns use explicit letter-boundary lookarounds in substring
    # mode rather than naive .*word.* - without them, 'NumberRealEstateLoansOrLines'
    # matches 'state' (realE-STATE) and anything containing 'capacity' matches
    # 'city' (capa-CITY). Both were observed as false positives on GMSC/PAK.
    (r'(?<![a-z])(zip|postcode)(?![a-z])|postal_?code', 'sub', PROXY_RISK,
     'Geography at postal-code level - recognised redlining proxy.'),
    (r'(?<![a-z])(borough|city|state|district|region|province|county)(?![a-z])',
     'sub', PROXY_RISK,
     'Geography - recognised proxy for race/national origin (redlining risk).'),
    (r'(?<![a-z])area_?code(?![a-z])', 'sub', PROXY_RISK,
     'Telephone area code - geographic proxy.'),
    (r'quant_dependants|num.*dependent.*|people_liable|numberofdependents|'
     r'nkid|n_?kids?|dep|num.*child.*',
     'full', PROXY_RISK,
     'Household composition - proxy for familial status / sex. Includes the common '
     'credit-scoring abbreviations NKID (number of children) and DEP (dependents).'),
    (r'housing|res|residential_?status|home_?owner.*', 'full', PROXY_RISK,
     'Housing/residential tenure - correlated with protected characteristics; treat with '
     'care. Includes the RES abbreviation used in several credit-scoring datasets.'),
]

# ---------------------------------------------------------------------------
# Availability rules. Ordered - first match wins. Anything unmatched defaults
# to origination, on the basis that the conservative assumption for an
# application scorecard is that a field IS available at decision time; where
# it is not, it must be flagged explicitly.
# ---------------------------------------------------------------------------
_AVAILABILITY_RULES = [
    (r'externalriskestimate|.*external.*score.*|.*bureau.*score.*|cibil.*|fico.*',
     'full', EXTERNAL_SCORE,
     'Output of another model used as an input - partially a score-recovery exercise.'),

    # Taiwan UCI: PAY_0 is repayment status in the month immediately before the
    # target month, so it is partially definitional of next-month default.
    (r'pay_0', 'full', NEAR_TARGET,
     'Repayment status in the month immediately preceding the target window - '
     'partially definitional of the target.'),

    (r'pay_[2-9]|pay_amt.*|bill_amt.*', 'full', BEHAVIOURAL,
     'Account performance history - observable only after account opening.'),
    (r'msincemostrecent.*|msinceoldest.*|maxdelq.*|numtrades.*|numsatisfactory.*|'
     r'percenttrades.*|netfraction.*|numrevolving.*|numinstall.*|numinq.*|'
     r'numbank2natl.*|averageminfile|numtotaltrades|percentinstall.*',
     'full', BEHAVIOURAL,
     'Credit-bureau behavioural aggregate - reflects post-origination conduct.'),
    (r'delinq|derog|clage|clno|ninq', 'full', BEHAVIOURAL,
     'Bureau delinquency / trade-line history - behavioural.'),
    (r'numberoftime.*|numberoftimes.*|revolvingutilization.*|numberofopen.*|'
     r'numberrealestate.*', 'full', BEHAVIOURAL,
     'Bureau behavioural aggregate (GMSC-style) - post-origination conduct.'),
]


def _match(name, pattern, mode):
    flags = re.IGNORECASE
    if mode == 'full':
        return re.fullmatch(pattern, name, flags) is not None
    return re.search(pattern, name, flags) is not None


def _classify_one(name, rules, default_tag, default_reason):
    for pattern, mode, tag, reason in rules:
        if _match(name, pattern, mode):
            return tag, reason
    return default_tag, default_reason


def classify_columns(df, target=None, eligibility_overrides=None, availability_overrides=None):
    """Per-column eligibility and availability tags. Never drops anything.

    eligibility_overrides / availability_overrides: {column: tag} dicts applied
    last, for dataset-specific determinations the name-based rules cannot make
    (a column whose name is uninformative, or a jurisdictional call).

    Returns a DataFrame indexed by column with eligibility / eligibility_reason
    / availability / availability_reason.
    """
    eligibility_overrides = eligibility_overrides or {}
    availability_overrides = availability_overrides or {}
    cols = [c for c in df.columns if c != target]
    rows = []
    for c in cols:
        elig, elig_why = _classify_one(
            c, _ELIGIBILITY_RULES, PERMISSIBLE,
            'No name-based match to a prohibited or proxy-risk pattern.')
        avail, avail_why = _classify_one(
            c, _AVAILABILITY_RULES, ORIGINATION,
            'Assumed observable at application/decision time (no behavioural pattern matched).')
        if c in eligibility_overrides:
            elig, elig_why = eligibility_overrides[c], 'Explicit dataset-specific override.'
        if c in availability_overrides:
            avail, avail_why = availability_overrides[c], 'Explicit dataset-specific override.'
        rows.append({'column': c, 'eligibility': elig, 'eligibility_reason': elig_why,
                     'availability': avail, 'availability_reason': avail_why})
    out = pd.DataFrame(rows).set_index('column')
    return out.loc[cols]


def ineligible_columns(tags, columns=None):
    """Columns tagged prohibited or proxy_risk, optionally restricted to `columns`."""
    if columns is None:
        sub = tags
    else:
        sub = tags.loc[[c for c in columns if c in tags.index]]
    return [c for c in sub.index if sub.loc[c, 'eligibility'] in INELIGIBLE_TAGS]


def flagged_name(column, tags):
    """'AGE [prohibited]' / 'EDUCATION [proxy_risk]' / 'DEBTINC' - for results tables.

    ASCII marker rather than a warning glyph: this string is printed to Windows
    consoles whose default codec is cp1252.
    """
    if column not in tags.index:
        return column
    marks = []
    if tags.loc[column, 'eligibility'] in INELIGIBLE_TAGS:
        marks.append(tags.loc[column, 'eligibility'])
    if tags.loc[column, 'availability'] in (NEAR_TARGET, EXTERNAL_SCORE):
        marks.append(tags.loc[column, 'availability'])
    return column + ' [' + ', '.join(marks) + ']' if marks else column


def warn_on_retained_ineligible(selected_columns, tags, context=''):
    """Emit one UserWarning per retained prohibited/proxy_risk column.

    MUST be called from the final-model build path and from report generation
    (METHODOLOGY.md v3 section 3.1). Returns the offending columns so callers
    can also record them in a model card.
    """
    offenders = ineligible_columns(tags, selected_columns)
    where = ' (' + context + ')' if context else ''
    for c in offenders:
        warnings.warn(
            'REGULATORY ELIGIBILITY' + where + ": retained column '" + str(c) +
            "' is tagged '" + str(tags.loc[c, 'eligibility']) + "'. " +
            str(tags.loc[c, 'eligibility_reason']) +
            ' Retained by project decision for benchmark comparability; not '
            'suitable for a live credit decision. See METHODOLOGY.md v3 section 3.1.',
            UserWarning, stacklevel=2)
    return offenders


def availability_warnings(selected_columns, tags, context=''):
    """Warn where a selected set mixes in near_target or external_score fields.

    These block nothing, but a headline metric computed on a feature set
    containing them must be reported as such (METHODOLOGY.md v3 s3.3).
    """
    sub = tags.loc[[c for c in selected_columns if c in tags.index]]
    flagged = {}
    for tag in (NEAR_TARGET, EXTERNAL_SCORE):
        flagged[tag] = [c for c in sub.index if sub.loc[c, 'availability'] == tag]
    where = ' (' + context + ')' if context else ''
    for tag, cols in flagged.items():
        if cols:
            warnings.warn(
                'FEATURE AVAILABILITY' + where + ': selected set contains ' + tag +
                ' column(s) ' + str(cols) + '. Report results with and without them; '
                'do not present this as an origination-time (application) model. '
                'See METHODOLOGY.md v3 section 3.3.',
                UserWarning, stacklevel=2)
    return flagged


DISCLOSURE_TEXT = (
    "**Regulatory eligibility disclosure.** This analysis retains features that are prohibited or\n"
    "proxy-prohibited inputs to consumer credit decisions in major jurisdictions (listed below). They are\n"
    "retained because these are public research benchmark datasets and their inclusion preserves\n"
    "comparability with the published literature on the same data. No model in this work is intended or\n"
    "suitable for deployment in a live credit decision. Retention is a methodological choice for\n"
    "comparability and is not an endorsement of such use. A fairness-constrained replication excluding\n"
    "these features is planned."
)


def disclosure_block(tags, selected_columns=None):
    """The mandatory section-10.3 disclosure block, with offending columns listed.

    Returns an empty string when no retained column is prohibited/proxy_risk, so
    it can be inserted unconditionally into a findings log.
    """
    offenders = ineligible_columns(tags, selected_columns)
    if not offenders:
        return ''
    lines = [DISCLOSURE_TEXT, '', 'Retained regulatory-ineligible features:', '',
             '| Column | Tag | Basis |', '|---|---|---|']
    for c in offenders:
        lines.append('| `' + str(c) + '` | ' + str(tags.loc[c, 'eligibility']) + ' | ' +
                     str(tags.loc[c, 'eligibility_reason']) + ' |')
    return '\n'.join(lines)


def governance_table_markdown(tags):
    """Full Stage-0 classification table as markdown, for the findings log."""
    lines = ['| Column | Eligibility | Availability | Basis |', '|---|---|---|---|']
    for c in tags.index:
        lines.append('| `' + str(c) + '` | ' + str(tags.loc[c, 'eligibility']) + ' | ' +
                     str(tags.loc[c, 'availability']) + ' | ' +
                     str(tags.loc[c, 'eligibility_reason']) + ' |')
    return '\n'.join(lines)


def summary(tags):
    """Counts per tag, for a quick console/report line."""
    return {
        'eligibility': tags['eligibility'].value_counts().to_dict(),
        'availability': tags['availability'].value_counts().to_dict(),
        'n_columns': len(tags),
    }
