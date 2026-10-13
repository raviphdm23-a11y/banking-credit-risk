# Model card - HMEQ

**Intended use:** Methodological research only.
**NOT for use in:** any live or production credit decision.

## Features

| Column | Eligibility | Availability |
|---|---|---|
| `DEBTINC` | permissible | origination |
| `DELINQ` | permissible | behavioural |
| `DEROG` | permissible | behavioural |
| `CLAGE` | permissible | behavioural |
| `MORTDUE` | permissible | origination |
| `VALUE` | permissible | origination |
| `NINQ` | permissible | behavioural |
| `JOB` | permissible | origination |
| `LOAN` | permissible | origination |
| `YOJ` | permissible | origination |
| `CLNO` | permissible | behavioural |

## Regulatory-ineligible features retained

None.

## Selection

Tolerance met: True. Rule: smallest k with DeLong p >= 0.05 (not distinguishable from the full-candidate model) and relative Gini loss <= 5.0%

## Calibration

Method: isotonic. Brier 0.0710 -> 0.0687. ECE 0.0235 -> 0.0157.

## Known limitations

- Accept-only sample: feature strength is attenuated by the original approval policy (METHODOLOGY v3 s3.2). No reject inference performed.
- No out-of-time validation; all cross-validation is i.i.d. random.
- Importance is conditional on the value-function learner used.
