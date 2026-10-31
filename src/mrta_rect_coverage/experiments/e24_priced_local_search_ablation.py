"""E24: does exact priced local search buy search quality at a fixed wall clock?

One block (the deployed ``AUX`` pool: manual destroy/repair plus the frozen
LLM-generated destroy and repair), same solver, same seeds.  The only difference
between the two arms is how the per-iteration local search prices its candidate
moves:

* ``off`` - ``run_stronger_local_search``: every candidate neighbour is scored by
  a full ``evaluator.evaluate`` (R route-DP evaluations), which for 8 robots and
  80 tasks is about 9,400 whole-solution evaluations per failed sweep.
* ``on``  - ``run_priced_local_search``: the same neighbourhoods, in the same
  order, with the same first-improvement rule, but each candidate is priced with
  exact forward/backward DP tables in O(64) per slot, plus an exact dominance
  filter (a move that cannot lower the current makespan is skipped).

The two arms are decision-equivalent for the same initial state, so any measured
difference is purely "more iterations inside the same wall clock", not a
different search.  That is what makes this experiment a test of the *budget*
hypothesis rather than a test of a new heuristic.

Primary metric: paired relative makespan change ``(off - on) / off`` (positive =
the priced arm is better).  Pre-registered reading:

* KEEP           median >= +0.010 and CI lower bound > 0
* KEEP_WEAK      median > 0 and CI lower bound > 0
* TURN_OFF       |median| < 0.005 and CI covers 0
* TURN_OFF_HURT  median <= -0.005 with CI upper bound < 0
* INCONCLUSIVE   otherwise

Two instances are small (R2/T10, R2/T20) where local search is cheap and the
predicted gain is near zero; they are included on purpose so a regression would
show up instead of being averaged away.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from .e3_alns import ROOT, write_json
from .e11_structural_benchmark import catalog, load_entry, make_solver
from .e6_pair_selection import close_extra_executors

DEFAULT_OUTPUT = ROOT / 'outputs/e24_priced_local_search_ablation'
INSTANCES = (
    'development/BASE/R2_T10_0',
    'development/HV-GEOM/R2_T20_0',
    'development/BASE/R4_T40_0',
    'development/HV-GEOM/R4_T40_0',
    'development/BOTTLENECK/R4_T40_0',
    'development/SPATIAL/R4_T40_0',
    'development/TURN-HIGH/R4_T40_0',
    'development/TRAVEL-HIGH/R8_T80_0',
)
SEEDS = (0, 1)
ARMS = ('off', 'on')
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20261114


def _solver(instance, seed, arm):
    overrides = {'priced_local_search': True} if arm == 'on' else None
    return make_solver(instance, seed, 'AUX', executor='warm',
                       config_overrides=overrides)


def solve_one(entry, seed, arm):
    instance = load_entry(entry)
    started = perf_counter()
    solver = _solver(instance, seed, arm)
    setup_seconds = perf_counter() - started
    try:
        # Same convention as E12: the budget is one second per task of the instance.
        budget = float(instance.task_count)
        solver.config.max_runtime_seconds = max(1.0, budget - setup_seconds)
        result = solver.solve()
        total_seconds = perf_counter() - started
        split = dict(result.timing_breakdown_seconds)
        timed = sum(split.values())
        usage = {}
        for row in result.iteration_history:
            usage[row['destroy']] = usage.get(row['destroy'], 0) + 1
    finally:
        close_extra_executors(solver)
    return dict(
        instance=entry['instance_id'],
        arm=arm,
        seed=seed,
        task_count=instance.task_count,
        robot_count=instance.robot_count,
        makespan=result.best_evaluation.makespan,
        initial_makespan=result.initial_makespan,
        iterations=result.iterations_completed,
        runtime_seconds=total_seconds,
        budget_seconds=budget,
        stage_seconds={key: round(float(value), 6) for key, value in split.items()},
        stage_shares={key: (None if timed <= 0 else round(float(value) / timed, 4))
                      for key, value in split.items()},
        ms_per_iteration=(None if result.iterations_completed <= 0
                          else round(1000.0 * total_seconds / result.iterations_completed, 4)),
        local_search_mean_ms=(None if result.iterations_completed <= 0
                              else round(1000.0 * float(split.get('local_search_seconds', 0.0))
                                         / result.iterations_completed, 4)),
        destroy_uses=usage,
        executor='warm',
    )


def _bootstrap(deltas):
    rng = random.Random(BOOTSTRAP_SEED)
    draws = [mean(deltas[rng.randrange(len(deltas))] for _ in range(len(deltas)))
             for _ in range(BOOTSTRAP_RESAMPLES)]
    draws.sort()
    return draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1]


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


def stage_run(output):
    output.mkdir(parents=True, exist_ok=True)
    index = {entry['instance_id']: entry for entry in catalog()['entries']}
    write_json(output / 'experiment_config.json', dict(
        phase='E24 exact priced local search A/B',
        instances=list(INSTANCES), seeds=list(SEEDS), arms=list(ARMS),
        block='AUX (deployed pool: manual + frozen LLM-generated operators)',
        budget='one second per instance task (E12 convention)',
        executor='warm',
        mechanism=('local search prices each candidate move with exact forward/backward '
                   'Route-DP tables (O(64) per slot) instead of a full route-DP evaluation '
                   'per candidate, plus an exact dominance filter on the untouchable routes'),
        variables='priced_local_search only; every other config field identical per pair',
        equivalence=('unit tests assert the priced search reproduces the reference '
                     'first-improvement decision for the same initial state, so the '
                     'comparison isolates iteration count, not a different heuristic'),
        order='arm order alternates by (instance, seed) position',
        primary_metric='paired (off - on) / off, positive favours the priced arm',
        preregistered=dict(KEEP='median >= 0.010 and CI lower > 0',
                           KEEP_WEAK='median > 0 and CI lower > 0',
                           TURN_OFF='|median| < 0.005 and CI covers 0',
                           TURN_OFF_HURT='median <= -0.005 and CI upper < 0'),
        bootstrap=dict(resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED),
    ))
    rows = []
    for position, name in enumerate(INSTANCES):
        entry = index[name]
        for seed in SEEDS:
            order = ARMS if (position + seed) % 2 == 0 else tuple(reversed(ARMS))
            for arm in order:
                row = solve_one(entry, seed, arm)
                rows.append(row)
                print(f"{name} s{seed} {arm:3s}: makespan={row['makespan']:.3f} "
                      f"iters={row['iterations']:5d} ms/iter={row['ms_per_iteration']} "
                      f"ls={row['local_search_mean_ms']}ms t={row['runtime_seconds']:.2f}s",
                      flush=True)
    write_json(output / 'runs.json', rows)
    return rows


def stage_analyze(output):
    from .e5_destroy_repair import read

    rows = read(output / 'runs.json')
    pick = {(r['instance'], r['seed'], r['arm']): r for r in rows}
    pairs, deltas = [], []
    for name in INSTANCES:
        for seed in SEEDS:
            off, on = pick[(name, seed, 'off')], pick[(name, seed, 'on')]
            delta = (off['makespan'] - on['makespan']) / off['makespan']
            deltas.append(delta)
            pairs.append(dict(
                instance=name, seed=seed, task_count=off['task_count'],
                makespan_off=off['makespan'], makespan_on=on['makespan'],
                delta_rel=delta,
                iterations_off=off['iterations'], iterations_on=on['iterations'],
                iteration_ratio=(None if off['iterations'] <= 0
                                 else on['iterations'] / off['iterations']),
                ms_per_iteration_off=off['ms_per_iteration'],
                ms_per_iteration_on=on['ms_per_iteration'],
                local_search_ms_off=off['local_search_mean_ms'],
                local_search_ms_on=on['local_search_mean_ms'],
                local_search_share_off=off['stage_shares'].get('local_search'),
                local_search_share_on=on['stage_shares'].get('local_search'),
            ))
    lower, upper = _bootstrap(deltas)
    med = median(deltas)
    by_tasks = {}
    for pair in pairs:
        by_tasks.setdefault(pair['task_count'], []).append(pair['delta_rel'])
    summary = dict(
        pairs=len(deltas), median_delta_rel=med, mean_delta_rel=mean(deltas),
        ci_lower=lower, ci_upper=upper,
        wins=sum(d > 1e-9 for d in deltas), ties=sum(abs(d) <= 1e-9 for d in deltas),
        losses=sum(d < -1e-9 for d in deltas),
        verdict=_verdict(med, lower, upper),
        median_iteration_ratio=median(p['iteration_ratio'] for p in pairs
                                      if p['iteration_ratio'] is not None),
        median_local_search_ms_off=median(p['local_search_ms_off'] for p in pairs
                                          if p['local_search_ms_off'] is not None),
        median_local_search_ms_on=median(p['local_search_ms_on'] for p in pairs
                                         if p['local_search_ms_on'] is not None),
        by_task_count={int(key): dict(
            pairs=len(values), median_delta_rel=median(values),
            mean_delta_rel=mean(values),
            wins=sum(v > 1e-9 for v in values), losses=sum(v < -1e-9 for v in values),
        ) for key, values in sorted(by_tasks.items())},
    )
    write_json(output / 'pairs.json', pairs)
    write_json(output / 'summary.json', summary)
    _write_report(output, summary, pairs)
    return summary


def _write_report(output, summary, pairs):
    lines = ['# E24 Exact priced local search: fixed wall-clock A/B', '',
             f'Output: `{output}`', '',
             '| pairs | median Δ | mean Δ | 95% CI | W/T/L | median iters ratio | verdict |',
             '| ---: | ---: | ---: | --- | --- | ---: | --- |',
             f"| {summary['pairs']} | {summary['median_delta_rel']:+.4%} | "
             f"{summary['mean_delta_rel']:+.4%} | "
             f"[{summary['ci_lower']:+.4%}, {summary['ci_upper']:+.4%}] | "
             f"{summary['wins']}/{summary['ties']}/{summary['losses']} | "
             f"{summary['median_iteration_ratio']:.2f}x | {summary['verdict']} |",
             '',
             f"local search per iteration (median): "
             f"{summary['median_local_search_ms_off']:.3f} ms → "
             f"{summary['median_local_search_ms_on']:.3f} ms.",
             '', '## By task count', '',
             '| tasks | pairs | median Δ | mean Δ | W/L |', '| ---: | ---: | ---: | ---: | ---: |']
    for tasks, block in summary['by_task_count'].items():
        lines.append(f"| {tasks} | {block['pairs']} | {block['median_delta_rel']:+.4%} | "
                     f"{block['mean_delta_rel']:+.4%} | {block['wins']}/{block['losses']} |")
    lines.extend(['', '## Paired deltas (positive = priced arm better)', '',
                  '| Instance | seed | off | on | Δ | iters off→on | ls ms off→on |',
                  '| --- | ---: | ---: | ---: | ---: | --- | --- |'])
    for row in pairs:
        lines.append(f"| {row['instance'].removeprefix('development/')} | {row['seed']} | "
                     f"{row['makespan_off']:.3f} | {row['makespan_on']:.3f} | "
                     f"{row['delta_rel']:+.4%} | "
                     f"{row['iterations_off']}→{row['iterations_on']} | "
                     f"{row['local_search_ms_off']:.3f}→{row['local_search_ms_on']:.3f} |")
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('run', 'analyze'), required=True)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.stage == 'run':
        stage_run(args.output.resolve())
    else:
        summary = stage_analyze(args.output.resolve())
        print(f"median {summary['median_delta_rel']:+.4%} "
              f"CI [{summary['ci_lower']:+.4%}, {summary['ci_upper']:+.4%}] -> {summary['verdict']}")


if __name__ == '__main__':
    main()
