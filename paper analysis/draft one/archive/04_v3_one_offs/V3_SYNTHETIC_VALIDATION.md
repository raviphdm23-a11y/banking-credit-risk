# Synthetic ground-truth validation (METHODOLOGY v3 s7.4)

Generator: correlated informative features, an exact duplicate, a U-shaped feature, an
interaction-only feature with ~zero marginal signal, a proxy of an informative feature, and pure noise.
Power = fraction of truly-predictive features confirmed. FDR = fraction of confirmed that are pure noise.

| n | event rate | rho | T | power | FDR | confirmed | TP | FP | dup collapsed | U-shape flagged | interaction kept |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 2000 | 0.15 | 0.0 | 150 | 1.00 | 0.00 | 8 | 8 | 0 | True | True | True |
| 2000 | 0.15 | 0.5 | 150 | 1.00 | 0.00 | 8 | 8 | 0 | True | True | True |
| 2000 | 0.15 | 0.9 | 150 | 1.00 | 0.00 | 8 | 8 | 0 | True | True | True |
| 10000 | 0.15 | 0.0 | 150 | 1.00 | 0.00 | 8 | 8 | 0 | True | True | True |
| 10000 | 0.15 | 0.5 | 150 | 1.00 | 0.00 | 8 | 8 | 0 | True | True | True |
| 10000 | 0.15 | 0.9 | 150 | 1.00 | 0.00 | 8 | 8 | 0 | True | True | True |
