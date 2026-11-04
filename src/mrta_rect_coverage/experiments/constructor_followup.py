"""One construction diagnosis and one frozen full-solve development regression."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
from contextlib import ExitStack
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from statistics import mean, median, pstdev
from time import perf_counter

from .external_location import OUT as BASE, _prepare, _study, _load_instance, study_pairs
from .structural_population import ROOT, read, save, sha
from .e10b_structural_dp_analysis import evaluator_for
from ..comparison_algorithms import cdabc
from ..comparison_algorithms.common import SearchEnvironment, SearchConfig, SearchDeadline
from ..core.models import MultiRobotSolution
from ..heuristics.structural_search import PairPortfolioSolver
from ..heuristics.work_travel_construction import improve_initialization

OUT = ROOT / 'outputs/structural_population/constructor_followup_005'
CONSTRUCTION_FRACTION = .2
CONSTRUCTION_PRICE_CAP = 10000


def route_match(left, right):
    """Maximum task-set intersection matching; homogeneous robot IDs are arbitrary."""
    a, b = list(map(set, left)), list(map(set, right))
    if len(a) != len(b):
        raise ValueError('robot count mismatch')
    @lru_cache(None)
    def match(i, mask):
        if i == len(a):
            return 0, ()
        choices = []
        for j in range(len(b)):
            if not mask & (1 << j):
                score, tail = match(i + 1, mask | (1 << j))
                choices.append((score + len(a[i] & b[j]), (j,) + tail))
        return max(choices, key=lambda x: (x[0], tuple(-v for v in x[1])))
    kept, mapping = match(0, 0)
    return {'right_robot_for_left': mapping, 'same_assignment_tasks': kept,
            'changed_assignment_tasks': sum(map(len, a)) - kept,
            'matched_routes': [{'left_robot': i, 'right_robot': j,
                'common': sorted(a[i] & b[j]), 'left_only': sorted(a[i] - b[j]),
                'right_only': sorted(b[j] - a[i])} for i, j in enumerate(mapping)]}


def snapshot(solution, evaluation, phase, elapsed):
    return {'phase': phase, 'elapsed_seconds': elapsed,
            'makespan': evaluation.makespan, 'per_robot_costs': evaluation.per_robot_costs,
            'routes': [list(r) for r in solution.routes]}


def verify_snapshots(instance, rows):
    evaluator = evaluator_for(instance)
    for row in rows:
        value = evaluator.evaluate(MultiRobotSolution(row['routes']))
        assert abs(value.makespan - row['makespan']) < 1e-8
        assert all(abs(a - b) < 1e-8 for a, b in zip(value.per_robot_costs, row['per_robot_costs']))
        row['public_exact_verification'] = True


class TraceEnvironment(SearchEnvironment):
    def __init__(self, *args):
        self.snapshots = []
        self.heuristics = 0
        self.init_saved = False
        super().__init__(*args)

    def record(self, phase, generation=0):
        super().record(phase, generation)
        if phase not in ('cycle', 'finished'):
            self.snapshots.append(snapshot(self.best.solution, self.best.evaluation,
                                           phase, self.elapsed()))

    def evaluate(self, solution, phase):
        ind = super().evaluate(solution, phase)
        if phase == 'heuristic_initialization':
            self.heuristics += 1
            self.snapshots.append(snapshot(ind.solution, ind.evaluation,
                f'heuristic_{self.heuristics}_complete', self.elapsed()))
        return ind

    def neighbor(self, *args, **kwargs):
        if not self.init_saved:
            self.snapshots.append(snapshot(self.best.solution, self.best.evaluation,
                                           'initialization_end', self.elapsed()))
            self.init_saved = True
        return super().neighbor(*args, **kwargs)


def diagnose():
    protocol = _prepare()
    target = OUT / 'diagnosis.json'
    if target.exists():
        raise FileExistsError('diagnosis is once-only; read the saved record')
    entry = protocol['instances'][-1]
    seed = protocol['seeds'][0]
    instance = _load_instance(entry)
    env = TraceEnvironment(instance, SearchConfig(max_time=12, seed=seed,
                            population_size=12, scout_limit=50))
    generation = 0
    try:
        generation = cdabc._search(env)
    except SearchDeadline:
        generation = env.generation
    result = env.finish(generation)
    final = snapshot(result.best_solution, result.best_evaluation, 'final', result.runtime_seconds)
    env.snapshots.append(final)
    verify_snapshots(instance, env.snapshots)
    study = _study(protocol)
    started = perf_counter()
    solver = PairPortfolioSolver(instance, constructor=study.cfg['constructor'],
                                 config=study.config(seed, seconds=12))
    initial = snapshot(solver.initial_solution, solver.solution_evaluator.evaluate(solver.initial_solution),
                       'frozen_candidate_initial_reconstruction', perf_counter() - started)
    baseline = next(x for x in read(BASE / 'runs.json') if x['instance_id'] == entry['instance_id']
                    and x['seed'] == seed and x['method'] == 'candidate_portfolio')
    old_best = {'phase': 'frozen_candidate_saved_best', 'elapsed_seconds': baseline['first_final_best_seconds'],
                **{k: baseline[k] for k in ('routes', 'makespan', 'per_robot_costs')}}
    verify_snapshots(instance, [initial, old_best])
    first_best = next(x for x in env.snapshots if abs(x['makespan'] - final['makespan']) < 1e-8)
    save(target, {'baseline_configuration_hash': protocol['configuration_hash'],
        'instance_id': entry['instance_id'], 'input_sha256': entry['sha256'], 'seed': seed,
        'scope': 'one instrumented CDABC replay; not replacement performance data',
        'cdabc_snapshots': env.snapshots, 'cdabc_first_final_best': first_best,
        'candidate_initial': initial, 'candidate_saved_best': old_best,
        'assignment_match_final': route_match(old_best['routes'], final['routes']),
        'sources': {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__)]}})
    for row in env.snapshots:
        if row['phase'] in ('initial_reference', 'heuristic_1_complete', 'heuristic_2_complete', 'initialization_end') or row is first_best:
            print({k: row[k] for k in ('phase', 'elapsed_seconds', 'makespan', 'per_robot_costs')}, flush=True)
    print('saved candidate', initial['makespan'], old_best['makespan'], old_best['elapsed_seconds'], flush=True)


def replay_initial():
    protocol = _prepare()
    target = OUT / 'same_initial_replay.json'
    if target.exists():
        raise FileExistsError('same-initial replay is once-only')
    diagnosis = read(OUT / 'diagnosis.json')
    start_row = next(x for x in diagnosis['cdabc_snapshots'] if x['phase'] == 'heuristic_1_complete')
    entry, seed = protocol['instances'][-1], protocol['seeds'][0]
    study = _study(protocol)
    started = perf_counter()
    instance = _load_instance(entry)
    solver = PairPortfolioSolver(instance, config=study.config(seed, seconds=12))
    solver.initial_solution = MultiRobotSolution([r[:] for r in start_row['routes']])
    with ExitStack() as stack:
        kernels, executors = study.attach(solver, study_pairs(), stack)
        setup = perf_counter() - started
        solver.config.max_runtime_seconds = max(.001, 12 - setup)
        result = solver.solve()
    elapsed = perf_counter() - started
    best = snapshot(result.best_solution, result.best_evaluation, 'same_initial_candidate_best', elapsed)
    verify_snapshots(instance, [best])
    hits = [h for h in result.iteration_history if abs(h['best_makespan'] - best['makespan']) < 1e-8]
    best['first_final_best_seconds'] = setup + hits[0]['elapsed_seconds'] if hits else setup
    save(target, {'scope': 'diagnostic supplied initial solution; excludes its offline construction cost, not deployable performance',
        'seed': seed, 'initial': start_row, 'best': best, 'iterations': result.iterations_completed,
        'pair_stats': solver.deployment_stats, 'history': result.iteration_history,
        'assignment_match': route_match(start_row['routes'], best['routes'])})
    print({k: best[k] for k in ('makespan', 'per_robot_costs', 'first_final_best_seconds')}, flush=True)


def prepare():
    base = _prepare()  # Existing solver/candidate/input identities must still match.
    source_paths = [Path(__file__), ROOT / 'src/mrta_rect_coverage/heuristics/work_travel_construction.py',
                    ROOT / 'src/mrta_rect_coverage/core/incremental_route.py']
    sources = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    reused = {name: sha(BASE / name) for name in ('protocol.json', 'runs.json', 'analysis.json')}
    path = OUT / 'protocol.json'
    if path.exists():
        row = read(path)
        assert row['sources'] == sources, 'modified implementation drift'
        assert row['reused_artifacts'] == reused, 'baseline artifacts changed'
        assert row['configuration_hash'] == config_hash(row), 'protocol changed'
        return base, row
    row = {
        'version': 'constructor_followup_005', 'baseline_configuration_hash': base['configuration_hash'],
        'data_role': 'all eight external_location_004 instances are consumed development regressions',
        'instances': base['instances'], 'seeds': base['seeds'],
        'budgets_seconds_by_tasks': base['budgets_seconds_by_tasks'],
        'pairs': study_pairs(), 'alns_template': base['candidate']['config_template'],
        'construction': {'order': 'CDABC first heuristic: normalized depot travel/work split',
            'insertion': 'exact (global makespan, marginal route cost, robot, slot)',
            'implementation': 'shared incremental pricer; no full DP for every candidate insertion',
            'deadline_fraction_from_input_load_start': CONSTRUCTION_FRACTION,
            'price_cap': CONSTRUCTION_PRICE_CAP, 'fallback': 'retain complete spatial initial solution',
            'scope': 'initialization only; candidate, pairs, weight rules, acceptance formula and LS unchanged'},
        'timing': 'Same input-load-to-executor-cleanup allowance as external_location_004; construction/setup deducted. Independent final verification excluded and separately timed. Historical controls reused, no concurrent solves.',
        'sources': sources, 'reused_artifacts': reused,
        'host': {'platform': platform.platform(), 'python': platform.python_version(),
                 'processor': platform.processor(), 'cpu_count': os.cpu_count()},
        'smoke': 'T100 and dispersed T40, seed 17, once each; full matrix independent of smoke scores',
        'llm_requests': 0, 'formal_data_accessed': False,
    }
    row['configuration_hash'] = config_hash(row)
    save(path, row)
    return base, row


def config_hash(row):
    return hashlib.sha256(json.dumps({k: v for k, v in row.items() if k != 'configuration_hash'},
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def run_modified(study, entry, seed, protocol):
    budget = protocol['budgets_seconds_by_tasks'][str(entry['n_tasks'])]
    start = perf_counter()
    instance = _load_instance(entry)
    solver = PairPortfolioSolver(instance, constructor='spatial_sort', config=study.config(seed, seconds=budget))
    construction = improve_initialization(solver, deadline=start + CONSTRUCTION_FRACTION * budget,
                                         price_cap=CONSTRUCTION_PRICE_CAP)
    # Validation/initial snapshot and all executor preparation remain in the allowance.
    initial_eval = solver.solution_evaluator.evaluate(solver.initial_solution)
    initial = snapshot(solver.initial_solution, initial_eval, 'modified_initial', perf_counter() - start)
    with ExitStack() as stack:
        kernels, executors = study.attach(solver, study_pairs(), stack)
        setup = perf_counter() - start
        solver.config.max_runtime_seconds = max(.001, budget - setup)
        result = solver.solve()
    elapsed = perf_counter() - start
    best = snapshot(result.best_solution, result.best_evaluation, 'modified_final', elapsed)
    verification_start = perf_counter()
    verify_snapshots(instance, [initial, best])
    verification_seconds = perf_counter() - verification_start
    hits = [h for h in result.iteration_history if abs(h['best_makespan'] - best['makespan']) < 1e-8]
    first_best = initial['elapsed_seconds'] if abs(initial['makespan'] - best['makespan']) < 1e-8 else setup + hits[0]['elapsed_seconds']
    records = [row for kernel in kernels.values() for row in kernel.records]
    row = {
        'method': 'work_travel_r4_c2', 'instance_id': entry['instance_id'], 'seed': seed,
        'configuration_hash': protocol['configuration_hash'], 'input_sha256': entry['sha256'],
        'makespan': best['makespan'], 'per_robot_costs': best['per_robot_costs'], 'routes': best['routes'],
        'initial': initial, 'construction': construction, 'end_to_end_seconds': elapsed,
        'budget_seconds': budget, 'overshoot_seconds': max(0., elapsed - budget),
        'setup_seconds': setup, 'verification_seconds': verification_seconds,
        'first_final_best_seconds': first_best, 'iterations': result.iterations_completed,
        'incomplete_iterations': result.incomplete_iterations,
        'incomplete_iteration_records': result.incomplete_iteration_records,
        'pair_stats': solver.deployment_stats, 'history': result.iteration_history,
        'config': asdict(solver.config), 'fallbacks': result.fallback_events,
        'structural_work': {
            'phase_seconds': {p: sum(r['phase_costs'][p] for r in records) for p in
                ('feature_construction', 'exact_pricing', 'strategy_execution', 'reconstruction', 'completion')},
            'policy_calls': sum(r['policy_calls'] for r in records),
            'price_requests': sum(r['price_requests'] for r in records),
            'errors': sum(r['status'] == 'error' for r in records),
            'budget_stops': sum(r['status'] == 'budget_exhausted' for r in records)},
        'executors': {name: x.samples for name, x in executors.items()},
        'feasible': True, 'error': None,
    }
    return row


def run(smoke=False):
    base, protocol = prepare()
    study = _study(base)
    target = OUT / ('smoke.json' if smoke else 'runs.json')
    rows = read(target) if target.exists() else []
    assert all(r['configuration_hash'] == protocol['configuration_hash'] for r in rows)
    done = {(r['instance_id'], r['seed']) for r in rows}
    entries = [base['instances'][-1], base['instances'][1]] if smoke else base['instances']
    seeds = [17] if smoke else base['seeds']
    for entry in entries:
        for seed in seeds:
            if (entry['instance_id'], seed) in done:
                continue
            row = run_modified(study, entry, seed, protocol)
            rows.append(row)
            save(target, rows)
            print({k: row[k] for k in ('instance_id', 'seed', 'makespan', 'end_to_end_seconds', 'feasible')},
                  'construction', row['construction']['status'], row['initial']['makespan'], flush=True)
    if smoke:
        assert len(rows) == 2 and all(r['construction']['status'] == 'complete' for r in rows)
        assert all(r['construction']['selected'] == 'work_travel_exact' for r in rows)
        assert all(r['structural_work']['policy_calls'] > 0 for r in rows)
    else:
        analyze()


def summarize(values):
    return {'mean_percent': mean(values), 'median_percent': median(values),
            'wins_ties_losses': [sum(x > 1e-9 for x in values), sum(abs(x) <= 1e-9 for x in values),
                                 sum(x < -1e-9 for x in values)],
            'maximum_regression_percent': max(0., -min(values))}


def analyze():
    base, protocol = prepare()
    modified = read(OUT / 'runs.json')
    old = read(BASE / 'runs.json')
    assert len(modified) == 24 and len({(r['instance_id'], r['seed']) for r in modified}) == 24
    rows = []
    flat = []
    for entry in base['instances']:
        groups = {'modified': [r for r in modified if r['instance_id'] == entry['instance_id']],
                  'frozen': [r for r in old if r['instance_id'] == entry['instance_id'] and r['method'] == 'candidate_portfolio'],
                  'CDABC': [r for r in old if r['instance_id'] == entry['instance_id'] and r['method'] == 'CDABC']}
        row = {'instance_id': entry['instance_id'], 'scenario': entry['scenario'],
               'robots': entry['n_robots'], 'tasks': entry['n_tasks']}
        for name, records in groups.items():
            assert sorted(r['seed'] for r in records) == base['seeds']
            assert all(r['feasible'] and r['input_sha256'] == entry['sha256'] for r in records)
            row[name + '_mean'] = mean(r['makespan'] for r in records)
            row[name + '_pstdev'] = pstdev(r['makespan'] for r in records)
            row[name + '_seconds'] = mean(r['end_to_end_seconds'] for r in records)
            for r in records:
                flat.append({'instance_id': entry['instance_id'], 'method': name,
                    **{k: r.get(k) for k in ('seed', 'makespan', 'end_to_end_seconds', 'overshoot_seconds',
                       'iterations', 'incomplete_iterations', 'feasible', 'error')},
                    'initial_makespan': r.get('initial', {}).get('makespan', r.get('initial_makespan')),
                    'construction_seconds': r.get('construction', {}).get('elapsed_seconds'),
                    'policy_calls': r.get('structural_work', {}).get('policy_calls'),
                    'source': 'new full solve' if name == 'modified' else 'external_location_004 reused'})
        row['modified_vs_CDABC_percent'] = 100 * (row['CDABC_mean'] - row['modified_mean']) / row['CDABC_mean']
        row['modified_vs_frozen_percent'] = 100 * (row['frozen_mean'] - row['modified_mean']) / row['frozen_mean']
        row['frozen_vs_CDABC_percent'] = 100 * (row['CDABC_mean'] - row['frozen_mean']) / row['CDABC_mean']
        rows.append(row)
    result = {'configuration_hash': protocol['configuration_hash'], 'rows': rows,
        'modified_vs_CDABC': summarize([r['modified_vs_CDABC_percent'] for r in rows]),
        'modified_vs_frozen': summarize([r['modified_vs_frozen_percent'] for r in rows]),
        'other_six_vs_frozen': summarize([r['modified_vs_frozen_percent'] for i, r in enumerate(rows) if i not in (1, 7)]),
        'all_feasible': all(r['feasible'] for r in modified),
        'new_solve_seconds': sum(r['end_to_end_seconds'] for r in modified),
        'max_modified_overshoot_seconds': max(r['overshoot_seconds'] for r in modified),
        'construction_stops': sum(r['construction']['status'] != 'complete' for r in modified),
        'structural_errors': sum(r['structural_work']['errors'] for r in modified),
        'incomplete_iterations': sum(r['incomplete_iterations'] for r in modified)}
    save(OUT / 'analysis.json', result)
    for name, data in [('instance_results.csv', rows), ('seed_results.csv', flat)]:
        with (OUT / name).open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['diagnose', 'same-initial', 'prepare', 'smoke', 'run', 'analyze'], default='run')
    args = parser.parse_args()
    if args.stage == 'diagnose':
        diagnose()
    elif args.stage == 'same-initial':
        replay_initial()
    elif args.stage == 'prepare':
        print(prepare()[1]['configuration_hash'])
    elif args.stage == 'smoke':
        run(smoke=True)
    elif args.stage == 'run':
        run()
    elif args.stage == 'analyze':
        analyze()


if __name__ == '__main__':
    main()
