# Offline Operator Evolution

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
