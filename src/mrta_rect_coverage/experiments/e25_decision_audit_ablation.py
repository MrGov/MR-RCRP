"""E25: audit the operators' *decisions*, then credit decisions instead of outcomes.

Two questions, two stages.

``describe`` — what do the deployed operators actually decide?  Every destroy call
and every repair call is scored against the exact Route-DP optimum of that moment
(``heuristics/decision_audit.py``), which no scalar log can reconstruct:

* destroy: ``precision`` (fraction of the removed tasks that really belong to the
  ``k`` most expensive tasks under exact marginal saving) and ``saving_capture``;
* repair: ``makespan_hit_rate`` (fraction of removed tasks handed to a route that
  minimises the exact resulting makespan), ``sum_hit_rate``, and the two regret
  magnitudes, split into ``myopic_only`` (served the summed cost, ignored the
  bottleneck) and ``balance_aware`` (the reverse).

``run`` — hypothesis H-Q: replacing the 8/3/1 outcome credit with this exact
decision quality changes which operator the adaptive weights favour, and that is
worth more than the noise it removes.  Both arms audit (so audit cost is identical
in both); the only difference is which quantity feeds the segment weights.

Primary metric: paired relative makespan change ``(off - on) / off`` (positive = the
decision-credited arm is better).  Pre-registered reading:

* KEEP           median >= +0.010 and CI lower bound > 0
* KEEP_WEAK      median > 0 and CI lower bound > 0
* TURN_OFF       |median| < 0.005 and CI covers 0
* TURN_OFF_HURT  median <= -0.005 with CI upper bound < 0
* INCONCLUSIVE   otherwise
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

DEFAULT_OUTPUT = ROOT / 'outputs/e25_decision_audit_ablation'
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
BOOTSTRAP_SEED = 20261121


def _resolve(name: str) -> str:
    return name


def _solver(instance, seed, arm):
    # Both arms audit, so the observation cost is identical and only the credit
    # rule differs.
    overrides = {'decision_audit': True,
                 'decision_driven_selection': arm == 'on'}
    return make_solver(instance, seed, 'AUX', executor='warm',
                       config_overrides=overrides)


def _budget(instance) -> float:
    return float(instance.task_count)


def solve_one(entry, seed, arm):
    instance = load_entry(entry)
    started = perf_counter()
    solver = _solver(instance, seed, arm)
    setup_seconds = perf_counter() - started
    try:
        budget = _budget(instance)
        solver.config.max_runtime_seconds = max(1.0, budget - setup_seconds)
        result = solver.solve()
        total_seconds = perf_counter() - started
        usage = {}
        qualities = {'destroy': [], 'repair': []}
        for row in result.iteration_history:
            usage[row['destroy']] = usage.get(row['destroy'], 0) + 1
            quality = row.get('decision_quality')
            if quality:
                qualities['destroy'].append(quality['destroy'])
                qualities['repair'].append(quality['repair'])
    finally:
        close_extra_executors(solver)

    weights = {
        'destroy': {name: solver.destroy_weights[name] for name in result.operator_usage_stats['destroy']},
        'repair': {name: solver.repair_weights[name] for name in result.operator_usage_stats['repair']},
    }
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
        executor='warm',
        destroy_uses=usage,
        operator_weights=weights,
        decision_quality=dict(
            destroy=(None if not qualities['destroy'] else mean(qualities['destroy'])),
            repair=(None if not qualities['repair'] else mean(qualities['repair'])),
            samples=len(qualities['destroy']),
        ),
        decision_audit=result.decision_audit,
    )


def _audit_suppressed(entry, seed):
    """One short run per (instance, seed) whose only job is to describe decisions."""

    instance = load_entry(entry)
    started = perf_counter()
    solver = _solver(instance, seed, 'off')
    setup_seconds = perf_counter() - started
    try:
        budget = _budget(instance)
        solver.config.max_runtime_seconds = max(1.0, budget - setup_seconds)
        result = solver.solve()
    finally:
        close_extra_executors(solver)
    return dict(instance=entry['instance_id'], seed=seed,
                makespan=result.best_evaluation.makespan,
                iterations=result.iterations_completed,
                audit=result.decision_audit)


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


def stage_describe(output):
    output.mkdir(parents=True, exist_ok=True)
    index = {entry['instance_id']: entry for entry in catalog()['entries']}
    rows = []
    for name in INSTANCES:
        entry = index[_resolve(name)]
        for seed in SEEDS:
            row = _audit_suppressed(entry, seed)
            rows.append(row)
            audit = row['audit'] or {}
            print(f"{row['instance']} s{seed}: iters={row['iterations']:5d} "
                  f"destroy_ops={len(audit.get('destroy', {}))} "
                  f"repair_ops={len(audit.get('repair', {}))}", flush=True)
    write_json(output / 'describe_runs.json', rows)
    return rows


def stage_run(output):
    output.mkdir(parents=True, exist_ok=True)
    index = {entry['instance_id']: entry for entry in catalog()['entries']}
    write_json(output / 'experiment_config.json', dict(
        phase='E25 decision-quality credit vs outcome credit (H-Q)',
        instances=list(INSTANCES), seeds=list(SEEDS), arms=list(ARMS),
        block='AUX (deployed pool: manual + frozen LLM-generated operators)',
        budget='one second per instance task (E12 convention)',
        executor='warm',
        mechanism=('segment reward = 8 * exact decision quality: destroy precision '
                   'against the true top-k marginal saving set, repair makespan hit '
                   'rate against the exact best route for each removed task'),
        variables=('decision_driven_selection only; decision_audit is on in BOTH arms '
                   'so the observation cost is identical'),
        order='arm order alternates by (instance, seed) position',
        primary_metric='paired (off - on) / off, positive favours the decision credit',
        preregistered=dict(KEEP='median >= 0.010 and CI lower > 0',
                           KEEP_WEAK='median > 0 and CI lower > 0',
                           TURN_OFF='|median| < 0.005 and CI covers 0',
                           TURN_OFF_HURT='median <= -0.005 and CI upper < 0'),
        bootstrap=dict(resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED),
    ))
    rows = []
    for position, name in enumerate(INSTANCES):
        entry = index[_resolve(name)]
        for seed in SEEDS:
            order = ARMS if (position + seed) % 2 == 0 else tuple(reversed(ARMS))
            for arm in order:
                row = solve_one(entry, seed, arm)
                rows.append(row)
                quality = row['decision_quality']
                print(f"{row['instance']} s{seed} {arm:3s}: "
                      f"makespan={row['makespan']:.3f} iters={row['iterations']:5d} "
                      f"q_destroy={quality['destroy']} q_repair={quality['repair']} "
                      f"t={row['runtime_seconds']:.2f}s", flush=True)
    write_json(output / 'runs.json', rows)
    return rows


def _aggregate_audit(rows):
    destroy, repair = {}, {}
    for row in rows:
        audit = row.get('audit') or {}
        for operator, block in (audit.get('destroy') or {}).items():
            destroy.setdefault(operator, []).append(block)
        for operator, block in (audit.get('repair') or {}).items():
            repair.setdefault(operator, []).append(block)

    def pooled(blocks, keys):
        out = {}
        for key in keys:
            values = [float(block[key]) for block in blocks if block.get(key) is not None]
            out[f'mean_{key}'] = None if not values else mean(values)
        out['runs'] = len(blocks)
        return out

    return dict(
        destroy={name: pooled(blocks, ('precision', 'saving_capture'))
                 for name, blocks in sorted(destroy.items())},
        repair={name: pooled(blocks, ('makespan_hit_rate', 'sum_hit_rate', 'both_hit_rate',
                                      'neither_rate', 'mean_sum_regret_ratio',
                                      'mean_makespan_regret_ratio'))
                for name, blocks in sorted(repair.items())},
    )


def stage_analyze(output):
    from .e5_destroy_repair import read

    rows = read(output / 'runs.json')
    pick = {(r['instance'], r['seed'], r['arm']): r for r in rows}
    pairs, deltas = [], []
    for name in INSTANCES:
        instance_id = _resolve(name)
        for seed in SEEDS:
            off, on = pick[(instance_id, seed, 'off')], pick[(instance_id, seed, 'on')]
            delta = (off['makespan'] - on['makespan']) / off['makespan']
            deltas.append(delta)
            pairs.append(dict(
                instance=instance_id, seed=seed, task_count=off['task_count'],
                makespan_off=off['makespan'], makespan_on=on['makespan'],
                delta_rel=delta,
                iterations_off=off['iterations'], iterations_on=on['iterations'],
                quality_destroy_off=off['decision_quality']['destroy'],
                quality_destroy_on=on['decision_quality']['destroy'],
                quality_repair_off=off['decision_quality']['repair'],
                quality_repair_on=on['decision_quality']['repair'],
                weights_off=off['operator_weights'], weights_on=on['operator_weights'],
                destroy_uses_off=off['destroy_uses'], destroy_uses_on=on['destroy_uses'],
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
        by_task_count={int(key): dict(
            pairs=len(values), median_delta_rel=median(values),
            mean_delta_rel=mean(values),
            wins=sum(v > 1e-9 for v in values), losses=sum(v < -1e-9 for v in values),
        ) for key, values in sorted(by_tasks.items())},
    )
    describe_rows = []
    describe_path = output / 'describe_runs.json'
    if describe_path.exists():
        describe_rows = read(describe_path)
        summary['decision_profile'] = _aggregate_audit(describe_rows)
    write_json(output / 'pairs.json', pairs)
    write_json(output / 'summary.json', summary)
    _write_report(output, summary, pairs)
    return summary


def _fmt_float(value, pattern='{:.4f}'):
    return 'n/a' if value is None else pattern.format(value)


def _fmt_percent(value):
    return 'n/a' if value is None else f'{value:.4%}'


def _write_report(output, summary, pairs):
    lines = ['# E25 Decision-quality credit vs outcome credit (H-Q)', '',
             f'Output: `{output}`', '',
             '| pairs | median Δ | mean Δ | 95% CI | W/T/L | verdict |',
             '| ---: | ---: | ---: | --- | --- | --- |',
             f"| {summary['pairs']} | {summary['median_delta_rel']:+.4%} | "
             f"{summary['mean_delta_rel']:+.4%} | "
             f"[{summary['ci_lower']:+.4%}, {summary['ci_upper']:+.4%}] | "
             f"{summary['wins']}/{summary['ties']}/{summary['losses']} | "
             f"{summary['verdict']} |", '']
    profile = summary.get('decision_profile')
    if profile:
        lines.extend(['## Decision profile (describe stage, deployed pool)', '',
                      'Destroy: how much of the true marginal-saving set the operator removed.',
                      '',
                      '| destroy | runs | precision | saving capture |',
                      '| --- | ---: | ---: | ---: |'])
        for name, block in profile['destroy'].items():
            lines.append(f"| {name} | {block['runs']} | "
                         f"{_fmt_float(block['mean_precision'])} | "
                         f"{_fmt_float(block['mean_saving_capture'])} |")
        lines.extend(['', 'Repair: did each removed task go to the route that minimises the '
                          'exact resulting makespan?', '',
                      '| repair | runs | makespan hit | sum hit | neither | mean ms regret |',
                      '| --- | ---: | ---: | ---: | ---: | ---: |'])
        for name, block in profile['repair'].items():
            lines.append(f"| {name} | {block['runs']} | "
                         f"{_fmt_float(block.get('mean_makespan_hit_rate'))} | "
                         f"{_fmt_float(block.get('mean_sum_hit_rate'))} | "
                         f"{_fmt_float(block.get('mean_neither_rate'))} | "
                         f"{_fmt_percent(block.get('mean_makespan_regret_ratio'))} |")
        lines.append('')
    lines.extend(['## By task count', '',
                  '| tasks | pairs | median Δ | mean Δ | W/L |',
                  '| ---: | ---: | ---: | ---: | ---: |'])
    for tasks, block in summary['by_task_count'].items():
        lines.append(f"| {tasks} | {block['pairs']} | {block['median_delta_rel']:+.4%} | "
                     f"{block['mean_delta_rel']:+.4%} | {block['wins']}/{block['losses']} |")
    lines.extend(['', '## Paired deltas (positive = decision credit better)', '',
                  '| Instance | seed | off | on | Δ | iters off→on | q_destroy off→on | q_repair off→on |',
                  '| --- | ---: | ---: | ---: | ---: | --- | --- | --- |'])
    for row in pairs:
        def fmt(value):
            return 'n/a' if value is None else f'{value:.3f}'
        lines.append(f"| {row['instance'].removeprefix('development/')} | {row['seed']} | "
                     f"{row['makespan_off']:.3f} | {row['makespan_on']:.3f} | "
                     f"{row['delta_rel']:+.4%} | "
                     f"{row['iterations_off']}→{row['iterations_on']} | "
                     f"{fmt(row['quality_destroy_off'])}→{fmt(row['quality_destroy_on'])} | "
                     f"{fmt(row['quality_repair_off'])}→{fmt(row['quality_repair_on'])} |")
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('describe', 'run', 'analyze'), required=True)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.stage == 'describe':
        stage_describe(args.output.resolve())
    elif args.stage == 'run':
        stage_run(args.output.resolve())
    else:
        summary = stage_analyze(args.output.resolve())
        print(f"median {summary['median_delta_rel']:+.4%} "
              f"CI [{summary['ci_lower']:+.4%}, {summary['ci_upper']:+.4%}] "
              f"-> {summary['verdict']}")


if __name__ == '__main__':
    main()
