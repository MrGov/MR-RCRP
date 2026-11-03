# Offline Operator Evolution

## Current method: structural population and deployment selection (2026-11-02)

This section supersedes the repair-first scope below for the current batch. The
research hypothesis is that exact entry/exit chains, joint removal costs and
bottleneck migration evidence help evolve useful destruction/reconstruction
logic, and that selecting combinations improves complete solves. Neither claim
is assumed true.

An individual is a source-hashed Python `search_step(features, rng)` program with
two phases: destroy returns an actual task subset; repair selects actual
task/robot/slot extensions of one or more current reconstruction branches. The
host prices each new branch exactly, supplies state-chain information and exact
insertion alternatives, enforces task integrity and caps branch width, removal
size, pricing work and subprocess time. Candidates can change removal extent,
contiguity, joint task reassignment, insertion order, slot selection and branch
survival. They cannot access the solver, implement a replacement objective or
change acceptance/initialization/LS. This is a small batched action interface,
not the old pair-ranking or call/skip interface.

Three native manual destroy/repair pair seeds and a deterministic state-chain
reference start the active population. New sources come from structural mutation,
two-parent recombination, composition-gap generation and occasional de novo
design. The immutable archive contains all sources/failures; the active population
has capacity 10 (not a quota); the deployment is a separate explicit list of
allowed destroy-repair pairs. Different phases of one source can be paired with
manual or other generated phases. Pair selection uses initial exploration and
smoothed 8/3/1 pair reward; no causal credit is assigned to an individual phase.

Correctness/cost checks reject invalid behavior, then fixed-state fingerprints
detect exact behavioral duplicates and provide feedback. A local gain is NOT an
admission requirement. Every distinct feasible candidate receives full timed
ALNS evaluation. Survival uses normalized per-instance complete-solve results,
an elite, instance specialists within a quality floor and bounded population
replacement. Deployment checks limited additions, replacements and deletions,
including at least one two-generated-member combination. It is not top-k ranking.

The batch has at most four rounds, four new candidates per round, 32 actual
requests including at most one engineering repair per candidate, and no provider
retries. Two rounds without either new effective behavior or combination progress
allow stopping. Manual-only selection is allowed. Single-member and multi-member
comparisons use the same archive. The deterministic reference separates the new
host search mechanism from LLM assistance; one batch cannot identify a causal
effect of structural feedback without a matched feedback ablation.

Data/configuration are frozen before any candidate result: six development
instances, two seeds, task-scaled wall budgets, common spatial-sort initializer,
enhanced SA, exact priced local search. Setup and boundary/cleanup costs are
recorded and charged against the end-to-end allowance, with atomic iteration
overshoot reported. Two development instances are reserved until freeze. Their
E14 descriptive-use history is explicitly recorded; they are held out from THIS
batch only, not independent validation. No final/test/lockbox input is opened.

### Direct original-paper check

- **G-LNS, arXiv:2602.08253v1**, local `Com-alg/G-LNS.pdf`, pp. 3-5,
  sections 3.2-3.5: manual/LLM seeds, separate destroy/repair populations,
  multi-episode ALNS evaluation, accumulated operator fitness and pair synergy,
  pruning, logical mutation, homogeneous and synergistic joint crossover. Thus
  joint evolution and complementary destroy/repair logic are already prior art.
- **Full-component ALNS evolution, arXiv:2603.06996v2 (19 May 2026)**,
  local `Com-alg/ALNS 全组件演化.pdf`, pp. 3-4 and 9-12: seven components,
  isolated evaluation, quality/time/usage score, MAP-Elites, cascade screening,
  parallel/serial evolution, and explicitly observed composition incompatibility.
  We hold common controls fixed and select actual deployed combinations using
  complete timed solves; this distinction is a study design, not novelty proof.
- **Wang et al., evALNS, DOI:10.1007/s42524-026-5124-4**, local
  `Com-alg/evALNS.pdf`, sections 3.1-3.3: expert and LLM destroy populations,
  mutation/crossover and elite exchange, with functional natural language
  embeddings. Expert/generated mixing and multi-lineage evolution are prior art.

