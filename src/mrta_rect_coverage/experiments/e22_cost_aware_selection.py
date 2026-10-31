"""E22: does spend-aware operator selection (M2) pay off at a fixed wall clock?

Two blocks, same solver, same budget, only ``cost_aware_selection`` differs:

* ``AUX``  - heterogeneous pool (manual destroy/repair + LLM-generated destroy/repair);
  this is where the mechanism is supposed to bite.
* ``B1``   - homogeneous manual pool; here the mechanism must be a no-op. If it is
  not, whatever it is doing is not "spend awareness" (this is the E16 lesson).

Primary metric: paired relative makespan change ``(off - on) / off`` (positive = the
spend-aware arm is better). Pre-registered reading:

* KEEP         median >= +0.010 and CI lower bound > 0
* KEEP_WEAK    median > 0 and CI lower bound > 0
* TURN_OFF     |median| < 0.005 and CI covers 0
* TURN_OFF_HURT median <= -0.005 with CI upper bound < 0
* INCONCLUSIVE otherwise
"""
from __future__ import annotations

import argparse
import random
from dataclasses import asdict, replace
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from .e3_alns import ROOT, write_json
from .e11_structural_benchmark import catalog, load_entry, make_solver
from .e6_pair_selection import close_extra_executors

DEFAULT_OUTPUT = ROOT / 'outputs/e22_cost_aware_selection'
INSTANCES = (
    'development/BASE/R4_T40_0',
    'development/HV-GEOM/R4_T40_0',
    'development/BOTTLENECK/R4_T40_0',
    'development/SPATIAL/R4_T40_0',
    'development/TURN-HIGH/R4_T40_0',
    'development/TRAVEL-HIGH/R8_T80_0',
)
SEEDS = (0, 1)
BUDGET_SECONDS = 10.0
ARMS = ('off', 'on')
BLOCKS = ('AUX', 'B1')
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20261031


def _solver(instance, seed, block, arm, mode):
    method = 'AUX' if block == 'AUX' else 'B1'
    solver = make_solver(instance, seed, method, executor='warm')
    if arm == 'on':
        solver.config = replace(solver.config, cost_aware_selection=True, cost_aware_mode=mode)
    return solver


def solve_one(entry, seed, block, arm, mode='probability'):
    instance = load_entry(entry)
    started = perf_counter()
    solver = _solver(instance, seed, block, arm, mode)
    setup_seconds = perf_counter() - started
    try:
        solver.config.max_runtime_seconds = max(1.0, BUDGET_SECONDS - setup_seconds)
        result = solver.solve()
        total_seconds = perf_counter() - started
        usage = {}
        for row in result.iteration_history:
            usage.setdefault(row['destroy'], 0)
            usage[row['destroy']] += 1
        spend = {
            group: {
                name: dict(calls=int(record[1]),
                           seconds=round(float(record[0]), 6),
                           mean_ms=None if record[1] == 0 else round(1000.0 * record[0] / record[1], 4))
                for name, record in records.items()
            }
            for group, records in result.operator_time_stats.items()
        }
    finally:
        close_extra_executors(solver)
    return dict(
        instance=entry['instance_id'],
        block=block,
        arm=arm,
        seed=seed,
        makespan=result.best_evaluation.makespan,
        initial_makespan=result.initial_makespan,
        iterations=result.iterations_completed,
        runtime_seconds=total_seconds,
        spend=spend,
        destroy_uses=usage,
        executor='warm',
        mode=mode,
    )


def _bootstrap(deltas):
    rng = random.Random(BOOTSTRAP_SEED)
    draws = []
    n = len(deltas)
    for _ in range(BOOTSTRAP_RESAMPLES):
        draws.append(mean(deltas[rng.randrange(n)] for _ in range(n)))
    draws.sort()
    lower = draws[int(0.025 * len(draws))]
    upper = draws[int(0.975 * len(draws)) - 1]
    return lower, upper


def _verdict(med, lower, upper):
    if med >= 0.010 and lower > 0:
        return 'KEEP'
    if med > 0 and lower > 0:
        return 'KEEP_WEAK'
    if abs(med) < 0.005 and lower <= 0 <= upper:
        return 'TURN_OFF'
    if med <= -0.005 and upper < 0:
        return 'TURN_OFF_HURT'
    return 'INCONCLUSIVE'


