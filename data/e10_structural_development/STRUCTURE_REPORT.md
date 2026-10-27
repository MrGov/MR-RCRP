# E10 structural development dataset

21 instances, seven paired scenarios x three independent replicate seeds. R=4, T=40, depot=(0,0); every robot shares the instance parameters. Six-line TXT files round-trip through the production loader. No optimization score enters generation or labels.

| Scenario | Aspect max/min mean | Relative H/V gap | Preferred turning share | Mean H/V sweeps | Mean min processing | Workload CV | Pairwise Manhattan | Travel/work proxy |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| BASE | 1.000 | 0.000 | 0.213 | 4.98/4.98 | 96.15 | 0.295 | 380.26 | 3.973 |
| HV-GEOM | 9.000 | 0.335 | 0.054 | 8.50/8.42 | 94.55 | 0.154 | 380.26 | 4.029 |
| SPATIAL | 1.000 | 0.000 | 0.213 | 4.98/4.98 | 96.15 | 0.295 | 572.20 | 5.985 |
| BOTTLENECK | 1.000 | 0.000 | 0.266 | 4.47/4.47 | 95.80 | 1.629 | 380.26 | 3.988 |
| TURN-HIGH | 1.000 | 0.000 | 0.351 | 4.98/4.98 | 116.03 | 0.279 | 380.26 | 3.291 |
| TRAVEL-HIGH | 1.000 | 0.000 | 0.213 | 4.98/4.98 | 96.15 | 0.295 | 380.26 | 7.947 |
| SWEEP-NARROW | 1.000 | 0.000 | 0.228 | 7.62/7.62 | 149.97 | 0.284 | 380.26 | 2.547 |

## Design and actual controls

- BASE: independent uniformly sampled integer centers conditioned on non-overlapping shared exclusion envelopes; square sides sampled from 12/15/18. Square geometry is the deliberately neutral H/V reference. Placement is not an unconstrained spatial Poisson process.
- HV-GEOM: alternating 3x and 1/3x dimensions (aspect 9), preserves each area and center exactly. Perimeter, corner locations and discrete processing workloads change; it is not an isolated H/V-state intervention.
- SPATIAL: doubles center x only, retaining every dimension and all physical parameters. The layout is stretched; coordinate spans, separation and depot distances co-vary. It does not isolate clustering or hold depot travel fixed.
- BOTTLENECK: four enlarged square tasks and 36 smaller ones; scalar normalization targets BASE sum min(H,V) processing within 2%. Centers stay fixed; total area/perimeter and task dimensions are not fixed. Intrinsic workload imbalance does not prove any solver bottleneck.
- TURN-HIGH/TRAVEL-HIGH/SWEEP-NARROW: exact BASE task list, only turning_time=10 / travel_speed=0.5 / sweep_width=2 changes respectively. Other parameters remain 3/1/1/5.

All variants use shared exclusion envelopes during BASE placement so changed geometry fits without relocating centers. Non-overlap is strict in rectangle interiors; coordinates stay nonnegative. SPATIAL extends the x domain, intentionally.

## Definitions

H sweeps=ceil(height/sweep_width), V sweeps=ceil(width/sweep_width). Processing=passes*scan_length/sweep_speed+(passes-1)*turning_time. Relative H/V gap=abs(pH-pV)/max(pH,pV), matching the existing extractor. Preferred turning share uses the mode of minimum isolated processing; H wins exact ties. Workload CV=population std(p_min)/mean(p_min). Travel/work proxy=mean centroid pair Manhattan / travel_speed / mean(p_min); depot proxy=2*mean depot Manhattan / travel_speed / mean(p_min). These are intrinsic pressure proxies, not Route-DP route costs. Sweep parity fractions record potential exit-state changes, not observed optimized state transitions.

Every numerical feature has mean/min/max across three replicates in structure_summary.csv. structure_checks.json records per-replicate structural tests. No algorithm outcomes are used for those tests.

## Seeds and pairing

| Replicate | Shared geometry seed | BASE paired instances |
|---|---:|---|
| 0 | 2187802853561209829 | all seven scenarios, replicate 0 |
| 1 | 4544452884924016370 | all seven scenarios, replicate 1 |
| 2 | 15822737991118767124 | all seven scenarios, replicate 2 |

| Replicate | HV area vs BASE | HV min-work change | BOTTLENECK area change | BOTTLENECK min-work change |
|---|---:|---:|---:|---:|
| 0 | +0.000% | -2.011% | -4.702% | -0.959% |
| 1 | +0.000% | -4.403% | -2.190% | -0.126% |
| 2 | +0.000% | +1.848% | -6.117% | -0.000% |

## Use and reproduce

All entries are development. These do not replace the 60 original main instances or r2_sanity. Existing held-out/final/lockbox data were not inputs. For future confirmation freeze this design first and use a new dataset version and independent seeds. Do not treat the three paired scenarios within one replicate as independent draws.

```powershell
$env:PYTHONPATH='src'
& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.dataset_protocol --structural-output data/e10_structural_development
```

Existing nonempty output is refused. To reproduce bytes use a fresh --structural-output directory, then compare TXT hashes with manifest.json. The per-scenario subdirectories permit legacy R4_T40_0/1/2 names without changing the loader. Instance IDs must include scenario or relative path to avoid basename collisions.

Validation and a few optional short B1 runs are separate from generation; no LLM calls or method comparison is part of this dataset. These physical settings are development controls without engineering calibration.