The potential problem-specific increment is exposing the coupled coverage-state
chain and exact joint reconstruction outcomes to structural evolution, then
testing budgeted combination utility for MR-RCRP. It requires performance and
matched mechanism evidence; multiple programs, passing tests and real calls do
not establish it.

### Implementation and verification sequence

1. Extend existing hash/AST/subprocess execution to the batched structural action
   contract; test illegal actions, exact branches, timeouts and cleanup.
2. Add the small host reconstruction kernel and explicit pair-selector subclass;
   retain production model, DP, pricing, acceptance and local search.
3. Add one bounded evolution runner/config: lock data, baseline/reference,
   generate/evaluate/select/feedback, population survival, composition edits.
4. Run the authorized real batch, freeze sources/pairs, execute reserved checks
   once, report paired quality/stability, all failures and separate offline cost.
5. Update current status, positioning and runnable entry points from actual results.

### Historical development batch (run_001, 2026-11-03)

The records below are immutable results under the first budget and measurement
semantics. Use the corrected-kernel full-solve review below for current method
selection and performance claims.

The frozen instance rule produced six development instances (20/40/60/80/100
tasks, 2/4/8 robots, six structures), each with seeds 23/29, plus two
batch-held instances checked once after freeze. Both reserve IDs were already
used descriptively in E14; this is not untouched validation.

The batch made 18 charged request attempts over four rounds. Ten candidate source
records resulted from structural mutation, two-parent recombination, gap-directed
generation and de-novo generation, alongside provider/parse failures, one
interrupted attempt and one engineering repair. Eight distinct feasible LLM
behaviors were evaluated before the corrected capped rerun; exact behavioral
duplicates were rejected. Population capacity was 10, with elites, instance
specialists and one observed replacement. Attempts reporting usage totalled
201,578 tokens (173,098 prompt, 28,480 completion); some failed/interrupted
requests have unknown usage. Provider billing is unavailable. Known request
latency totals 358 seconds. No new request was made for the host correction.

| Complete-solve group | Mean improvement vs manual | Paired rows better / worse |
|---|---:|---:|
| Manual ALNS | 0% | reference |
| Deterministic state-chain reference + three manual pairs | 2.66% | 10 / 2 |
| Best single LLM member + same manual pairs (`r4_c2`) | 2.61% | 8 / 4 |
| Best two-LLM-member set + two manual pairs (`r4_replace`) | 2.14% | 7 / 5 |
| Remove `r4_c2` from that two-member set | 0.60% | 3 / 9 |
| Capped recheck of `r1_c3` | -2.46% | 0 / 12 |

The selected development freeze was the deterministic reference plus all three
manual pairs. Its largest gains occurred on BOTTLENECK T60 (+8.56%) and
SWEEP-NARROW T100 (+5.59%). The best single LLM member was slightly behind this
reference, and the two-generated-member replacement set was weaker. Removing
`r4_c2` left the companion set largely ineffective.

The final deployment proposal thus contains three manually designed pairs plus
the deterministic reference pair. It uses exact entry/exit chains, joint
contiguous-window removal prices and at most three exact-priced reconstruction
branches. Pair roulette gives each deployed pair one first-use probe, then uses
smoothed 8/3/1 reward with 10% exploration. Reward stays at pair level; it is
not assigned to individual phases.

At the post-freeze check, all four rows (two reserved instances x two seeds)
favored manual ALNS. The reference combination lost by a mean 10.36%; the best
single LLM combination lost 12.76%; the best two-LLM-member composition lost
10.67%. These IDs have historical E14 descriptive use, so this is a small
development transfer check, not independent validation. The recommended
deployment remains manual ALNS; no generated member or structural reference is
promoted after the transfer result.

The deterministic structural mechanism accounts for its development gain over
manual ALNS in this sample. LLM evolution produced distinct behavior and one
development member close to the reference, but did not outperform it, improve
the multi-member composition, or pass the post-freeze check. This run cannot
attribute the deterministic mechanism's gain to LLM evolution; a matched
feedback/representation ablation is absent. No superiority or novelty claim is
established. The structural-feedback hypothesis remains unconfirmed.

