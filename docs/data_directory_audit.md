# E1 data directory audit (read-only evidence, 2026-10-19)

Scope: `data/`, the three `r2-sanity-v1` manifests, `dataset_protocol.py`, `instance_loader.py`, directly relevant data entry points/docs, and the persisted E1/E1R and R3 split records. No instance was solved or regenerated for this audit. SHA-256 means raw file bytes; the separate semantic comparison parsed all six-line numeric tokens as binary64 values in order. Neither file name nor family label alone establishes instance identity.

## Current tree and origin

```text
data/
├── R2_T*.txt, R4_T*.txt, R8_T*.txt       61 root-level instance files
├── development/                         2 family directories, 0 files
├── held-out/                            2 family directories, 0 files
├── final/                               2 family directories, 0 files
└── r2_sanity/
    ├── development/ F_DEV_BALANCED, F_DEV_CLUSTERED   2 files
    ├── held-out/   F_HOLD_DEPOT_NEAR, F_HOLD_DISPERSED 2 files
    └── final/      F_FINAL_SCALE, F_FINAL_TRAVEL      2 files
```

| Directory | Evidenced purpose / origin | Creator and creation time |
|---|---|---|
| `data/development/` | Currently empty family placeholders; **not** the E1 input. Their family names match the R2 development design, but no checked script/manifest points to files there. | **UNKNOWN / UNKNOWN** |
| `data/held-out/` | Currently empty family placeholders; not the R2 held-out files. | **UNKNOWN / UNKNOWN** |
| `data/final/` | Currently empty family placeholders; not the R2 final files. | **UNKNOWN / UNKNOWN** |
| `data/r2_sanity/` | Six generated sanity instances, two per split. `build_sanity_dataset()` writes under this tree; the three manifests declare generator `mr-rcrp-deterministic-generator-v1`, file paths, seeds and hashes. `docs/dataset_protocol.md` says these are protocol-validation artifacts, not a paper-scale dataset. This establishes the documented generation mechanism, not the human/invocation that created the checked-in files. | Actual invoker/time **UNKNOWN / UNKNOWN** |
| `data/R*_T*_*.txt` | 61 root-level inputs in the loader's six-line format. `data/README.md` documents naming, and `configs/default.yaml` points at `data/R2_T10_0.txt`. No inspected generator or import provenance identifies their creator. | **UNKNOWN / UNKNOWN** |

Git provenance could not be corroborated in this environment because `git` is unavailable on `PATH` or the checked standard install paths. The existence of repository metadata alone does not establish who created a directory or when.

## File identity and split overlap

There are **67** instance text files: 61 at `data/` root and six under `data/r2_sanity/`. All **67 raw SHA-256 hashes are distinct**. Independently, all **67 ordered numeric-token sequences are distinct** under the six-line schema. Therefore no exact-byte copy or numerically identical instance was found among the scoped files; this does not claim broader optimization-equivalence under transformations not checked here.

Four names occur twice, each time with **different bytes and different numeric content**: `R2_T10_0.txt` (root vs sanity development), `R2_T20_0.txt` (root vs sanity development), `R4_T20_0.txt` (the two sanity held-out families), and `R6_T40_0.txt` (the two sanity final families). A basename-only join would incorrectly conflate them. All six manifest `file_hash` values match current on-disk SHA-256 values.

Across the R2 sanity manifests, development (2), held-out (2), and final (2) have no shared manifest instance ID, family ID, raw hash, or ordered numeric-token sequence. In particular, no development–held-out or development–final duplicate was found. These are the **sanity** splits only: `data/r2_sanity/held-out/` is the held-out location named by the R2 held-out manifest, whereas the top-level `data/held-out/` is empty. Neither is evidence of a fresh confirmatory-heldout dataset.

R3's `outputs/r3_diagnostics/raw/held-out_runs.json` and six held-out convergence records (two families × seeds 0–2) show the sanity held-out was used diagnostically. `docs/research_method_vNext.md` explicitly marks those six runs `diagnostic-heldout-consumed` and requires new unseen selection-validation and confirmatory-heldout splits. Reusing these R2 sanity held-out instances as confirmatory evidence would therefore contaminate that claim. No fresh confirmatory manifest was established by this scoped audit.

## E1 actual selection and loading

The E1/E1R invocation used `manifests/r2-sanity-v1_development.json`. It lists:

| Manifest instance ID | Actual path selected |
|---|---|
| `F_DEV_BALANCED_r0` | `data/r2_sanity/development/F_DEV_BALANCED/R2_T10_0.txt` |
| `F_DEV_CLUSTERED_r0` | `data/r2_sanity/development/F_DEV_CLUSTERED/R2_T20_0.txt` |

`load_development_instance_paths()` calls `load_manifest(..., expected_split="development")`, checks each entry's split, confines its resolved path under the dataset root, and checks file existence. `_run_branch()` passes only those returned paths to `build_repair_benchmark_cases()`, which calls `load_instance()` on each. E1R's persisted `metadata.json` records those two absolute paths, development count 2, seeds 0/1, `heldout_accessed=false`, `final_test_accessed=false`; F1/F2 trial files each contain eight records for the two selected instance stems across two generations and two seeds. No held-out/final path appears in this recorded E1 input chain. The metadata flags are program-written assertions, not an operating-system file-access trace; an independent runtime trace was **not** recorded.

Important distinction: E1's path-selection helper **does not compare file bytes to the manifest `file_hash` before loading**. The separate `load_manifest_instances()` API in `dataset_protocol.py` does perform SHA-256 verification, but E1 does not call it. Current bytes match the manifest (checked above); future silent replacement at an approved development path would not be caught by E1's current loader. This is a provenance risk, not evidence that E1 used the wrong files.

There are other non-E1 direct-input entry points: `configs/default.yaml` names the root `data/R2_T10_0.txt`; `main.py` loads that configured path; `benchmark_runner.py` uses a nonrecursive `data_dir.glob("R*_T*_*.txt")`, so `data_dir=data` reads root files directly rather than the sanity manifests. Thus “all project access is manifest-driven” applies to the R2 protocol path, **not** to every existing entry point. No evidence in the inspected E1 chain shows it bypassed its development manifest.

## Paper-experiment risks and unknowns

1. **High:** the consumed R3 diagnostic held-out cannot serve as fresh confirmatory held-out; new unseen split/manifest provenance is needed before such a claim.
2. **Moderate:** E1 selects via manifest but omits manifest-hash enforcement at load time. Record or verify bytes per trial before future confirmatory work.
3. **Moderate:** same basenames refer to different instances; joins must use manifest identity plus path/hash, not basename alone. E1 trial records use `instance_id` equal to the filename stem, so their identity must be interpreted with the E1 metadata/manifest.
4. **Scope:** the six R2 files are a sanity set, and the 61 root files have **UNKNOWN** origin/split provenance. Neither is, by itself, a frozen paper-scale dataset.
5. **Manual confirmation needed:** who/when created the empty top-level split folders and root files; exact generator invocation/date for the R2 sanity artifacts; whether an external dataset or Git history documents the 61 root files. No guess is made here.

No files or manifests were moved, regenerated, or renamed during this audit. No held-out/final solver or E2 run was performed.
