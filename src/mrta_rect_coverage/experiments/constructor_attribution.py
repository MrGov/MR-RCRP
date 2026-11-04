"""Limited matched-construction native-reference check on the two priority cases."""
from pathlib import Path
from statistics import mean

from .constructor_followup import OUT, prepare, run_modified, config_hash
from .external_location import _study, study_pairs
from .structural_population import ROOT, read, save, sha


def main():
    base, parent = prepare()
    pairs = study_pairs()[:2] + [['reference:destroy', 'reference:repair']]
    entries = [base['instances'][-1], base['instances'][1]]
    protocol = {'parent_configuration_hash': parent['configuration_hash'],
        'instances': entries, 'seeds': parent['seeds'], 'pairs': pairs,
        'budgets_seconds_by_tasks': parent['budgets_seconds_by_tasks'],
        'construction': parent['construction'], 'reference_mode': 'native deterministic reference',
        'scope': 'post-main-run attribution on two pre-existing priority cases; no tuning, no generalized claim',
        'reuse_r4_results': sha(OUT / 'runs.json'),
        'sources': {str(p.relative_to(ROOT)): sha(p) for p in
            [Path(__file__), ROOT / 'src/mrta_rect_coverage/experiments/constructor_followup.py']},
        'llm_requests': 0}
    protocol['configuration_hash'] = config_hash(protocol)
    protocol_path = OUT / 'attribution_protocol.json'
    if protocol_path.exists():
        assert read(protocol_path) == protocol
    else:
        save(protocol_path, protocol)
    study = _study(base)
    original_attach = study.attach
    # The existing shared runner owns timing, validation and cleanup. Only its
    # actual deployment pairs differ, using the trusted native reference path.
    study.attach = lambda solver, ignored_pairs, stack: original_attach(solver, pairs, stack)
    target = OUT / 'attribution_runs.json'
    rows = read(target) if target.exists() else []
    for entry in entries:
        for seed in protocol['seeds']:
            if any(r['instance_id'] == entry['instance_id'] and r['seed'] == seed for r in rows):
                continue
            row = run_modified(study, entry, seed, protocol)
            row['method'] = 'work_travel_native_reference'
            row['actual_pairs'] = pairs
            rows.append(row)
            save(target, rows)
            print(entry['scenario'], seed, row['makespan'], row['end_to_end_seconds'], flush=True)
    generated = read(OUT / 'runs.json')
    analysis = []
    for entry in entries:
        native = [r for r in rows if r['instance_id'] == entry['instance_id']]
        r4 = [r for r in generated if r['instance_id'] == entry['instance_id']]
        assert len(native) == len(r4) == 3
        a, b = mean(r['makespan'] for r in r4), mean(r['makespan'] for r in native)
        analysis.append({'scenario': entry['scenario'], 'r4_mean': a, 'reference_mean': b,
            'r4_improvement_percent': 100 * (b - a) / b,
            'seed_pairs': [{'seed': s, 'r4': next(r['makespan'] for r in r4 if r['seed'] == s),
                           'reference': next(r['makespan'] for r in native if r['seed'] == s)} for s in protocol['seeds']]})
    save(OUT / 'attribution_analysis.json', analysis)
    print(analysis, flush=True)


if __name__ == '__main__':
    main()
