# R3 Held-Out Hypotheses

Frozen on 2026-09-29 after Track A and Track B development diagnostics and before any held-out diagnostic execution. The R2 final manifest and files remain prohibited.

## H1: H/V sensitivity and inner-DP response

Across controlled held-out families, higher `relative_hv_gap_mean` is expected to correspond to higher mean accepted-move `state_changed_fraction` and `dp_cascade_ratio`. Both metrics are averaged over the frozen seeds before comparing families.

## H2: Assignment contribution

For each held-out family, positive accepted assignment-classified repair gain is expected to exceed positive accepted ordering-only repair gain. Local-search gain is reported separately and is not credited to repair.

## H3: Structural operator ranking

The top built-in destroy operator by positive accepted objective gain per use is expected to differ for at least one controlled travel-dominated versus non-travel-dominated family comparison. This is a limited complementarity check, not a universal operator-ranking claim.

The hypotheses, metrics, 100-iteration budget, and held-out seeds `0,1,2` are frozen before opening held-out inputs. Failed hypotheses remain reported and do not trigger method or threshold changes.
