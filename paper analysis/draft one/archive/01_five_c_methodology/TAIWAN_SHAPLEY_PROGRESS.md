# Taiwan Credit Card — Shapley Run Progress Tracker

**PLAN REVISED 2026-10-09**: switched from exact Shapley on all 15 Step 1-4 survivors to correlation-based
pruning first (per `METHODOLOGY.md` Step 2a), then exact Shapley on the pruned pool — after Phases 1-2 of
the original plan had already run (16,384 subsets computed). Correlation pruning (Spearman >0.7, keep
higher-IV member) dropped `PAY_3`/`PAY_4`/`PAY_5` as redundant with stronger neighbors, shrinking the pool
from 15 to 12 columns: `AGE, EDUCATION, LIMIT_BAL, PAY_0, PAY_2, PAY_6, PAY_AMT1-6`.

**Reuse result:** every already-computed subset from the original 15-column checkpoint that happens to use
only the 12 survivors is directly reusable (a subset's value doesn't depend on the larger pool it came
from). Of the 4,095 subsets needed for the pruned pool (2¹²−1), **3,301 were already done — only 794 new
subsets needed** (~3,970 fits, single short background run, no further phasing needed).

| Step | Status |
|---|---|
| Original Phase 1 (sizes 1-6, 9,948 subsets) | Done (job `bts3m1qpr`) |
| Original Phase 2 (size 7, 6,435 subsets) | Done (job `bgdldegny`) — total 16,384 computed under old plan |
| Correlation pruning (15→12 columns) | Done |
| Pruned-pool run (794 new subsets, reusing 3,301) | **Running** (job `brc1zgrgk`) |

Going forward (per the broader methodology discussion, 2026-10-09): any dataset whose pool is too large for
exact Shapley even after correlation pruning should switch to sampled/approximate Shapley (SAGE-style
permutation sampling), not keep scaling up exact enumeration. Taiwan and HELOC are both still within reach
of exact computation after pruning, so this run finishes exactly, not approximately.

Update this table (status + total count) after each check-in.