Integrity review found that repair branching could exceed the declared width
exponentially. The host now caps live branches at width three and records the
maximum. The pre-fix 63,478-second `r1_c3` result is preserved as
`outputs/structural_population/run_001/development/r1_c3_invalid_unbounded.json`
and excluded from selection summaries. The same member was rerun across all 12
development rows under the branch cap; its mean was 2.46% worse than manual and
no run exceeded 12.69 seconds end to end.

**Next priority:** improve the deterministic state-chain search and branch
pruning/anytime policy without another LLM batch. Then freeze a new structural
split and predeclare a matched LLM-versus-reference mechanism comparison. The
current bottleneck is transfer and combination quality, not candidate count.

Replay the frozen development deployment without model calls:

```powershell
$env:PYTHONPATH='src'
python -m mrta_rect_coverage.experiments.structural_deploy --freeze outputs/structural_population/run_001/freeze.json --instance development/BOTTLENECK/R4_T60_0 --seed 23 --output outputs/structural_population/run_001/replay.json
```

### Corrected shared-budget review (review_002, 2026-11-03)

`outputs/structural_population/review_002/` freezes the candidate bytes and the
corrected implementation hashes. It makes **zero LLM requests** and reuses the
existing model, Route-DP, exact pricer, feasibility checks, initializer,
acceptance and local search. One wall-clock deadline and the common logical
price cap cover destroy feature construction, exact pricing, strategy execution,
reconstruction and completion. If a strategy timeout reaches that deadline,
the incomplete ALNS iteration is aborted, the last legal complete solution is
retained, and the attempt receives no acceptance/reward or pair credit. The
phase timers are disjoint; reconstruction excludes feature construction,
pricing and policy time. Frozen-source identity and two targeted deadline tests
cover these boundaries.

The six development cells (20-100 tasks, 2/4/8 robots) each use seeds 23/29
and predeclared 3/5/7/10/12-second end-to-end budgets. A further two previously
viewed E14 instances are reported only as development regressions. Their use
history is explicit; none of these rows is independent validation. A fixed
manual-pair-only `PairPortfolioSolver` separates the restriction to specified
pairs and pair-level credit from the original ALNS's independent destroy and
repair selection.

| Complete-solve condition | Mean vs original manual | Better / worse / tie | Mean vs manual-pair control | Incomplete iterations |
|---|---:|---:|---:|---:|
| Original manual ALNS | 0.00% | 0 / 0 / 12 | - | 0 |
| Fixed manual pairs only | -2.93% | 3 / 9 / 0 | 0.00% | 7 |
| Deterministic state-chain reference + manual pairs | +0.77% | 7 / 5 / 0 | +3.40% | 10 |
| Best single generated pair (`r4_c2`) + three manual pairs | +1.67% | 8 / 2 / 2 | +4.25% | 9 |
| Original multi-member replacement (`r4_c2`, `r2_c2`) | +1.64% | 8 / 4 / 0 | +4.18% | 12 |
| Same multi set without `r2_c2` | +1.98% | 8 / 4 / 0 | +4.52% | 10 |
| Same multi set without `r4_c2` | -2.32% | 2 / 10 / 0 | +0.44% | 11 |
| `r2_c2` added to all manual pairs | -3.16% | 5 / 7 / 0 | -0.28% | 10 |

The row-level percentages below are paired differences from original manual
ALNS, averaged only across the two listed seeds per instance in the summary
table. Exact makespans, both seeds, timing, operator calls, phase costs,
feasibility, and complete iteration histories are in `analysis.json` and each
condition's JSON file.

