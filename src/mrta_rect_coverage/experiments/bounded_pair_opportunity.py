"""Cache equivalence, one deployment recheck and at most three pair diagnostics.

Uses the existing search kernel even for single-pair diagnosis. Its additional
offline enumeration is never included in a normal deployment score.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
from statistics import mean
from time import perf_counter

from .bounded_repair_strategy import (
    ROOT, MANUAL, read, fresh, save, digest, make_solver, deploy, snapshot, work, trace,
)
from ..core.models import MultiRobotSolution
from ..heuristics.bounded_repair_search import BoundedRepairSearch, SearchBudget, StrategyExecutor, reference_rank_pairs
from ..heuristics.priced_local_search import run_priced_local_search


def semantic(record):
    return {k:v for k,v in record.items() if k not in ('pricing_work','dp_work','runtime_seconds')}


def stamp(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def load_policy(stack, path):
    return stack.enter_context(StrategyExecutor(path,expected_hash=read(path.parent/'lineage.json')['hash']))


def policies(source):
    return {f'generation_{i}':source/f'request_{i:02d}/candidate.py' for i in (1,2)}


def choice_counts(records, max_pairs):
    """Ranking freedom, not evidence that extra search is itself useful."""
    stats = Counter()
    for k in records:
        n = len(k['features']['pairs']) if k['features'] else 0
        actual = len(k['selected_pairs'])
        stats['calls'] += 1
        stats['only_one_pair'] += int(n == 1)
        stats['zero_candidates'] += int(n == 0)
        stats['all_pairs_searched_more_than_one'] += int(n > 1 and actual == n)
        stats['zero_pairs_expanded'] += int(actual == 0)
        stats['budget_limited_prefix'] += int(actual < min(n, max_pairs))
        stats['choice_opportunity'] += int(n > actual > 0)
    return dict(stats)


def prepare(config_path):
    config = read(config_path)
    out, source = ROOT/config['output_dir'], ROOT/config['source_run']
    out.mkdir(parents=True,exist_ok=False)
    save(out/'config.json',config)
    cases,entries,base = read(source/'cases.json'),read(source/'entries.json'),read(source/'config.json')
    save(out/'cases.json',cases)
    save(out/'entries.json',entries)
    save(out/'base_config.json',base)
    reference = read(source/'paired_reference.json')['cases']
    selected = []
    for family in ('SPATIAL','BOTTLENECK'):
        index = next(i for i,r in enumerate(reference) if family in r['instance_id'] and
                     len(r['kernel']['features']['pairs'])>base['search']['max_pairs'])
        selected.append({**deepcopy(cases[index]),'source_ref':f'{config["source_run"]}/paired_reference.json#/cases/{index}',
                         'paired_index':index,'rule':config['representative_rules'][len(selected)]})
    old = read(source/'deployment_iterations.json')
    deployment = next(r for r in old if r['group']=='reference' and r['seed']==23 and 'BOTTLENECK' in r['instance_id'])
    kr = next(k for k in deployment['kernel_records'] if k['features'] and len(k['features']['pairs'])==15)
    features=kr['features']
    index=deployment['kernel_records'].index(kr)
    hist=[h for h in deployment['history'] if h['repair']=='bounded_reference'][index]
    case={'instance_id':deployment['instance_id'],'partial_routes':deepcopy(features['routes']),
          'removed_tasks':[int(t) for t in features['tasks']], 'seed':23+hist['iteration'],
          'trace_seed':23,'trace_iteration':hist['iteration'],'band':'first_deployment_six_task_pool',
          'source_ref':f'{config["source_run"]}/deployment_iterations.json#reference/BOTTLENECK/seed23/kernel/{index}',
          'rule':config['representative_rules'][2]}
    assert case['removed_tasks']==hist['removed_tasks']
    assert case['partial_routes']==hist['partial_routes']
    case['case_id']=stamp(case)[:16]
    selected.append(case)
    save(out/'diagnostic_states.json',selected)  # fixed before additional search
    historical=[]
    for mode in ('iterations','time'):
        for row in read(source/f'deployment_{mode}.json'):
            historical.append({'mode':mode,'group':row['group'],'instance_id':row['instance_id'],
                               'seed':row['seed'],'counts':choice_counts(row['kernel_records'],base['search']['max_pairs'])})
    save(out/'historical_choice_counts.json',historical)
    recheck=out/'recheck'; recheck.mkdir()
    save(recheck/'config.json',{**base,'output_dir':str(recheck.relative_to(ROOT)),
         'run_stop_reason':'one cache-only recheck of existing sources; no new model requests'})
    save(recheck/'entries.json',entries)
    print(json.dumps({'selected':[{'instance':c['instance_id'],'removed':len(c['removed_tasks']),
                                  'source':c['source_ref']} for c in selected]}),flush=True)


def verify(out):
    fresh(out/'equivalence.json')
    config=read(out/'config.json'); source=ROOT/config['source_run']
    base=read(out/'base_config.json'); cases=read(out/'cases.json')
    entries={e['instance_id']:e for e in read(out/'entries.json')}
    rows=[]
    with ExitStack() as stack:
        rankers={'reference':reference_rank_pairs,**{k:load_policy(stack,p) for k,p in policies(source).items()}}
        for label,ranker in rankers.items():
            for i,case in enumerate(cases):
                results=[]
                for mode in ('uncached','cached'):
                    s=make_solver(entries[case['instance_id']],case['seed'],iterations=1)
                    if mode=='uncached':
                        s.insertion_pricer.insertion_costs=s.insertion_pricer.insertion_costs_uncached
                    partial=MultiRobotSolution(deepcopy(case['partial_routes']))
                    kernel=BoundedRepairSearch(s,ranker=ranker,budget=SearchBudget(**base['search']))
                    repaired=kernel(partial,case['removed_tasks'],s.solution_evaluator.evaluate_partial(partial))
                    refined,ev=run_priced_local_search(deepcopy(repaired),s.solution_evaluator,s.insertion_pricer,max_iterations=1)
                    results.append({'kernel':kernel.records[-1],'post_ls_routes':refined.routes,'post_ls':ev.makespan,
                                    'work':snapshot(s)})
                a,b=results
                assert semantic(a['kernel'])==semantic(b['kernel'])
                assert a['post_ls_routes']==b['post_ls_routes'] and a['post_ls']==b['post_ls']
                assert a['work']['prices']['insertion_requests']==b['work']['prices']['insertion_requests']
                rows.append({'label':label,'case_index':i,'case_id':case['case_id'],
                    'semantic_hash':stamp(semantic(b['kernel'])),'ranked_pairs':b['kernel']['ranked_pairs'],
                    'selected_pairs':b['kernel']['selected_pairs'],'repair_routes':b['kernel']['routes'],
                    'repair':b['kernel']['makespan'],'post_ls_routes':b['post_ls_routes'],'post_ls':b['post_ls'],
                    'logical_budget_requests':b['kernel']['price_requests'],
                    'uncached_work':a['work'],'cached_work':b['work']})
        # A small semantic control before timed runs. No equality requirement for calculations or cache hits.
        trajectory=[]
        entry=next(e for e in entries.values() if 'BOTTLENECK' in e['instance_id'])
        for label in ['manual',*rankers]:
            records=[]
            for mode in ('uncached','cached'):
                s=make_solver(entry,23,iterations=12,max_runtime_seconds=None)
                if mode=='uncached':
                    s.insertion_pricer.insertion_costs=s.insertion_pricer.insertion_costs_uncached
                kernel=None
                if label!='manual':
                    kernel=BoundedRepairSearch(s,ranker=rankers[label],budget=SearchBudget(**base['search']))
                    s.register_bounded_repair(kernel,name='bounded_'+label)
                result=s.solve()
                keys=('destroy','repair','accepted','candidate_delta','best_makespan','current_makespan',
                      'repaired_routes','refined_routes','temperature','removed_tasks')
                records.append({'history':[{k:h.get(k) for k in keys} for h in result.iteration_history],
                                'routes':result.best_solution.routes,'work':snapshot(s),
                                'kernel':[semantic(k) for k in kernel.records] if kernel else []})
            a,b=records
            assert a['history']==b['history'] and a['routes']==b['routes'] and a['kernel']==b['kernel']
            assert a['work']['prices']['insertion_requests']==b['work']['prices']['insertion_requests']
            trajectory.append({'group':label,'history_hash':stamp(b['history']),
                               'uncached_work':a['work'],'cached_work':b['work']})
    changes=[]
    for label in ('generation_1','generation_2'):
        parent='reference' if label=='generation_1' else 'generation_1'
        comparisons=[]
        for i in range(len(cases)):
            a=next(r for r in rows if r['label']==parent and r['case_index']==i)
            b=next(r for r in rows if r['label']==label and r['case_index']==i)
            comparisons.append({'case_index':i,'ranking_changed':a['ranked_pairs']!=b['ranked_pairs'],
                'selected_set_changed':set(a['selected_pairs'])!=set(b['selected_pairs']),
                'completed_routes_changed':a['repair_routes']!=b['repair_routes'],
                'repair_makespan_changed':a['repair']!=b['repair'],
                'post_ls_routes_changed':a['post_ls_routes']!=b['post_ls_routes'],
                'post_ls_makespan_changed':a['post_ls']!=b['post_ls']})
        changes.append({'parent':parent,'child':label,'cases':comparisons})
    save(out/'equivalence.json',{'paired':rows,'fixed_trajectory':trajectory,'behavior_changes':changes,
          'all_equal':True,'scope':'36 paired cache controls; four groups x 12 fixed iterations, no deadline'})
    print('PASS: 36 paired controls and four fixed-iteration cache controls; logical requests unchanged.',flush=True)


def recheck(out):
    if not read(out/'equivalence.json')['all_equal']:
        raise ValueError('semantic verification required')
    source=ROOT/read(out/'config.json')['source_run']
    deploy(out/'recheck',policy_paths=policies(source),groups=['manual','reference','generation_1','generation_2'])
    old=read(source/'deployment_iterations.json')
    new=read(out/'recheck/deployment_iterations.json')
    comparisons=[]
    keys=('destroy','repair','accepted','candidate_delta','best_makespan','current_makespan',
          'repaired_routes','refined_routes','temperature','removed_tasks')
    for b in new:
        a=next(x for x in old if (x['group'],x['instance_id'],x['seed'])==(b['group'],b['instance_id'],b['seed']))
        assert b['best_routes']==a['best_routes'] and b['makespan']==a['makespan']
        assert [{k:h.get(k) for k in keys} for h in a['history']]==[{k:h.get(k) for k in keys} for h in b['history']]
        assert len(a['kernel_records'])==len(b['kernel_records'])
        for x,y in zip(a['kernel_records'],b['kernel_records']):
            xx,yy=semantic(x),semantic(y); yy.pop('ranked_pairs',None)
            assert xx==yy
        comparisons.append({'group':b['group'],'instance_id':b['instance_id'],'seed':b['seed'],
                            'matches_saved_original':True,'cached_work':b['work']})
    save(out/'historical_fixed_equivalence.json',comparisons)
    print('PASS: all 32 optimized fixed solves match saved pre-optimization search traces.',flush=True)


def force_first(pair_id):
    def rank(features,rng):
        ids=reference_rank_pairs(features,rng)
        return [pair_id]+[x for x in ids if x!=pair_id]
    return rank


def diagnostic(out):
    fresh(out/'diagnostic.json')
    config,base=read(out/'config.json'),read(out/'base_config.json')
    source=ROOT/config['source_run']
    entries={e['instance_id']:e for e in read(out/'entries.json')}
    all_rows=[]
    started=perf_counter()
    with ExitStack() as stack:
        rankers={'reference':reference_rank_pairs,**{k:load_policy(stack,p) for k,p in policies(source).items()}}
        for case in read(out/'diagnostic_states.json'):
            entry=entries[case['instance_id']]
            def evaluate(ranker,budget):
                s=make_solver(entry,case['seed'],iterations=1)
                kernel=BoundedRepairSearch(s,ranker=ranker,budget=budget)
                partial=MultiRobotSolution(deepcopy(case['partial_routes']))
                before,clock=snapshot(s),perf_counter()
                repaired=kernel(partial,case['removed_tasks'],s.solution_evaluator.evaluate_partial(partial))
                repair_seconds=perf_counter()-clock
                repair_work=work(before,snapshot(s))
                raw=s.solution_evaluator.evaluate(repaired)
                before,clock=snapshot(s),perf_counter()
                refined,ev=run_priced_local_search(deepcopy(repaired),s.solution_evaluator,s.insertion_pricer,max_iterations=1)
                return {'kernel':kernel.records[-1],'repair':raw.makespan,'post_ls':ev.makespan,
                        'repair_trace':trace(raw),'post_ls_trace':trace(ev),'post_ls_routes':refined.routes,
                        'repair_seconds':repair_seconds,'ls_seconds':perf_counter()-clock,
                        'repair_work':repair_work,'ls_work':work(before,snapshot(s))}
            budget=SearchBudget(**base['search'])
            deployed={name:evaluate(ranker,budget) for name,ranker in rankers.items()}
            features=deployed['reference']['kernel']['features']
            ids=[p['id'] for p in features['pairs']]
            assert len(ids)<=config['diagnostic_max_pairs_per_state'] and len(ids)<=15
            each={pid:evaluate(force_first(pid),replace(budget,max_pairs=1)) for pid in ids}
            best_id=min(ids,key=lambda pid:(each[pid]['post_ls'],each[pid]['repair'],pid))
            best=each[best_id]
            missed=all(best_id not in d['kernel']['selected_pairs'] for d in deployed.values())
            better=best['post_ls'] < min(d['post_ls'] for d in deployed.values())-config['minimum_improvement']
            intervention=None
            # One normal-budget witness, not an all-subsets enumeration. Prefer a
            # second pair whose raw key will not displace the diagnosed good result.
            if missed and better:
                best_key=(best['repair'],sum(r['cost'] for r in best['repair_trace']))
                candidates=[pid for pid in ids if pid!=best_id and
                    (each[pid]['repair'],sum(r['cost'] for r in each[pid]['repair_trace']))>=best_key]
                if candidates:
                    second=next(pid for pid in reference_rank_pairs(features,random.Random(case['seed'])) if pid in candidates)
                    def witness(f,rng):
                        return [best_id,second]+[pid for pid in reference_rank_pairs(f,rng) if pid not in (best_id,second)]
                    intervention=evaluate(witness,budget)
            actionable=bool(intervention and intervention['post_ls']<min(d['post_ls'] for d in deployed.values())-config['minimum_improvement'])
            all_rows.append({'case':case,'deployed_policies':deployed,'per_pair':each,'best_forced_pair':best_id,
                'missed_by_all':missed,'better_post_ls':better,'normal_budget_witness':intervention,
                'actionable':actionable,'distinct_completed_routes':len({stamp(v['kernel']['routes']) for v in each.values()}),
                'distinct_post_ls_routes':len({stamp(v['post_ls_routes']) for v in each.values()}),
                'post_ls_range':[min(v['post_ls'] for v in each.values()),max(v['post_ls'] for v in each.values())]})
            print(json.dumps({'instance':case['instance_id'],'pairs':len(ids),'best':best_id,
                  'reference_post_ls':deployed['reference']['post_ls'],'diagnostic_best_post_ls':best['post_ls'],
                  'actionable':actionable,'distinct_routes':all_rows[-1]['distinct_completed_routes']}),flush=True)
    diagnostic_results=[v for row in all_rows for v in row['per_pair'].values()]
    result={'states':all_rows,'revision_gate':any(r['actionable'] for r in all_rows),
            'seconds':perf_counter()-started,'enumerated_pairs':len(diagnostic_results),
            'enumeration_logical_requests':sum(r['kernel']['price_requests'] for r in diagnostic_results),
            'enumeration_actual_computations':sum(r['repair_work']['prices']['insertion_computations'] for r in diagnostic_results),
            'enumeration_ls_seconds':sum(r['ls_seconds'] for r in diagnostic_results),
            'scope':'Offline selected-state candidate-pool diagnostic only. Not equal-budget deployment, global optimum, or universal improvement ceiling.'}
    save(out/'diagnostic.json',result)


def diagnostic_evidence(row):
    """Read saved branches only; no extra evaluations or outcome-based selection."""
    values = list(row['per_pair'].values())
    comps = [c for value in values for c in value['kernel']['completions']]
    reference = row['deployed_policies']['reference']
    features = reference['kernel']['features']
    bottleneck = max(range(len(features['routes'])), key=lambda i: features['route_costs'][i])
    unchanged = lambda routes: routes[bottleneck] == features['routes'][bottleneck]
    return {
        'source_ref': row['case']['source_ref'], 'instance_id': row['case']['instance_id'],
        'band': row['case']['band'], 'pairs': len(values),
        'reference_repair': reference['repair'], 'reference_post_ls': reference['post_ls'],
        'best_forced_pair': row['best_forced_pair'],
        'best_forced_post_ls': min(v['post_ls'] for v in values),
        'post_ls_range': row['post_ls_range'], 'actionable': row['actionable'],
        'distinct_returned_routes': row['distinct_completed_routes'],
        'distinct_returned_post_ls_routes': row['distinct_post_ls_routes'],
        'retained_leaves': len(comps),
        'distinct_retained_partials': len({stamp(c['branch']['routes']) for c in comps}),
        'distinct_tail_completed_routes': len({stamp(c['routes']) for c in comps}),
        'partial_bottleneck_robot_zero_based': bottleneck,
        'partial_bottleneck_route': features['routes'][bottleneck],
        'partial_bottleneck_cost': features['route_costs'][bottleneck],
        'retained_leaves_preserving_bottleneck_route': sum(unchanged(c['branch']['routes']) for c in comps),
        'tail_completions_preserving_bottleneck_route': sum(unchanged(c['routes']) for c in comps),
        'retained_partial_makespans': sorted({c['branch']['makespan'] for c in comps}),
        'tail_makespan_range': [min(c['makespan'] for c in comps),max(c['makespan'] for c in comps)],
        'greedy_incumbent': reference['kernel']['greedy_makespan'],
    }


def summarize(out):
    """Reproducible artifact-only analysis after the single frozen recheck."""
    fresh(out/'analysis.json')
    base, config = read(out/'base_config.json'), read(out/'config.json')
    equivalence, diagnosis = read(out/'equivalence.json'), read(out/'diagnostic.json')
    deployment = read(out/'recheck/deployment.json')
    source = ROOT/config['source_run']
    groups = ['manual','reference','generation_1','generation_2']
    assert equivalence['all_equal'] and len(deployment) == 64
    assert len(diagnosis['states']) <= config['diagnostic_max_states'] <= 3
    for row in deployment:
        assert row['valid'] and not row['fallbacks']
        executor = row['executor']
        if executor:
            assert executor['closed'] and executor['calls'] == len(row['kernel_records']) > 0
            assert all(s['status'] == 'success' for s in executor['samples'])
        stats = row['work']['prices']
        assert stats['insertion_requests'] == stats['insertion_cache_hits'] + stats['insertion_computations']
        for kernel in row['kernel_records']:
            assert not kernel['strategy_error']
            assert kernel['price_requests'] == kernel['pricing_work']['insertion_requests'] <= base['search']['max_prices']
            assert kernel['expansions'] <= base['search']['max_expansions']
            assert len(kernel['selected_pairs']) <= base['search']['max_pairs']

    totals, paired_rows = [], []
    for mode in ('iterations','time'):
        rows = [r for r in deployment if r['mode'] == mode]
        for instance in dict.fromkeys(r['instance_id'] for r in rows):
            manual = {r['seed']:r['makespan'] for r in rows if r['instance_id']==instance and r['group']=='manual'}
            for label in groups:
                values = sorted((r for r in rows if r['instance_id']==instance and r['group']==label),key=lambda r:r['seed'])
                value = mean(r['makespan'] for r in values)
                baseline = mean(manual.values())
                paired_rows.append({'mode':mode,'instance_id':instance,'group':label,'mean':value,
                    'delta_vs_manual':value-baseline,'delta_percent_vs_manual':100*(value/baseline-1),
                    'seeds':[{'seed':r['seed'],'makespan':r['makespan'],
                              'delta_vs_manual':r['makespan']-manual[r['seed']]} for r in values]})
        for label in groups:
            rr = [r for r in rows if r['group']==label]
            kernels = [k for r in rr for k in r['kernel_records']]
            samples = [s for r in rr if r['executor'] for s in r['executor']['samples']]
            steady = [s['wall_time_ms'] for r in rr if r['executor'] for s in r['executor']['samples'][1:]]
            members = {}
            for r in rr:
                for name,stats in r['repair_stats'].items():
                    aggregate = members.setdefault(name,Counter())
                    aggregate.update(stats)
            totals.append({'mode':mode,'group':label,'mean':mean(r['makespan'] for r in rr),
                'iterations':sum(r['iterations'] for r in rr),'kernel_calls':len(kernels),
                'solve_seconds':sum(r['solve_seconds'] for r in rr),
                'end_to_end_seconds':sum(r['end_to_end_seconds'] for r in rr),
                'max_overshoot_seconds':max(r['overshoot_seconds'] for r in rr),
                'prices':{k:sum(r['work']['prices'][k] for r in rr) for k in (
                    'insertion_requests','insertion_cache_hits','insertion_computations','table_builds',
                    'table_build_seconds','insertion_compute_seconds')},
                'dp':{k:sum(r['work']['dp'][k] for r in rr) for k in ('calls','cache_misses','compute_time_sec')},
                'loading_seconds':sum(r['executor']['loading_seconds'] for r in rr if r['executor']),
                'worker_startup_seconds':sum(s['startup_ms'] for s in samples)/1000,
                'validation_import_seconds':sum(s['validation_import_ms'] for s in samples)/1000,
                'mean_subsequent_call_ms':mean(steady) if steady else None,
                'max_kernel_logical_requests':max((k['price_requests'] for k in kernels),default=0),
                'choice_counts':choice_counts(kernels,base['search']['max_pairs']),
                'member_statistics':members})

    cache_comparison=[]
    for label in groups[1:]:
        rows=[r for r in equivalence['paired'] if r['label']==label]
        aggregate={mode:{k:sum(r[mode+'_work']['prices'][k] for r in rows) for k in (
            'insertion_requests','insertion_computations','insertion_cache_hits',
            'table_builds','table_build_seconds','insertion_compute_seconds')} for mode in ('uncached','cached')}
        assert aggregate['uncached']['insertion_requests']==aggregate['cached']['insertion_requests']
        cache_comparison.append({'group':label,**aggregate})
    changes=[{'parent':r['parent'],'child':r['child'],
              'counts':{k:sum(c[k] for c in r['cases']) for k in r['cases'][0] if k!='case_index'}}
             for r in equivalence['behavior_changes']]
    evidence=[diagnostic_evidence(row) for row in diagnosis['states']]
    for row in diagnosis['states']:
        assert len(row['per_pair']) <= config['diagnostic_max_pairs_per_state'] <= 15
        for value in row['per_pair'].values():
            k=value['kernel']
            assert len({t for pair in k['features']['pairs'] for t in pair['tasks']}) <= config['diagnostic_max_tasks'] <= 6
            assert len(k['selected_pairs']) == 1 and k['config']['max_pairs'] == 1
            assert k['price_requests'] <= base['search']['max_prices']
            assert k['expansions'] <= base['search']['max_expansions']
            assert {a:b for a,b in k['config'].items() if a!='max_pairs'} == {a:b for a,b in base['search'].items() if a!='max_pairs'}
    historical=[]
    old=read(out/'historical_choice_counts.json')
    for mode in ('iterations','time'):
        counts=Counter()
        for r in old:
            if r['mode']==mode:
                counts.update(r['counts'])
        historical.append({'mode':mode,'counts':dict(counts)})
    artifacts=[out/f for f in ('config.json','base_config.json','cases.json','diagnostic_states.json',
        'equivalence.json','historical_fixed_equivalence.json','diagnostic.json','recheck/deployment.json')]
    sources=[ROOT/f for f in ('src/mrta_rect_coverage/core/incremental_route.py',
        'src/mrta_rect_coverage/heuristics/bounded_repair_search.py',
        'src/mrta_rect_coverage/experiments/bounded_repair_strategy.py',
        'src/mrta_rect_coverage/experiments/bounded_pair_opportunity.py')]+list(policies(source).values())
    decisions={'model_requests':0,'input_tokens':0,'output_tokens':0,'new_candidates':0,
        'retained_generated':None,'actual_deployment':MANUAL,
        'stop_reason':'No diagnosed pair beats the existing reference after the same local search; no revision gate passed. Stop this pair-ranking lineage.',
        'next_priority':'Test a single state-based call/skip decision for optional two-step search, using bottleneck reachability and predicted benefit versus cost; no instance-name rules.',
        'limitation':'Observed retained actions cannot change the binding route in the six-task-pool example; most completed routes differ but do not improve makespan. This does not prove that another pool, pruned branch or tail rule cannot help.'}
    assert not diagnosis['revision_gate'], 'An actionable gate requires completing revisions before this no-call decision.'
    results={'scope':'Development regression and bounded selected-state diagnosis only; no significance or global optimality claim.',
        'pricing_comparison':cache_comparison,'behavior_changes':changes,'historical_choice_counts':historical,
        'deployment_totals':totals,'per_instance':paired_rows,'diagnostic_evidence':evidence,
        'offline_diagnostic_cost':{k:v for k,v in diagnosis.items() if k!='states'},
        'checks':{'paired_equivalence_cases':len(equivalence['paired']),
            'new_fixed_12_iteration_controls':len(equivalence['fixed_trajectory']),
            'saved_fixed_40_iteration_matches':len(read(out/'historical_fixed_equivalence.json')),
            'deployment_solves':len(deployment),'all_valid':True,'all_workers_closed':True,
            'all_budgets_and_logical_counts_valid':True},
        'decision':decisions,
        'source_sha256_text_utf8':{str(p.relative_to(ROOT)):digest(p) for p in sources},
        'artifact_sha256_bytes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}}
    save(out/'analysis.json',results)
    print(json.dumps({'checks':results['checks'],'decision':decisions,'time_means':
        {r['group']:r['mean'] for r in totals if r['mode']=='time'}},ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=ROOT/'configs/bounded_pair_opportunity.json')
    parser.add_argument('--stage',choices=('prepare','verify','recheck','diagnose','summarize'),required=True)
    args=parser.parse_args()
    out=ROOT/read(args.config)['output_dir']
    if args.stage=='prepare':
        prepare(args.config)
    else:
        {'verify':verify,'recheck':recheck,'diagnose':diagnostic,'summarize':summarize}[args.stage](out)


if __name__=='__main__':
    main()
