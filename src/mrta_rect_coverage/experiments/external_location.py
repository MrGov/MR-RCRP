"""Frozen 1:1 development comparison of the structural portfolio and CDABC."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
from statistics import mean, median, pstdev
from time import perf_counter

from ..comparison_algorithms.cdabc import solve as solve_cdabc
from ..comparison_algorithms.common import SearchConfig
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..heuristics.alns_solver import ALNSConfig
from ..experiments.e10b_structural_dp_analysis import evaluator_for
from .dataset_protocol import FamilySpec, generate_instance, write_generated_instance
from .structural_population import ROOT, Study, read, save, sha

OUT = ROOT / 'outputs/structural_population/external_location_004'
INPUT_DIR = ROOT / 'outputs/structural_population/deploy_check_003/inputs/external_location_004'
REVIEW = ROOT / 'outputs/structural_population/review_002'
RUN = ROOT / 'outputs/structural_population/run_001'
SEEDS = (17, 29, 43)
DATASET_VERSION = 'mr-rcrp-external-development-v1'
BUDGETS = {'20': 3, '40': 5, '60': 7, '80': 10, '100': 12}

SPECS = (
    FamilySpec('XLOC_BASE_R2_T20', 'development', 2, 20, 'square-ish',
        'uniform', 'balanced', 'mixed-HV', coordinate_scale=180),
    FamilySpec('XLOC_SPATIAL_R4_T40', 'development', 4, 40, 'horizontal-elongated',
        'dispersed', 'travel-dominated', 'low-HV-sensitivity', coordinate_scale=240),
    FamilySpec('XLOC_HV_CLUSTER_R4_T40', 'development', 4, 40, 'mixed-aspect',
        'clustered', 'coverage-dominated', 'high-HV-sensitivity', coordinate_scale=240),
    FamilySpec('XLOC_TURN_CLUSTER_R4_T60', 'development', 4, 60, 'horizontal-elongated',
        'clustered', 'coverage-dominated', 'high-HV-sensitivity', coordinate_scale=300),
    FamilySpec('XLOC_TRAVEL_DISPERSED_R4_T60', 'development', 4, 60, 'vertical-elongated',
        'dispersed', 'travel-dominated', 'low-HV-sensitivity', coordinate_scale=300),
    FamilySpec('XLOC_BASE_R8_T80', 'development', 8, 80, 'square-ish',
        'uniform', 'balanced', 'mixed-HV', coordinate_scale=360),
    FamilySpec('XLOC_MULTICLUSTER_R8_T80', 'development', 8, 80, 'mixed-aspect',
        'multi-cluster', 'travel-dominated', 'high-HV-sensitivity', coordinate_scale=360),
    FamilySpec('XLOC_MULTICLUSTER_R8_T100', 'development', 8, 100, 'mixed-aspect',
        'multi-cluster', 'balanced', 'high-HV-sensitivity', coordinate_scale=420),
)


def _implementation_hashes():
    paths = [
        Path(__file__), RUN / 'requests/16_r4_c2/candidate.py',
        RUN / 'sources/reference.py',
        ROOT / 'src/mrta_rect_coverage/comparison_algorithms/cdabc.py',
        ROOT / 'src/mrta_rect_coverage/comparison_algorithms/common.py',
        ROOT / 'src/mrta_rect_coverage/comparison_algorithms/ADAPTATIONS.md',
        ROOT / 'src/mrta_rect_coverage/heuristics/structural_search.py',
        ROOT / 'src/mrta_rect_coverage/experiments/structural_population.py',
        ROOT / 'src/mrta_rect_coverage/heuristics/alns_solver.py',
        ROOT / 'src/mrta_rect_coverage/heuristics/search_budget.py',
        ROOT / 'src/mrta_rect_coverage/core/solution_evaluator.py',
        ROOT / 'src/mrta_rect_coverage/core/dp_evaluator.py',
        ROOT / 'src/mrta_rect_coverage/core/state_generator.py',
        ROOT / 'src/mrta_rect_coverage/core/cost_matrix.py',
        ROOT / 'src/mrta_rect_coverage/llm/operator_evolution/candidate_execution.py',
        ROOT / 'src/mrta_rect_coverage/llm/operator_evolution/persistent_candidate_execution.py',
    ]
    return {str(path.relative_to(ROOT)): sha(path) for path in paths}


def _prepare():
    if (OUT / 'protocol.json').exists():
        protocol = read(OUT / 'protocol.json')
        if protocol['configuration_hash'] != _configuration_hash(protocol):
            raise ValueError('frozen protocol hash mismatch')
        if protocol['sources'] != _implementation_hashes():
            raise ValueError('frozen implementation or candidate source changed')
        for row in protocol['instances']:
            if sha(ROOT / row['input_path']) != row['sha256']:
                raise ValueError('frozen instance input changed')
        return protocol

    # Freeze the opponent before opening any newly generated instance outcome.
    selected_opponent = {
        'name': 'CDABC',
        'selection_reason': (
            'Selected before this comparison from the four available adaptations: '
            'E12 reported the lowest overall mean makespan (3254.271), all 8 timed '
            'records feasible and zero fallbacks. Its single-objective makespan '
            'contract matches the candidate and it uses the shared Exact Route-DP evaluator.'),
        'implementation_status': 'project adaptation; not author-code reproduction',
        'adaptation': (
            'Minimum H/V processing substitutes agricultural work; population size 12 '
            'instead of paper scale 130; bounded best-insertion steps replace repeated '
            'neighborhood exhaustion. Current CDABC/common source hashes are frozen below.'),
        'prior_e12_evidence': {
            'config_sha256': sha(ROOT / 'outputs/e12_literature_baselines/experiment_config.json'),
            'result_sha256': read(ROOT / 'outputs/e12_literature_baselines/final_validation.json')['result_sha256'],
            'overall_mean_makespan': 3254.2712965048736,
            'final_feasible_records': 8,
            'fallbacks': 0,
        },
        'config': asdict(SearchConfig(max_time=1, seed=0, population_size=12, scout_limit=50)),
    }
    instances = []
    for spec in SPECS:
        generated = generate_instance(spec, 0, dataset_version=DATASET_VERSION)
        path = write_generated_instance(generated, INPUT_DIR / spec.family_id)
        rel = path.relative_to(ROOT).as_posix()
        instances.append({
            'instance_id': f'{DATASET_VERSION}/{spec.family_id}/R{spec.n_robots}_T{spec.n_tasks}_0',
            'scenario': spec.family_id, 'split': 'development',
            'n_robots': spec.n_robots, 'n_tasks': spec.n_tasks, 'replicate_id': 0,
            'generation_seed': generated.generation_seed, 'input_path': rel,
            'sha256': sha(path),
            'params': {k: getattr(generated.instance, k) for k in
                ('sweep_width', 'sweep_speed', 'travel_speed', 'turning_time')},
            'family_spec': asdict(spec),
        })
    protocol = {
        'version': 'external_location_004_frozen',
        'question': 'frozen manual-pair plus r4_c2 portfolio vs credible external single-objective makespan competitor',
        'opponent': selected_opponent,
        'selection_history': (
            'The existing official structural-benchmark development IDs have E11/E14 and '
            'earlier method-work history. This comparison uses eight new deterministic '
            'generator identities; the current four-instance deploy_check_003 inputs '
            'are excluded. No validation/test/final/lockbox inputs are used.'),
        'instances': instances,
        'seeds': list(SEEDS),
        'budgets_seconds_by_tasks': BUDGETS,
        'timing': 'Serial paired run on same host. Input load, state/cost setup, initialization, candidate executor startup/cleanup, search and solver teardown are measured end to end; each method receives the same task-scaled wall allowance. Final independent Exact-DP verification is recorded separately outside the search allowance.',
        'candidate': {
            'method': 'PairPortfolioSolver with exactly the first two frozen MANUAL_PAIRS plus r4_c2 destroy-repair pair',
            'pairs': [['random_destroy', 'greedy_insertion'],
                ['bottleneck_route_destroy', 'regret_k_insertion'],
                ['r4_c2:destroy', 'r4_c2:repair']],
            'pair_selection': 'one initial use per pair, then 10% uniform pair exploration and pair-level segment reward weights',
            'configuration_source': 'review_002/config.json and deploy_check_003/protocol.json',
            'config_template': asdict(ALNSConfig.enhanced(iterations=None, random_seed=17,
                max_runtime_seconds=5, priced_local_search=True, segment_length=10,
                destroy_fraction=0.2, capture_operator_states=False)),
            'llm_requests': 0,
        },
        'opponent_runtime_config': {
            'population_size': 12, 'scout_limit': 50, 'local_depth': 8,
            'mutation_probability': 0.05, 'taskshift_probability': 0.05,
            'elite_fraction': 0.05, 'evaluation_mode': 'exact',
            'parameter_note': 'all parameters match existing SearchConfig defaults or E12 frozen CDABC config',
        },
        'objective_contract': {
            'coverage': 'each task exactly once across one route per robot',
            'states': 'eight legal H/V entry/exit states per rectangular task; both algorithms search with exact Route-DP',
            'costs': 'Manhattan travel at instance travel_speed plus sweep coverage time and turning time; include depot departure and return',
            'objective': 'minimize maximum per-robot route duration; common independent evaluator checks each saved final solution',
        },
        'sources': _implementation_hashes(),
        'llm_requests': 0,
        'formal_evaluation_set_accessed': False,
    }
    protocol['configuration_hash'] = _configuration_hash(protocol)
    save(OUT / 'protocol.json', protocol)
    return protocol


def _configuration_hash(protocol):
    material = {k: v for k, v in protocol.items() if k != 'configuration_hash'}
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _study(protocol):
    study = Study(REVIEW / 'config.json', resume=True)
    study.out = OUT
    study.entries = {'development': protocol['instances'], 'reserved': []}
    study.archive = read(RUN / 'archive.json')
    study.groups = {}
    study.ledger = []
    return study


def _load_instance(row):
    path = ROOT / row['input_path']
    if sha(path) != row['sha256']:
        raise ValueError('instance hash mismatch')
    instance = load_instance(path)
    if (instance.robot_count, instance.task_count) != (row['n_robots'], row['n_tasks']):
        raise ValueError('instance dimensions mismatch')
    for key, value in row['params'].items():
        if getattr(instance, key) != value:
            raise ValueError(f'instance physical parameter mismatch: {key}')
    instance.name = row['instance_id']
    return instance


def _candidate_one(study, entry, seed):
    started = perf_counter()
    record = study.run_one(entry, seed, study_pairs())
    total = perf_counter() - started
    instance = _load_instance(entry)
    solution = MultiRobotSolution(record['routes'])
    verification_started = perf_counter()
    verified = evaluator_for(instance).evaluate(solution)
    verification_seconds = perf_counter() - verification_started
    if abs(verified.makespan - record['makespan']) > 1e-8:
        raise ValueError('candidate common-evaluator verification mismatch')
    return {
        'method': 'candidate_portfolio', 'instance_id': entry['instance_id'],
        'seed': seed, 'makespan': verified.makespan, 'routes': record['routes'],
        'per_robot_costs': verified.per_robot_costs,
        'end_to_end_seconds': total, 'search_elapsed_seconds': record['end_to_end_seconds'],
        'verification_seconds': verification_seconds,
        'budget_seconds': BUDGETS[str(entry['n_tasks'])],
        'overshoot_seconds': max(0, total - BUDGETS[str(entry['n_tasks'])]),
        'iterations': record.get('iterations'), 'iterations_attempted': record.get('iterations_attempted'),
        'first_legal_complete_seconds': record.get('first_legal_complete_seconds'),
        'first_final_best_seconds': record.get('first_final_best_seconds'),
        'structural_work': record.get('structural_work', {}),
        'structural_events': record.get('structural_events', {}),
        'executors': record.get('executors', {}), 'pair_stats': record.get('pair_stats', {}),
        'incomplete_iterations': record.get('incomplete_iterations', 0),
        'fallbacks': record.get('fallbacks', []), 'feasible': True, 'error': None,
    }


def _cdabc_one(entry, seed):
    started = perf_counter()
    instance = _load_instance(entry)
    load_seconds = perf_counter() - started
    budget = BUDGETS[str(entry['n_tasks'])]
    search_budget = max(0.001, budget - load_seconds)
    config = SearchConfig(max_time=search_budget, seed=seed, population_size=12, scout_limit=50)
    result = solve_cdabc(instance, config)
    total = perf_counter() - started
    solution = result.best_solution
    verification_started = perf_counter()
    verified = evaluator_for(instance).evaluate(solution)
    verification_seconds = perf_counter() - verification_started
    if abs(verified.makespan - result.best_evaluation.makespan) > 1e-8:
        raise ValueError('CDABC common-evaluator verification mismatch')
    return {
        'method': 'CDABC', 'instance_id': entry['instance_id'], 'seed': seed,
        'makespan': verified.makespan, 'routes': solution.routes,
        'per_robot_costs': verified.per_robot_costs,
        'end_to_end_seconds': total, 'search_elapsed_seconds': result.runtime_seconds + load_seconds,
        'initialization_seconds': result.initialization_seconds + load_seconds,
        'verification_seconds': verification_seconds, 'budget_seconds': budget,
        'overshoot_seconds': max(0, total - budget), 'iterations': result.iterations,
        'evaluations': result.evaluations, 'route_dp_calls': result.route_dp_calls,
        'cache_misses': result.cache_misses, 'initial_makespan': result.initial_makespan,
        'phase_counts': result.phase_counts, 'config': asdict(config),
        'history': result.history, 'feasible': True, 'error': None,
    }


def study_pairs():
    return [['random_destroy', 'greedy_insertion'],
        ['bottleneck_route_destroy', 'regret_k_insertion'],
        ['r4_c2:destroy', 'r4_c2:repair']]


def run():
    protocol = _prepare()
    study = _study(protocol)
    target = OUT / 'runs.json'
    records = read(target) if target.exists() else []
    indexed = {(r['instance_id'], r['seed'], r['method']): r for r in records}
    for i, entry in enumerate(protocol['instances']):
        for seed in protocol['seeds']:
            # Alternating order controls simple machine-load/order bias.
            methods = ('candidate_portfolio', 'CDABC') if (i + seed) % 2 == 0 else ('CDABC', 'candidate_portfolio')
            for method in methods:
                key = (entry['instance_id'], seed, method)
                if key in indexed:
                    continue
                try:
                    row = (_candidate_one(study, entry, seed) if method == 'candidate_portfolio'
                           else _cdabc_one(entry, seed))
                except Exception as exc:
                    row = {'method': method, 'instance_id': entry['instance_id'], 'seed': seed,
                        'budget_seconds': BUDGETS[str(entry['n_tasks'])], 'feasible': False,
                        'error': f'{type(exc).__name__}: {exc}', 'end_to_end_seconds': None,
                        'makespan': None}
                row['input_sha256'] = entry['sha256']
                row['configuration_hash'] = protocol['configuration_hash']
                records.append(row); indexed[key] = row
                save(target, records)
                print(json.dumps({k: row.get(k) for k in
                    ('instance_id', 'seed', 'method', 'makespan', 'end_to_end_seconds', 'feasible', 'error')}), flush=True)
    _analyze(protocol, records)


def _analyze(protocol, records):
    by_key = {(r['instance_id'], r['seed'], r['method']): r for r in records}
    if len(by_key) != len(protocol['instances']) * len(protocol['seeds']) * 2:
        raise ValueError('incomplete scheduled denominator')
    rows = []
    instance_rows = []
    for entry in protocol['instances']:
        candidate = [by_key[(entry['instance_id'], s, 'candidate_portfolio')] for s in protocol['seeds']]
        opponent = [by_key[(entry['instance_id'], s, 'CDABC')] for s in protocol['seeds']]
        valid = all(x['feasible'] and x['makespan'] is not None for x in candidate + opponent)
        candidate_mean = mean(x['makespan'] for x in candidate) if valid else None
        opponent_mean = mean(x['makespan'] for x in opponent) if valid else None
        improvement = 100 * (opponent_mean - candidate_mean) / opponent_mean if valid else None
        row = {
            'instance_id': entry['instance_id'], 'scenario': entry['scenario'],
            'robots': entry['n_robots'], 'tasks': entry['n_tasks'], 'input_sha256': entry['sha256'],
            'candidate_mean_makespan': candidate_mean,
            'candidate_seed_makespans': [x['makespan'] for x in candidate],
            'candidate_seed_pstdev': pstdev(x['makespan'] for x in candidate) if valid else None,
            'candidate_mean_seconds': mean(x['end_to_end_seconds'] for x in candidate if x['end_to_end_seconds'] is not None),
            'CDABC_mean_makespan': opponent_mean,
            'CDABC_seed_makespans': [x['makespan'] for x in opponent],
            'CDABC_seed_pstdev': pstdev(x['makespan'] for x in opponent) if valid else None,
            'CDABC_mean_seconds': mean(x['end_to_end_seconds'] for x in opponent if x['end_to_end_seconds'] is not None),
            'improvement_percent': improvement, 'feasible': valid,
        }
        rows.append(row)
        instance_rows.append(row)

    paired = [x['improvement_percent'] for x in rows if x['improvement_percent'] is not None]
    wins = sum(x > 1e-9 for x in paired); ties = sum(abs(x) <= 1e-9 for x in paired)
    losses = sum(x < -1e-9 for x in paired)
    largest_loss = min(paired) if paired else None
    result = {
        'configuration_hash': protocol['configuration_hash'], 'protocol': protocol,
        'rows': rows, 'seed_level_records': records,
        'summary': {
            'instances': len(rows), 'scheduled_seed_pairs_per_method': len(records) // 2,
            'mean_instance_improvement_percent': mean(paired) if paired else None,
            'median_instance_improvement_percent': median(paired) if paired else None,
            'wins_ties_losses': [wins, ties, losses],
            'maximum_regression_percent': abs(largest_loss) if largest_loss is not None and largest_loss < 0 else 0,
            'max_candidate_seed_pstdev': max((r['candidate_seed_pstdev'] or 0) for r in rows),
            'mean_candidate_time_seconds': mean(r['candidate_mean_seconds'] for r in rows),
            'mean_CDABC_time_seconds': mean(r['CDABC_mean_seconds'] for r in rows),
            'all_feasible': all(r['feasible'] for r in rows),
        },
        'known_internal_reference': {
            'deploy_check_003_result_reused': True,
            'r4_c2_portfolio_mean_improvement_vs_deterministic_reference_percent': 0.6561124130760616,
            'note': 'same candidate variant was not rerun; internal reference is historical context, not an extra comparison arm',
        },
        'decision': _decision(rows),
    }
    save(OUT / 'analysis.json', result)
    _write_results_csv(rows)
    print(json.dumps({'summary': result['summary'], 'decision': result['decision']}, ensure_ascii=True), flush=True)


def _write_results_csv(rows):
    import csv
    fields = ['instance_id', 'scenario', 'robots', 'tasks', 'candidate_mean_makespan',
        'candidate_seed_makespans', 'candidate_seed_pstdev', 'candidate_mean_seconds',
        'CDABC_mean_makespan', 'CDABC_seed_makespans', 'CDABC_seed_pstdev',
        'CDABC_mean_seconds', 'improvement_percent', 'feasible', 'input_sha256']
    with (OUT / 'instance_results.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row,
                'candidate_seed_makespans': json.dumps(row['candidate_seed_makespans']),
                'CDABC_seed_makespans': json.dumps(row['CDABC_seed_makespans'])})


def _decision(rows):
    valid = [x for x in rows if x['improvement_percent'] is not None]
    if not valid:
        return 'No performance conclusion: at least one side did not return evaluable feasible solutions.'
    gains = [x['improvement_percent'] for x in valid]
    mean_gain = mean(gains)
    positive = sum(x > 1e-9 for x in gains)
    size_gains = {}
    for n in sorted({x['tasks'] for x in valid}):
        size_gains[str(n)] = mean(x['improvement_percent'] for x in valid if x['tasks'] == n)
    broad = positive >= 6 and all(v > 0 for v in size_gains.values())
    if mean_gain > 1 and broad:
        return 'Candidate leads broadly: freeze this version and expand a formal comparison to more instances and strong opponents.'
    worst = min(valid, key=lambda x: x['improvement_percent'])
    best = max(valid, key=lambda x: x['improvement_percent'])
    if mean_gain > -1 and positive >= 2:
        return (f'Mixed/near parity: prioritize a targeted full-search improvement on {worst["scenario"]}; '
            f'preserve {best["scenario"]} as a strong case. Do not expand the formal matrix yet.')
    return (f'Candidate trails materially: first address its worst-case {worst["scenario"]} '
        'search capability or time allocation before broadening external comparisons.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    protocol = _prepare()
    if args.prepare_only:
        print(json.dumps({'opponent': protocol['opponent'], 'configuration_hash': protocol['configuration_hash'],
            'instances': protocol['instances'], 'seeds': protocol['seeds'],
            'budgets': protocol['budgets_seconds_by_tasks']}, ensure_ascii=False, indent=2))
    else:
        run()


if __name__ == '__main__':
    main()