| Instance / seed | Manual pairs | Reference | `r4_c2` single | `r4_c2` + `r2_c2` | Shrunk: `r4_c2`, two manual pairs |
|---|---:|---:|---:|---:|---:|
| BASE / 23 | +0.30% | +0.56% | +0.26% | +1.30% | -0.26% |
| BASE / 29 | -0.61% | +0.22% | 0.00% | -2.73% | +0.26% |
| HV-GEOM / 23 | +2.33% | +3.37% | +3.37% | +2.87% | +2.87% |
| HV-GEOM / 29 | -0.04% | -0.34% | 0.00% | -1.42% | -0.17% |
| SPATIAL / 23 | +0.58% | -1.60% | +1.33% | -0.19% | +0.29% |
| SPATIAL / 29 | -1.88% | +1.27% | -0.74% | +0.03% | +1.08% |
| BOTTLENECK / 23 | -12.28% | +5.35% | +1.15% | +6.66% | +3.05% |
| BOTTLENECK / 29 | -5.87% | -0.32% | +3.99% | +7.05% | +4.17% |
| TRAVEL-HIGH / 23 | -1.53% | +0.40% | +0.40% | +0.40% | -0.04% |
| TRAVEL-HIGH / 29 | -2.00% | -0.26% | -1.41% | -1.38% | -0.06% |
| SWEEP-NARROW / 23 | -1.14% | +3.29% | +6.59% | +5.88% | +5.90% |
| SWEEP-NARROW / 29 | -12.99% | -2.66% | +5.08% | +1.14% | +6.68% |

The generated `r4_c2` condition beat the deterministic reference on five rows,
lost five and tied two; the 0.86% mean paired difference is not stable enough to
attribute a clear LLM increment. The deterministic reference itself beat the
manual-pair control on 10/12 rows. The single member and the original two-member
set have nearly identical means, but the multi set has more losses and more
budget-aborted iterations. In the two bounded removals, dropping `r2_c2` helped
while dropping `r4_c2` hurt. `r2_c2` alone with three manual pairs regressed.
The current development candidate is therefore the smaller three-pair
composition (`r4_c2` plus random/greedy and bottleneck/regret manual pairs),
not the two-generated-member set. This is a development choice, not a validated
production promotion.

| Previously viewed regression condition | Mean vs original manual | Better / worse |
|---|---:|---:|
| Fixed manual pairs only | -0.84% | 0 / 4 |
| Deterministic reference + manual pairs | +4.78% | 3 / 1 |
| `r4_c2` single + manual pairs | +9.84% | 4 / 0 |
| Original multi-member replacement | +7.13% | 3 / 1 |
| Shrunk `r4_c2` three-pair composition | +10.23% | 4 / 0 |

These four rows are the two E14-seen instances x two seeds. They diagnose no
current transfer regression, but cannot establish transfer or generalization.

| Development structural cost over 12 solves | Feature construction (s) | Exact pricing (s) | Strategy boundary (s) | Reconstruction (s) | Completion (s) | Budget stops / errors |
|---|---:|---:|---:|---:|---:|---:|
| Native deterministic reference | 9.17 | 34.36 | 1.53 | 1.27 | 0.00 | 10 / 0 |
| Isolated generated `r4_c2` single | 6.09 | 15.83 | 32.92 | 1.18 | 0.00 | 9 / 0 |
| Original two-generated-member set | 5.93 | 22.44 | 36.31 | 1.13 | 0.00 | 12 / 0 |
| Shrunk `r4_c2` three-pair set | 5.93 | 19.05 | 33.40 | 1.16 | 0.00 | 10 / 0 |

All 12 online budgets sum to 80 seconds per development condition. Generated
strategy calls alone consume about 33 seconds for `r4_c2`; this includes
feature/RNG copies and the checked persistent-process boundary, and is charged
to the same solve allowance. On the representative BASE/R2/T20 seed 23 check,
native and isolated reference decisions matched on fixed destroy and repair
features; the complete solve returned makespan 2299 in both modes. Under the
same three-second allowance, native execution completed about 438 iterations
with 0.027 seconds in the strategy phase; isolated execution completed 114
iterations with about 1.05 seconds there and one budget-aborted attempt. This
attributes the throughput gap to the execution boundary on this check, without
claiming an artificial cost-adjusted win for the native reference.

The corrected evaluation found one additional driver of the earlier record:
the abnormal pre-fix `r1_c3` result flowed directly into request 8's revision
prompt, was selected as `r2_c3`'s parent, and its descendants entered later
population and composition comparisons. The feedback/parent/survival history
is therefore contaminated, and cannot be described as evolution conducted
under the corrected kernel. The final `r4_c2` single and multi lineages and the
frozen deployment do not contain `r1_c3`; these current outcomes were rerun
under the corrected kernel. The locally fingerprint-identical `r3_c3` has
different source bytes from `r2_c3`; both received one complete evaluation, so
the fingerprint is treated only as suspected local duplication.

