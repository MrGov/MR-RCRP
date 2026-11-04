"""Frozen deployment check for the r4_c2 structural portfolio."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import random
from statistics import mean, pstdev
from time import perf_counter
import hashlib
import json
import argparse

from ..core.instance_loader import load_instance
from ..heuristics.alns_solver import ALNSConfig
from ..heuristics.structural_search import (MANUAL_PAIRS, PairPortfolioSolver,
    StructuralExecutor, StructuralKernel, reference_step, validate_actions)
from ..llm.operator_evolution.candidate_execution import CandidateProxy
from ..llm.operator_evolution.candidate_security import code_sha256
from .dataset_protocol import FamilySpec, generate_instance, write_generated_instance
from .structural_population import ROOT, Study, read, save, sha

OUT = ROOT / 'outputs/structural_population/deploy_check_003'
REVIEW = ROOT / 'outputs/structural_population/review_002'
RUN = ROOT / 'outputs/structural_population/run_001'
SEEDS = (23, 29, 31)
DATASET_VERSION = 'structural-deployment-check-v1'
SPECS = (
    FamilySpec('DC_BASE_R4_T40', 'development', 4, 40, 'mixed-aspect',
        'uniform', 'balanced', 'mixed-HV', replicate_count=1),
    FamilySpec('DC_CLUSTER_TURN_R4_T60', 'development', 4, 60, 'horizontal-elongated',
        'clustered', 'coverage-dominated', 'high-HV-sensitivity', replicate_count=1),
    FamilySpec('DC_DISPERSED_TRAVEL_R8_T80', 'development', 8, 80, 'vertical-elongated',
        'dispersed', 'travel-dominated', 'low-HV-sensitivity', replicate_count=1),
    FamilySpec('DC_MULTI_HV_R8_T100', 'development', 8, 100, 'mixed-aspect',
        'multi-cluster', 'balanced', 'high-HV-sensitivity', replicate_count=1),
)


def _load_frozen_study(entries):
    study = Study(REVIEW / 'config.json', resume=True)
    study.out = OUT
    study.entries = {'development': entries, 'reserved': []}
    study.archive = read(RUN / 'archive.json')
    study.groups = {}
    study.ledger = []
    return study


def _prepare_inputs():
    if (OUT / 'protocol.json').exists():
        protocol = read(OUT / 'protocol.json')
        if protocol['configuration_hash'] != _configuration_hash():
            raise ValueError('frozen deployment-check configuration changed')
        current = {
            'r4_c2_sha256_bytes': sha(RUN / 'requests/16_r4_c2/candidate.py'),
            'reference_sha256_bytes': sha(RUN / 'sources/reference.py'),
            'structural_search': sha(ROOT / 'src/mrta_rect_coverage/heuristics/structural_search.py'),
            'alns_solver': sha(ROOT / 'src/mrta_rect_coverage/heuristics/alns_solver.py'),
            'candidate_execution': sha(ROOT / 'src/mrta_rect_coverage/llm/operator_evolution/candidate_execution.py'),
            'persistent_candidate_execution': sha(ROOT / 'src/mrta_rect_coverage/llm/operator_evolution/persistent_candidate_execution.py'),
        }
        if current != protocol['frozen_sources']:
            raise ValueError('frozen source changed after deployment-check preparation')
        for entry in protocol['entries']:
            if sha(ROOT / entry['input_path']) != entry['sha256']:
                raise ValueError('frozen deployment input changed')
        return protocol

    inputs = OUT / 'inputs'
    entries = []
    for spec in SPECS:
        generated = generate_instance(spec, 0, dataset_version=DATASET_VERSION)
        path = write_generated_instance(generated, inputs / spec.family_id)
        rel = path.relative_to(ROOT).as_posix()
        entries.append({
            'instance_id': f'{DATASET_VERSION}/{spec.family_id}/R{spec.n_robots}_T{spec.n_tasks}_0',
            'split': 'development', 'scenario': spec.family_id,
            'n_robots': spec.n_robots, 'n_tasks': spec.n_tasks,
            'replicate_id': 0, 'generation_seed': generated.generation_seed,
            'input_path': rel, 'sha256': sha(path),
            'params': {'sweep_width': generated.instance.sweep_width,
                'sweep_speed': generated.instance.sweep_speed,
                'travel_speed': generated.instance.travel_speed,
                'turning_time': generated.instance.turning_time},
            'family_spec': spec.__dict__,
        })

    pairs = {
        'manual_alns': None,
        'fixed_manual_pairs': [list(p) for p in MANUAL_PAIRS[:2]],
        'manual_pairs_plus_reference': [list(p) for p in MANUAL_PAIRS[:2]] +
            [['reference:destroy', 'reference:repair']],
        'manual_pairs_plus_r4_c2': [list(p) for p in MANUAL_PAIRS[:2]] +
            [['r4_c2:destroy', 'r4_c2:repair']],
    }
    protocol = {
        'version': 'frozen_deployment_check_003',
        'purpose': 'new generated development identities; no candidate feedback or tuning',
        'dataset_version': DATASET_VERSION,
        'generator': 'existing dataset_protocol.generate_instance; deterministic stable family seeds',
        'entries': entries,
        'seeds': list(SEEDS),
        'seconds_by_tasks': {'40': 5, '60': 7, '80': 10, '100': 12},
        'constructor': 'spatial_sort',
        'pairs': pairs,
        'selection': 'equal pair selection, kernel, initialization, acceptance, local search and time budget in groups 2-4; group 1 is original ALNS',
        'frozen_sources': {
            'r4_c2_sha256_bytes': sha(RUN / 'requests/16_r4_c2/candidate.py'),
            'reference_sha256_bytes': sha(RUN / 'sources/reference.py'),
            'structural_search': sha(ROOT / 'src/mrta_rect_coverage/heuristics/structural_search.py'),
            'alns_solver': sha(ROOT / 'src/mrta_rect_coverage/heuristics/alns_solver.py'),
            'candidate_execution': sha(ROOT / 'src/mrta_rect_coverage/llm/operator_evolution/candidate_execution.py'),
            'persistent_candidate_execution': sha(ROOT / 'src/mrta_rect_coverage/llm/operator_evolution/persistent_candidate_execution.py'),
        },
        'prior_history': 'All official structural-benchmark development identities were previously used in E11/E14 or earlier. This check therefore uses new deterministic generated identities and is a development check, not official benchmark confirmation.',
        'model_requests': 0,
    }
    protocol['configuration_hash'] = _configuration_hash(protocol)
    save(OUT / 'protocol.json', protocol)
    save(OUT / 'config.json', {
        'protocol': 'protocol.json', 'configuration_hash': protocol['configuration_hash'],
        'candidate_sha256_bytes': protocol['frozen_sources']['r4_c2_sha256_bytes'],
        'reference_sha256_bytes': protocol['frozen_sources']['reference_sha256_bytes'],
    })
    return protocol


def _configuration_hash(protocol=None):
    if protocol is None:
        path = OUT / 'protocol.json'
        if path.exists():
            protocol = read(path)
        else:
            return _configuration_hash({
                'entries': [spec.__dict__ for spec in SPECS], 'seeds': list(SEEDS),
                'seconds_by_tasks': {'40': 5, '60': 7, '80': 10, '100': 12},
                'constructor': 'spatial_sort',
                'pairs': {'manual_alns': None,
                    'fixed_manual_pairs': [list(p) for p in MANUAL_PAIRS[:2]],
                    'manual_pairs_plus_reference': [list(p) for p in MANUAL_PAIRS[:2]] + [['reference:destroy', 'reference:repair']],
                    'manual_pairs_plus_r4_c2': [list(p) for p in MANUAL_PAIRS[:2]] + [['r4_c2:destroy', 'r4_c2:repair']]},
            })
    material = {k: v for k, v in protocol.items() if k != 'configuration_hash'}
    payload = json.dumps(material, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(payload).hexdigest()


def _reference_executor_check(study, entry):
    from ..core.models import MultiRobotSolution
    from ..core.state_generator import generate_all_states
    instance = load_instance(ROOT / entry['input_path'])
    solver = PairPortfolioSolver(instance, config=ALNSConfig.enhanced(iterations=1, random_seed=701))
    kernel = StructuralKernel(solver, reference_step, width=study.cfg['beam_width'], price_cap=study.cfg['price_cap'])
    evaluation = solver.solution_evaluator.evaluate(solver.initial_solution)
    features = kernel.destroy_features(solver.initial_solution, evaluation, max(2, int(.2 * entry['n_tasks'])))
    rng = random.Random(702)
    native_destroy = reference_step(deepcopy(features), random.Random(702))
    source = RUN / 'sources/reference.py'
    with StructuralExecutor(source, expected_hash=sha(source)) as executor:
        executor_destroy = executor(features, rng)
        partial, _ = solver._remove_tasks(solver.initial_solution, native_destroy)
        partial_eval = solver.solution_evaluator.evaluate_partial(partial)
        remaining = list(native_destroy)
        options = []
        for task in remaining:
            for robot, route in enumerate(partial.routes):
                costs = solver.insertion_pricer.insertion_costs(route, task)
                for position, cost in enumerate(costs):
                    row = list(partial_eval.per_robot_costs)
                    row[robot] = cost
                    options.append({'task': task, 'robot': robot, 'position': position,
                        'cost': cost, 'makespan': max(row), 'total': sum(row),
                        'bottleneck': max(range(len(row)), key=lambda r: row[r])})
        repair_features = {'phase': 'repair', 'branches': [{'routes': deepcopy(partial.routes),
            'costs': list(partial_eval.per_robot_costs), 'remaining': remaining, 'options': options}],
            'depth': 0, 'width': 3, 'prices_remaining': study.cfg['price_cap']}
        native_repair = reference_step(deepcopy(repair_features), random.Random(703))
        executor_repair = executor(repair_features, random.Random(703))
        samples = deepcopy(executor.samples)
    return {'instance_id': entry['instance_id'], 'destroy_equal': native_destroy == executor_destroy,
        'repair_equal': native_repair == executor_repair, 'samples': samples,
        'native_destroy': native_destroy, 'executor_destroy': executor_destroy,
        'native_repair': native_repair, 'executor_repair': executor_repair,
        'state_generator_tasks': len(generate_all_states(instance))}


def _executor_cost_probe(entry):
    from ..core.models import MultiRobotSolution
    instance = load_instance(ROOT / entry['input_path'])
    solver = PairPortfolioSolver(instance, config=ALNSConfig.enhanced(iterations=1, random_seed=811))
    kernel = StructuralKernel(solver, reference_step, width=3, price_cap=80000)
    evaluation = solver.solution_evaluator.evaluate(solver.initial_solution)
    started = perf_counter()
    features = kernel.destroy_features(solver.initial_solution, evaluation, max(2, int(.2 * entry['n_tasks'])))
    feature_seconds = perf_counter() - started
    source = RUN / 'requests/16_r4_c2/candidate.py'
    text = source.read_text(encoding='utf-8')
    proxy = CandidateProxy(source, 'structural', code_sha256(text), timeout_ms=150)
    legacy = []
    for seed in (901, 902, 903):
        copy_started = perf_counter()
        args = (deepcopy(features), random.Random(seed))
        copy_ms = (perf_counter() - copy_started) * 1000
        started = perf_counter()
        result = proxy.execute(args, timeout_ms=150)
        if result.status != 'success': raise RuntimeError(result.error_message)
        validation_started = perf_counter()
        actions = validate_actions(result.result, features)
        validation_ms = (perf_counter() - validation_started) * 1000
        legacy.append({'action': actions, 'wall_ms': (perf_counter()-started)*1000,
            'input_copy_ms': copy_ms, 'return_validation_ms': validation_ms,
            'stages': result.execution_stages})
    optimized = []
    with StructuralExecutor(source, expected_hash=sha(source)) as executor:
        for seed in (901, 902, 903):
            started = perf_counter()
            actions = executor(features, random.Random(seed))
            optimized.append({'action': actions,
                'wall_ms': (perf_counter()-started)*1000,
                'stages': executor.samples[-1]['execution_stages']})
    if [r['action'] for r in legacy] != [r['action'] for r in optimized]:
        raise AssertionError('frozen candidate decisions changed under executor optimization')
    return {'instance_id': entry['instance_id'], 'feature_construction_seconds': feature_seconds,
        'feature_pricing_seconds': kernel._active_record['phase_costs']['exact_pricing'],
        'legacy_per_call': legacy, 'warm_worker': optimized,
        'median_legacy_wall_ms': sorted(r['wall_ms'] for r in legacy)[1],
        'median_warm_wall_ms': sorted(r['wall_ms'] for r in optimized)[1],
        'median_legacy_policy_ms': sorted(r['stages']['policy'] for r in legacy)[1],
        'median_warm_policy_ms': sorted(r['stages']['policy'] for r in optimized)[1]}


def run():
    protocol = _prepare_inputs()
    entries = protocol['entries']
    study = _load_frozen_study(entries)
    if not (OUT / 'executor_cost_probe.json').exists():
        save(OUT / 'executor_cost_probe.json', _executor_cost_probe(entries[0]))
    if not (OUT / 'reference_executor_check.json').exists():
        check = _reference_executor_check(study, entries[0])
        save(OUT / 'reference_executor_check.json', check)
        if not check['destroy_equal'] or not check['repair_equal']:
            raise AssertionError('deterministic reference action mismatch in checked executor')

    labels = list(protocol['pairs'])
    groups = {}
    for label in labels:
        target = OUT / f'{label}.json'
        if target.exists():
            old = read(target)
            if old['configuration_hash'] != protocol['configuration_hash']:
                raise ValueError('existing group belongs to another frozen configuration')
            groups[label] = old
            continue
        partial = OUT / f'{label}.partial.json'
        rows = []
        if partial.exists():
            saved = read(partial)
            if saved['configuration_hash'] != protocol['configuration_hash']:
                raise ValueError('partial group belongs to another frozen configuration')
            rows = saved['rows']
        completed = {(row['instance_id'], row['seed']) for row in rows}
        for entry in entries:
            for seed in SEEDS:
                if (entry['instance_id'], seed) in completed:
                    continue
                row = study.run_one(entry, seed, protocol['pairs'][label])
                row['input_sha256'] = entry['sha256']
                rows.append(row)
                save(partial, {'configuration_hash': protocol['configuration_hash'], 'rows': rows})
                print(json.dumps({'group': label, 'instance': entry['instance_id'], 'seed': seed,
                    'makespan': row.get('makespan'), 'seconds': row['end_to_end_seconds'],
                    'iterations': row.get('iterations'), 'valid': row['valid'], 'error': row['error']}), flush=True)
        data = {'label': label, 'pairs': protocol['pairs'][label], 'rows': rows,
            'valid': all(r['valid'] and not r['error'] for r in rows),
            'configuration_hash': protocol['configuration_hash']}
        save(target, data)
        groups[label] = data

    base = {(r['instance_id'], r['seed']): r for r in groups['manual_alns']['rows']}
    paired = {}
    for label, data in groups.items():
        detail = []
        for row in data['rows']:
            b = base[(row['instance_id'], row['seed'])]
            control = groups['fixed_manual_pairs']
            c = next(x for x in control['rows'] if (x['instance_id'], x['seed']) == (row['instance_id'], row['seed']))
            reference = groups['manual_pairs_plus_reference']
            r = next(x for x in reference['rows'] if (x['instance_id'], x['seed']) == (row['instance_id'], row['seed']))
            detail.append({'instance_id': row['instance_id'], 'seed': row['seed'],
                'makespan': row.get('makespan'), 'vs_manual_alns_percent': _improvement(b, row),
                'vs_fixed_pair_control_percent': _improvement(c, row),
                'vs_reference_percent': _improvement(r, row),
                'end_to_end_seconds': row['end_to_end_seconds'],
                'overshoot_seconds': row['overshoot_seconds'], 'iterations': row.get('iterations'),
                'iterations_attempted': row.get('iterations_attempted'), 'valid': row['valid'],
                'first_legal_complete_seconds': row.get('first_legal_complete_seconds'),
                'first_final_best_seconds': row.get('first_final_best_seconds'),
                'incomplete_iterations': row.get('incomplete_iterations', 0),
                'fallbacks': row.get('fallbacks', []),
                'error': row['error'], 'structural_work': row.get('structural_work', {}),
                'executors': row.get('executors', {}), 'pair_stats': row.get('pair_stats', {})})
        improvements = [x['vs_manual_alns_percent'] for x in detail if x['vs_manual_alns_percent'] is not None]
        comparisons = {}
        for metric in ('vs_manual_alns_percent', 'vs_fixed_pair_control_percent', 'vs_reference_percent'):
            values = [x[metric] for x in detail if x[metric] is not None]
            comparisons[metric] = {'mean_percent': mean(values) if values else None,
                'wins': sum(x > 1e-9 for x in values), 'ties': sum(abs(x) <= 1e-9 for x in values),
                'losses': sum(x < -1e-9 for x in values)}
        by_instance = []
        for instance_id in dict.fromkeys(x['instance_id'] for x in detail):
            instance_rows = [x for x in detail if x['instance_id'] == instance_id]
            by_instance.append({'instance_id': instance_id,
                'makespans': [x['makespan'] for x in instance_rows],
                **{metric: mean(x[metric] for x in instance_rows) for metric in (
                    'vs_manual_alns_percent', 'vs_fixed_pair_control_percent', 'vs_reference_percent')}})
        paired[label] = {'rows': detail, 'mean_improvement_vs_manual_percent': mean(improvements) if improvements else None,
            'wins': sum(x > 1e-9 for x in improvements), 'ties': sum(abs(x) <= 1e-9 for x in improvements),
            'losses': sum(x < -1e-9 for x in improvements),
            'seed_pstdev_makespan': _seed_dispersion(detail),
            'comparisons': comparisons, 'by_instance': by_instance}
    report = {'configuration_hash': protocol['configuration_hash'], 'protocol': protocol,
        'groups': paired, 'executor_cost_probe': read(OUT / 'executor_cost_probe.json'),
        'reference_executor_check': read(OUT / 'reference_executor_check.json'),
        'total_solves': sum(len(g['rows']) for g in groups.values()),
        'all_valid': all(g['valid'] for g in groups.values()),
        'decision': _decision(paired),
        'next_priority': 'Record per-depth r4 repair offers, chosen task/robot/slot, retained branch bottleneck, and post-local-search gain on the weak T40/T80 structures; only then issue one targeted evolution round if a specific missing transition is observed.'}
    save(OUT / 'analysis.json', report)
    print(json.dumps({'output': str(OUT), 'decision': report['decision'],
        'summaries': {k: {x: v for x, v in d.items() if x != 'rows'} for k, d in paired.items()}}, ensure_ascii=True), flush=True)


def _improvement(base, row):
    if not base.get('makespan') or not row.get('makespan'): return None
    return 100 * (base['makespan'] - row['makespan']) / base['makespan']


def _seed_dispersion(rows):
    by_instance = {}
    for row in rows:
        by_instance.setdefault(row['instance_id'], []).append(row['makespan'])
    return {key: pstdev(values) if len(values) > 1 else 0. for key, values in by_instance.items()}


def _decision(paired):
    r4 = paired['manual_pairs_plus_r4_c2']
    ref = paired['manual_pairs_plus_reference']
    r4ref = r4['comparisons']['vs_reference_percent']
    r4manual = r4['comparisons']['vs_manual_alns_percent']
    refmanual = ref['comparisons']['vs_manual_alns_percent']
    by_instance = r4['by_instance']
    repeatable = (r4ref['wins'] >= 10 and r4ref['mean_percent'] > 0 and
                  all(row['vs_reference_percent'] > 0 for row in by_instance))
    if repeatable:
        return 'A: repeatable r4_c2 gain beyond manual ALNS and deterministic reference; keep as elite seed.'
    if (refmanual['mean_percent'] > 0 and r4manual['mean_percent'] > 0 and
            r4ref['mean_percent'] > 0):
        return 'B: structural method may help; LLM increment beyond deterministic reference is not established.'
    if refmanual['mean_percent'] <= 0 and r4manual['mean_percent'] <= 0:
        return 'C: current frozen structural deployment has no measured practical value; do not expand this lineage.'
    return 'D: results are mixed or unstable; one further predeclared paired check is needed before investing in evolution.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checks-only', action='store_true')
    args = parser.parse_args()
    if args.checks_only:
        protocol = _prepare_inputs()
        study = _load_frozen_study(protocol['entries'])
        probe = _executor_cost_probe(protocol['entries'][0])
        save(OUT / 'executor_cost_probe.json', probe)
        reference = _reference_executor_check(study, protocol['entries'][0])
        save(OUT / 'reference_executor_check.json', reference)
        print(json.dumps({'legacy_median_ms': probe['median_legacy_wall_ms'],
            'warm_median_ms': probe['median_warm_wall_ms'],
            'legacy_policy_ms': probe['median_legacy_policy_ms'],
            'warm_policy_ms': probe['median_warm_policy_ms'],
            'r4_actions_equal': [x['action'] for x in probe['legacy_per_call']] ==
                [x['action'] for x in probe['warm_worker']],
            'reference_destroy_equal': reference['destroy_equal'],
            'reference_repair_equal': reference['repair_equal']}, ensure_ascii=True), flush=True)
        return
    run()


if __name__ == '__main__':
    main()
