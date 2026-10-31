"""E23: does the exact-DP transfer-gain ruin criterion pay off at a fixed wall clock?

One block (the deployed ``AUX`` pool: manual destroy/repair plus the frozen
LLM-generated destroy and repair), same solver, same budget, same seeds.  The
only difference between the two arms is whether ``transfer_gain_destroy`` is
added as a fifth destroy operator:

* ``off`` - the pool as deployed today.
* ``on``  - the same pool plus the ruin criterion that scores every candidate
  removal by ``(cost released in its own route) - (cost added in the cheapest
  other route)``, both priced by the same exact Route-DP the evaluator uses.

Primary metric: paired relative makespan change ``(off - on) / off`` (positive =
the transfer-gain arm is better).  Pre-registered reading (see
``docs/operator_economics_and_plan.md`` S5, hypothesis H-E5):

* KEEP          median >= +0.010 and CI lower bound > 0
* KEEP_WEAK     median > 0 and CI lower bound > 0
* TURN_OFF      |median| < 0.005 and CI covers 0
* TURN_OFF_HURT median <= -0.005 with CI upper bound < 0
* INCONCLUSIVE  otherwise

The arm is an exploratory development measurement, not a confirmation: twelve
pairs at six instances can only resolve effects of roughly one percent.
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

DEFAULT_OUTPUT = ROOT / 'outputs/e23_transfer_gain_ablation'
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
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20261107


def _solver(instance, seed, arm):
    overrides = {'transfer_gain_destroy': True} if arm == 'on' else None
    return make_solver(instance, seed, 'AUX', executor='warm',
                       config_overrides=overrides)


def solve_one(entry, seed, arm):
    instance = load_entry(entry)
    started = perf_counter()
    solver = _solver(instance, seed, arm)
    setup_seconds = perf_counter() - started
    try:
        solver.config.max_runtime_seconds = max(1.0, BUDGET_SECONDS - setup_seconds)
        result = solver.solve()
        total_seconds = perf_counter() - started
        usage = {}
        for row in result.iteration_history:
            usage[row['destroy']] = usage.get(row['destroy'], 0) + 1
        spend = {
            group: {
                name: dict(calls=int(record[1]),
                           seconds=round(float(record[0]), 6),
                           mean_ms=None if record[1] == 0
                           else round(1000.0 * record[0] / record[1], 4))
                for name, record in records.items()
            }
            for group, records in result.operator_time_stats.items()
        }
    finally:
        close_extra_executors(solver)
    return dict(
        instance=entry['instance_id'],
        arm=arm,
        seed=seed,
        makespan=result.best_evaluation.makespan,
        initial_makespan=result.initial_makespan,
        iterations=result.iterations_completed,
        runtime_seconds=total_seconds,
        destroy_uses=usage,
        spend=spend,
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
        phase='E23 exact-DP transfer-gain ruin A/B',
        instances=list(INSTANCES), seeds=list(SEEDS), arms=list(ARMS),
        block='AUX (deployed pool: manual + frozen LLM-generated operators)',
        budget_seconds=BUDGET_SECONDS, executor='warm',
        mechanism=('destroy scores each candidate task by (cost released in its own route) '
                   '- (cost added when inserted at the best estimated position of another route), '
                   'both priced by the exact Route-DP, and removes the highest-gain tasks'),
        variables='transfer_gain_destroy only; every other config field identical per pair',
        order='arm order alternates by (instance, seed) position',
        primary_metric='paired (off - on) / off, positive favours the transfer-gain ruin',
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
                print(f"{name} s{seed} {arm:2s}: makespan={row['makespan']:.3f} "
                      f"iters={row['iterations']} t={row['runtime_seconds']:.2f}s", flush=True)
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
            pairs.append(dict(instance=name, seed=seed,
                              makespan_off=off['makespan'], makespan_on=on['makespan'],
                              delta_rel=delta,
                              iterations_off=off['iterations'], iterations_on=on['iterations'],
                              transfer_calls=on['destroy_uses'].get('transfer_gain_destroy', 0),
                              transfer_mean_ms=(on['spend'].get('destroy', {})
                                                .get('transfer_gain_destroy', {})
                                                .get('mean_ms'))))
    lower, upper = _bootstrap(deltas)
    med = median(deltas)
    summary = dict(
        pairs=len(deltas), median_delta_rel=med, mean_delta_rel=mean(deltas),
        ci_lower=lower, ci_upper=upper,
        wins=sum(d > 1e-9 for d in deltas), ties=sum(abs(d) <= 1e-9 for d in deltas),
        losses=sum(d < -1e-9 for d in deltas),
        verdict=_verdict(med, lower, upper),
        median_iterations_off=median(p['iterations_off'] for p in pairs),
        median_iterations_on=median(p['iterations_on'] for p in pairs),
        median_transfer_calls=median(p['transfer_calls'] for p in pairs),
        median_transfer_ms=median(p['transfer_mean_ms'] for p in pairs
                                  if p['transfer_mean_ms'] is not None) or None,
    )
    write_json(output / 'pairs.json', pairs)
    write_json(output / 'summary.json', summary)
    _write_report(output, summary, pairs)
    return summary


def _write_report(output, summary, pairs):
    lines = ['# E23 Exact-DP transfer-gain ruin: fixed wall-clock A/B', '',
             f'Output: `{output}`', '',
             '| pairs | median Δ | mean Δ | 95% CI | W/T/L | median iters off→on | verdict |',
             '| ---: | ---: | ---: | --- | --- | --- | --- |',
             f"| {summary['pairs']} | {summary['median_delta_rel']:+.4%} | "
             f"{summary['mean_delta_rel']:+.4%} | "
             f"[{summary['ci_lower']:+.4%}, {summary['ci_upper']:+.4%}] | "
             f"{summary['wins']}/{summary['ties']}/{summary['losses']} | "
             f"{summary['median_iterations_off']:.0f}→{summary['median_iterations_on']:.0f} | "
             f"{summary['verdict']} |",
             '',
             f"Transfer-gain operator (on arm): median {summary['median_transfer_calls']:.0f} calls per solve, "
             f"median {summary['median_transfer_ms']} ms per call.",
             '', '## Paired deltas (positive = transfer-gain arm better)', '',
             '| Instance | seed | off | on | Δ | transfer calls |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in pairs:
        lines.append(f"| {row['instance'].removeprefix('development/')} | {row['seed']} | "
                     f"{row['makespan_off']:.3f} | {row['makespan_on']:.3f} | "
                     f"{row['delta_rel']:+.4%} | {row['transfer_calls']} |")
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