No new LLM generation should begin yet. The sole next priority is to reduce and
measure checked-executor input/call overhead while preserving candidate actions,
then compare the frozen best generated composition with the native structural
reference under the same end-to-end budget. Continue evolution only if that
matched comparison shows a repeatable, practically useful candidate increment
on a newly predeclared development sample; do not select by member count or one
aggregate mean. The corrected review ran 17 development conditions and six
regression conditions, used zero model requests, and reports about 1,614 seconds
of total complete-solve evaluation wall time. The early failed pair-shape
attempts and the single pre-fix strategy-timeout row are preserved in separate
files and excluded from final quality summaries.

The sections below describe the older subsystem and remain compatibility notes.

## Why repair-first
Repair operators directly decide how removed tasks are reinserted and therefore dominate final makespan quality in this MRTA setting. We evaluate repair operators with strict fairness (same partial solutions, same seeds, same benchmark set).

## Why destroy is lightweight
Destroy quality matters, but in early-stage evolution its effect is harder to isolate. This framework therefore uses full repair evolution and a lighter destroy smoke benchmark with fixed built-in repair.

## Closed-loop workflow
1. Provider generates candidate repair (and optional destroy) operators.
2. Candidate loader validates import, signature, and smoke behavior.
3. Benchmark harness evaluates candidates on small instances.
4. Metrics are aggregated (improvement, success, runtime, timeout/error/invalid rates).
5. Feedback is built and sent into next-round prompt.
6. After N rounds, best operators are written to `best_operators.json`.
7. Best operators can be frozen into `src/mrta_rect_coverage/heuristics/generated_best/`.

## Providers
- `mock`: deterministic templates, no external API.
- `file`: writes prompts to files and reads manually produced candidates.
- `langchain_openai_compatible`: calls a real LLM via LangChain ChatOpenAI (supports any OpenAI-compatible endpoint).

## Run mock mode
```bash
python -m src.mrta_rect_coverage.experiments.operator_evolution_runner --provider mock --rounds 2 --freeze-best
```

## Run file mode
```bash
python -m src.mrta_rect_coverage.experiments.operator_evolution_runner --provider file --rounds 2
```
Then place candidate `.py` files under:
- `outputs/operator_evolution/file_provider_exchange/round_000/repair/`
- `outputs/operator_evolution/file_provider_exchange/round_000/destroy/`

## Run LangChain LLM mode

> **Safety warning:** generated code runs only inside a timeout-only subprocess,
> not a capability sandbox. Real-provider candidate execution requires explicit
> current-runtime risk acknowledgement. Do not treat artifact metadata as an
> execution authorization.

### 1. Install optional dependencies
```bash
pip install mrta-rect-coverage[llm]
# or manually:
pip install python-dotenv langchain-openai
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your API key and endpoint
```

Key environment variables:
| Variable | Description | Default |
|----------|-------------|---------|
| `OPERATOR_LLM_PROVIDER` | Provider name | `mock` |
| `OPERATOR_LLM_API_KEY` | API key (required for LangChain) | — |
| `OPERATOR_LLM_BASE_URL` | OpenAI-compatible base URL | (OpenAI default) |
| `OPERATOR_LLM_MODEL` | Model name | `gpt-4o` |
| `OPERATOR_LLM_TEMPERATURE` | Sampling temperature | `0.7` |
| `OPERATOR_LLM_TIMEOUT` | Request timeout (seconds) | `120` |
| `OPERATOR_LLM_MAX_RETRIES` | Retry count on transient failures | `2` |

### 3. Run evolution
```bash
python -m src.mrta_rect_coverage.experiments.operator_evolution_runner \
    --provider langchain_openai_compatible --rounds 3 --freeze-best
```