def stage_run(output, mode='probability'):
    output.mkdir(parents=True, exist_ok=True)
    index = {entry['instance_id']: entry for entry in catalog()['entries']}
    write_json(output / 'experiment_config.json', dict(
        phase='E22 spend-aware operator selection A/B',
        instances=list(INSTANCES), seeds=list(SEEDS), blocks=list(BLOCKS), arms=list(ARMS),
        budget_seconds=BUDGET_SECONDS, executor='warm', mode=mode,
        mechanism=('probability *= (median call seconds / operator call seconds) ** 1.0 clipped to [0.25, 4]' if mode == 'probability' else 'segment weight uses reward per median-cost call of search time'),
        variables='cost_aware_selection only; every other config field identical per pair',
        order='arm order alternates by (instance, seed) position; one warm-up solve excluded',
        primary_metric='paired (off - on) / off, positive favours spend-aware selection',
        preregistered=dict(KEEP='median >= 0.010 and CI lower > 0', KEEP_WEAK='median > 0 and CI lower > 0',
                           TURN_OFF='|median| < 0.005 and CI covers 0',
                           TURN_OFF_HURT='median <= -0.005 and CI upper < 0'),
        secondary='B1 block (homogeneous manual pool) must be a no-op; otherwise the effect is not spend awareness',
        bootstrap=dict(resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED),
    ))
    rows = []
    for position, name in enumerate(INSTANCES):
        entry = index[name]
        for seed in SEEDS:
            order = ARMS if (position + seed) % 2 == 0 else tuple(reversed(ARMS))
            for block in BLOCKS:
                for arm in order:
                    row = solve_one(entry, seed, block, arm, mode)
                    rows.append(row)
                    print(f"{name} s{seed} {block:3s} {arm:2s}: makespan={row['makespan']:.3f} "
                          f"iters={row['iterations']} t={row['runtime_seconds']:.2f}s", flush=True)
    write_json(output / 'runs.json', rows)
    return rows


def stage_analyze(output):
    from .e5_destroy_repair import read

    rows = read(output / 'runs.json')
    pick = {(r['instance'], r['seed'], r['block'], r['arm']): r for r in rows}
    pairs, summary = [], []
    for block in BLOCKS:
        deltas = []
        for name in INSTANCES:
            for seed in SEEDS:
                off = pick[(name, seed, block, 'off')]
                on = pick[(name, seed, block, 'on')]
                delta = (off['makespan'] - on['makespan']) / off['makespan']
                deltas.append(delta)
                pairs.append(dict(block=block, instance=name, seed=seed,
                                  makespan_off=off['makespan'], makespan_on=on['makespan'],
                                  delta_rel=delta,
                                  iterations_off=off['iterations'], iterations_on=on['iterations']))
        lower, upper = _bootstrap(deltas)
        med = median(deltas)
        summary.append(dict(
            block=block, pairs=len(deltas), median_delta_rel=med, mean_delta_rel=mean(deltas),
            ci_lower=lower, ci_upper=upper,
            wins=sum(d > 1e-9 for d in deltas), ties=sum(abs(d) <= 1e-9 for d in deltas),
            losses=sum(d < -1e-9 for d in deltas),
            verdict=_verdict(med, lower, upper),
            median_iterations_off=median(p['iterations_off'] for p in pairs if p['block'] == block),
            median_iterations_on=median(p['iterations_on'] for p in pairs if p['block'] == block),
        ))
    write_json(output / 'pairs.json', pairs)
    write_json(output / 'summary.json', summary)
    _write_report(output, summary, pairs)
    return summary


def _write_report(output, summary, pairs):
    lines = ['# E22 Spend-aware operator selection (M2): fixed wall-clock A/B', '',
             f'Output: `{output}`', '',
             '| Block | pairs | median Δ | mean Δ | 95% CI | W/T/L | median iters off→on | verdict |',
             '| --- | ---: | ---: | ---: | --- | --- | --- | --- |']
    for row in summary:
        lines.append(
            f"| {row['block']} | {row['pairs']} | {row['median_delta_rel']:+.4%} | "
            f"{row['mean_delta_rel']:+.4%} | [{row['ci_lower']:+.4%}, {row['ci_upper']:+.4%}] | "
            f"{row['wins']}/{row['ties']}/{row['losses']} | "
            f"{row['median_iterations_off']:.0f}→{row['median_iterations_on']:.0f} | {row['verdict']} |")
    lines += ['', '## Paired deltas (positive = spend-aware arm better)', '',
              '| Block | Instance | seed | off | on | Δ |', '| --- | --- | ---: | ---: | ---: | ---: |']
    for row in pairs:
        lines.append(f"| {row['block']} | {row['instance'].removeprefix('development/')} | {row['seed']} | "
                     f"{row['makespan_off']:.3f} | {row['makespan_on']:.3f} | {row['delta_rel']:+.4%} |")
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('run', 'analyze'), required=True)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--mode', choices=('probability', 'throughput'), default='probability')
    args = parser.parse_args()
    stage = args.stage
    if stage == 'run':
        stage_run(args.output.resolve(), args.mode)
    else:
        summary = stage_analyze(args.output.resolve())
        for row in summary:
            print(f"{row['block']}: median {row['median_delta_rel']:+.4%} "
                  f"CI [{row['ci_lower']:+.4%}, {row['ci_upper']:+.4%}] -> {row['verdict']}")


if __name__ == '__main__':
    main()
