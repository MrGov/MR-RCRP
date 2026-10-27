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

## E10 paired structural development families

Every family below has R=4, T=40, depot=(0,0), three repeats, homogeneous robots
and split `development`. Baseline parameters are width/sweep-speed/travel-speed/
turning-time = 3/1/1/5. They are initial model controls, not engineering calibration.

| Scenario | Geometry/layout rule | Exact controls and accompanying changes |
|---|---|---|
| BASE | Square side 12/15/18; uniform center proposals with shared-envelope rejection | Neutral H/V processing reference; placement conditioned on non-overlap |
| HV-GEOM | Width/height multiplied by 3 and 1/3, alternating orientation | Exact per-task area and centers; perimeter, corners and processing work change |
| SPATIAL | Double every center x | Exact dimensions/physical parameters; separation and depot distance both change |
| BOTTLENECK | Four heavy squares, 36 smaller squares | Exact centers; target sum min(H,V) work within 2% of BASE; area changes |
| TURN-HIGH | BASE tasks, turning_time=10 | Only this physical parameter changes |
| TRAVEL-HIGH | BASE tasks, travel_speed=0.5 | Only this physical parameter changes |
| SWEEP-NARROW | BASE tasks, sweep_width=2 | Only this physical parameter changes |

Seeds are derived from `stable_generation_seed("e10-structural-development-v1",
"E10_BASE", replicate)` and shared across seven scenarios within a repeat.
Repeated pairs are not independent draws. BASE centers reserve exclusion envelopes
for the largest same-index geometry, allowing every variant without relocation.
SPATIAL intentionally expands the x domain; all rectangles have nonnegative bounds
and do not overlap. The generated report records actual differences rather than
claiming single-factor isolation for the three geometry/layout interventions.