### Third-party endpoint examples
```bash
# DeepSeek
OPERATOR_LLM_BASE_URL=https://api.deepseek.com/v1
OPERATOR_LLM_MODEL=deepseek-chat

# Ollama (local)
OPERATOR_LLM_BASE_URL=http://localhost:11434/v1
OPERATOR_LLM_MODEL=llama3

# Azure OpenAI
OPERATOR_LLM_BASE_URL=https://your-resource.openai.azure.com/
OPERATOR_LLM_MODEL=gpt-4o
```

### LLM response parsing
The LangChain provider uses a two-stage parsing strategy:
1. **JSON parse**: expects a JSON array of `{"name", "description", "code"}` objects.
2. **Code fence fallback**: extracts Python code blocks from markdown fences.
3. If both fail, the raw response is saved to `outputs/operator_evolution/` and the round continues with an empty candidate list (no crash).

## Outputs
- `outputs/operator_evolution/round_XXX_metrics.csv`
- `outputs/operator_evolution/round_XXX_candidates.json` — per-round parsed candidates and validation results
- `outputs/operator_evolution/round_XXX_{type}_prompt.txt` — prompt sent to provider
- `outputs/operator_evolution/generate_{type}_round_XXX_raw.txt` — raw LLM response (LangChain provider only)
- `outputs/operator_evolution/evolution_summary.json`
- `outputs/operator_evolution/best_operators.json`
- `outputs/operator_evolution/plots/round_best_trend.png`
- `outputs/operator_evolution/plots/candidate_leaderboard.png`

## Freezing and ALNS integration
Freeze best operators via runner `--freeze-best` or `freeze_best_operators(...)`.
This creates a registry JSON consumed by ALNS config:
- `frozen_operator_registry_path`
- `use_frozen_repair`
- `use_frozen_destroy`

All frozen generated operators are denied deployment by default, regardless of
whether `source_provider` claims `mock`, `file`, `manual`, or a real LLM. The
current runtime must provide all of:

- `allow_generated_frozen_deployment=True` as a literal boolean;
- `explicit_runtime_deployment_ack=True` as a literal boolean;
- `runtime_authorization_source` set to an accepted current-config/session policy.

The Phase 4F real-provider allow/ack fields remain a strict-boolean compatibility
pair, but no provider label bypasses the common gate. `source_provider` and
`claimed_source_provider` are artifact claims for audit only. Trusted provider
provenance/receipts are not implemented, so registry metadata cannot authorize
deployment. Runtime executor identity and authorization-source strings are
ordinary evidence, not unforgeable capability tokens. Authorization under
`timeout_only` acknowledges residual risk; it does not claim capability isolation.

## Current limitations
- There is no capability sandbox; candidate calls use only a hard-timeout,
  timeout-only subprocess boundary.
- This is not a complete capability sandbox: the child process retains the host user's filesystem and network permissions.
- CPU, memory, environment-variable, and descendant-process-tree capabilities
  are also not isolated.
- File provider expects template-conformant Python modules.
- LangChain provider is synchronous only (async support planned).

## Architecture
```
llm/
├── runtime/                    # LLM client configuration (isolated from core)
│   ├── config.py               # LLMRuntimeConfig + load_from_env()
│   └── client_factory.py       # build_langchain_chat_model()
├── prompts/                    # Structured prompt templates
│   ├── common.py               # Shared fragments (problem, constraints, signatures)
│   ├── operator_generation.py  # Initial generation prompts
│   └── operator_revision.py    # Revision prompts with feedback
└── operator_evolution/         # Evolution subsystem
    ├── provider_interface.py   # OperatorEvolutionProvider Protocol
    ├── mock_provider.py        # Deterministic mock
    ├── file_provider.py        # File-based human-in-the-loop
    ├── langchain_provider.py   # LangChain ChatOpenAI provider
    ├── provider_factory.py     # build_provider() factory
    ├── evolution_loop.py       # Multi-round orchestrator
    └── ...                     # evaluator, loader, metrics, etc.
```

## Next extensions
- Add stricter static checks for candidate modules.
- Add per-instance and per-route bottleneck diagnostics.
- Add online provider adapters as optional plugins (still SDK-agnostic in core).
