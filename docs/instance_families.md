# R2 Sanity Family Matrix

| Family | Split | R | T | Load | Geometry | Spatial | Travel/coverage | H/V | Replicates | Purpose |
|---|---:|---:|---:|---:|---|---|---|---|---:|---|
| F_DEV_BALANCED | development | 2 | 10 | medium | square-ish | uniform | balanced | mixed-HV | 1 | parser and balanced baseline input |
| F_DEV_CLUSTERED | development | 2 | 20 | high | horizontal-elongated | clustered | coverage-dominated | high-HV-sensitivity | 1 | clustered and coverage pressure |
| F_HOLD_DISPERSED | held-out | 4 | 20 | medium | vertical-elongated | dispersed | travel-dominated | mixed-HV | 1 | spatial/travel generalization |
| F_HOLD_DEPOT_NEAR | held-out | 4 | 20 | medium | mixed-aspect | depot-near | balanced | low-HV-sensitivity | 1 | depot-distance and low H/V gap |
| F_FINAL_SCALE | final | 6 | 40 | high | mixed-aspect | multi-cluster | coverage-dominated | high-HV-sensitivity | 1 | unseen scale/distribution lockbox |
| F_FINAL_TRAVEL | final | 6 | 40 | high | horizontal-elongated | dispersed | travel-dominated | mixed-HV | 1 | travel-heavy lockbox |

The matrix is a compact sanity design, not a paper-scale benchmark. Family labels and placement rules are intrinsic and frozen before solver execution. Replicate identity is separate from solver seed and any future LLM evolution seed.
