# Current Research Positioning

## Objective

**面向入口—出口状态与任务分配、访问顺序相互耦合的多机器人矩形覆盖调度问题，设计具有可验证创新增量的 LLM 辅助进化计算求解方法。**

The research centers on solving MR-RCRP and on the contribution of the LLM-assisted evolution mechanism. Exact Route-DP, incremental pricing, local-search acceleration, candidate execution, audit, and logging enable correctness, efficiency, and evidence; progress in these components alone does not replace the research objective.

## Problem and Method

MR-RCRP assigns each complete rectangular task to one of several homogeneous robots. Each task has eight legal coverage states formed by four entry corners and H/V sweep modes; sweep parity determines the exit corner. Robots start and finish at the common depot. Manhattan travel, sweep processing, and turn time determine each route cost, and the objective minimizes the maximum route cost.

The implemented solver separates three responsibilities:

- **LLM, offline:** generates and revises candidate destroy/repair operators. It does not construct the final task allocation or replace exact evaluation.
- **ALNS, solution space:** searches task-to-robot assignments and ordered routes using destroy/repair, acceptance, adaptive operator control, and local search.
- **Exact Route-DP, fixed route:** chooses the minimum-cost legal state chain and evaluates each fixed task sequence. Incremental pricing and local-search acceleration are supporting implementations around the evaluator.

The repository contains real provider-backed candidate records and deployment integrations alongside manual baselines. It has exercised initial generation, feedback-driven revision, candidate selection, and fixed-source deployment. These are implemented stages of the offline operator pipeline; their existence does not by itself establish that evolution improves end-to-end makespan or that a particular feedback mechanism is novel.

The current 2026-11-02 method evolves structural destruction and reconstruction
programs using exact state-chain and joint-action evidence, then evaluates small
explicit destroy-repair deployments under matched complete-solve budgets.
Initialization, acceptance and priced local search are fixed. The candidate
archive, surviving population and actual deployment are distinct. The earlier
repair-only archive replay and its mixed single-scale results remain historical
evidence on the status page; they do not constrain this batch to one member.

The direct original-paper check in `operator_evolution.md` establishes that
G-LNS already co-evolves destroy/repair operators, full-component ALNS evolution
already studies seven modules and composition effects, and evALNS already mixes
expert and LLM lineages. These generic mechanisms are not novelty claims here.
The problem-specific structural-feedback hypothesis and complete-solve portfolio
benefit require empirical support, including a deterministic mechanism reference.
The completed run_001 batch did not establish an LLM increment: its best single
generated member was slightly behind the deterministic state-chain reference on
development, and the two-member set was worse than the single member. All four
batch-held rows favored manual ALNS; those instances have prior descriptive use
and do not constitute independent validation. The structural-feedback and
portfolio-complementarity hypotheses remain unconfirmed.

## Contribution Candidates and Evidence

Potential contributions must be selected from evidence, not fixed in advance. Candidate mechanisms include LLM operator generation/revision, DP-derived feedback, decision-audit feedback, operator-set complementarity, and interactions with problem-specific search. Each requires a matched comparison that isolates its increment and reports candidate quality separately from complete ALNS deployment quality.

Current records include positive, negative, mixed, and inconclusive results. E17 reports a small-sample candidate-quality contrast between `F1_scalar` and `F2_dataset`; E18 records selected source identities; E19 reports small and mixed deployment differences. E20, E16, E22, E23, and E25 preserve negative or inconclusive outcomes for their specific interventions. E24 reports an efficiency change and a small exploratory end-to-end contrast; it does not establish the central LLM-evolution contribution. See [`program_status_and_design.md`](program_status_and_design.md) for current interpretation limits and verified implementation questions.

No one of DP evidence, audit feedback, or complementary portfolios is declared the unique next path. They remain alternatives to compare against the central question: what verifiable, problem-relevant increment does the LLM-assisted evolution mechanism add to a strong and correctly measured solver?

## Claim Boundaries

- State which code version, operator hashes, data split, budget, seeds, and evaluation mode produced every result.
- Distinguish candidate/repair benchmark results from full-search makespan results.
- Distinguish development exploration from validation and confirmatory evidence. Previously consumed diagnostic data cannot become fresh held-out evidence by relabeling.
- Preserve failures, timeouts, fallbacks, and unfavorable results; do not alter denominators or comparison rules after seeing outcomes.
- Do not claim statistical superiority, generalization, causal mechanism, or novelty without the corresponding independent and matched evidence and an up-to-date literature review.
- Report the simplified model as an estimated completion-time objective under the declared assumptions, not a full physical robot execution model.

## Historical Formulation Map

The token `F2` changed meaning across stages. Keep historical identifiers unchanged:

| Historical document/experiment | Meaning of `F2` |
|---|---|
| `research_method_vNext.md` | A design-level scalar-plus-Exact-DP behavior condition in its F0–F3 proposal; not an implementation identity by itself. |
| `dp_feedback_chain_design_v0.3.md` | Proposed `F2_state` and `F2_contrastive` payload tiers. |
| `task_P2_state_feedback.md` | Planned `F2_state_v2` and `F2_contrastive_v2` formats. |
| E17 (`e17_evidence_arms.py`) | Executed `F2_dataset`, adding a dataset evidence payload based on `F2_state_v2`; it is not the same condition as every historical F2. |

For future work, name a condition by experiment scope, configuration version, and actual information supplied. Do not generalize the outcome of one `F2` condition to other feedback payloads.
