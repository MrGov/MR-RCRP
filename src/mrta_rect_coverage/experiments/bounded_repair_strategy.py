"""Small development experiment for isolated pair ranking over exact repair search.

Stages are explicit so the same frozen capability evidence feeds true revisions.
Each artifact name is single-use. No locked input, provider retry, or full subset scan.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict, replace
import difflib
import hashlib
import inspect
import json
from pathlib import Path
import random
from statistics import mean
from time import perf_counter

from .operator_gap_revision import ROOT, save, digest
from .operator_portfolio_evolution import _sample_trace
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..heuristics.bounded_repair_search import BoundedRepairSearch, SearchBudget, StrategyExecutor, reference_rank_pairs
from ..heuristics.priced_local_search import run_priced_local_search
from ..llm.operator_evolution.langchain_provider import LangChainOperatorEvolutionProvider
from ..llm.runtime.client_factory import build_langchain_chat_model
from ..llm.runtime.config import load_from_env

DATA = ROOT / 'data/structural_benchmark_v1'
MANUAL = ['greedy_insertion', 'regret_k_insertion', 'bottleneck_balancing_insertion']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def fresh(path):
    if path.exists():
        raise FileExistsError(f'Refusing to overwrite {path}')


def instance(entry):
    if entry['split'] != 'development':
        raise ValueError('development only')
    path = DATA / entry['path']
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
        raise ValueError('manifest identity mismatch')
    return load_instance(path)


def make_solver(entry, seed=23, **kw):
    args = dict(iterations=40, random_seed=seed, priced_local_search=True,
                capture_operator_states=True, segment_length=4, operator_minimum_uses=1)
    args.update(kw)
    return ALNSSolver(instance(entry), config=ALNSConfig.enhanced(**args))


def trace(evaluation):
    return [{'tasks': r.route_task_ids, 'cost': r.total_cost, 'states': r.chosen_state_ids,
             'entry': r.entry_points, 'exit': r.exit_points, 'transitions': r.transition_costs}
            for r in evaluation.route_evaluations]


def snapshot(s):
    return {'dp': s.route_dp.statistics(), 'prices': s.insertion_pricer.statistics()}


def work(before, after):
    return {group: {k: after[group][k]-before[group][k] for k in keys}
            for group, keys in [('dp', ('calls', 'cache_misses')),
                                ('prices', ('table_builds', 'insertion_prices', 'price_cache_hits'))]}


def paired(out, config, label, policy_path=None):
    target = out / f'paired_{label}.json'
    fresh(target)
    cases, entries = read(out/'cases.json'), read(out/'entries.json')
    lookup = {e['instance_id']: e for e in entries}
    result = {'label': label, 'source_hash': digest(policy_path) if policy_path else None,
              'cases': [], 'valid': True}
    started = perf_counter()
    with ExitStack() as stack:
        policy = stack.enter_context(StrategyExecutor(policy_path,
            expected_hash=read(policy_path.parent/'lineage.json')['hash'])) if policy_path else None
        for index, case in enumerate(cases):
            s = make_solver(lookup[case['instance_id']], case['seed'], iterations=1)
            partial = MultiRobotSolution(deepcopy(case['partial_routes']))
            p_eval = s.solution_evaluator.evaluate_partial(partial)
            kernel = None
            before, call = snapshot(s), perf_counter()
            if label in MANUAL:
                repaired = s.repair_ops[label](partial, list(case['removed_tasks']), p_eval)
            elif label == 'trace':
                repaired = MultiRobotSolution(deepcopy(case['baseline_repaired_routes']))
            else:
                kernel = BoundedRepairSearch(s, ranker=policy or reference_rank_pairs,
                                             budget=SearchBudget(**config['search']))
                repaired = kernel(partial, case['removed_tasks'], p_eval)
            repair_seconds, repair_work = perf_counter()-call, work(before, snapshot(s))
            raw_eval = s.solution_evaluator.evaluate(repaired)
            before, call = snapshot(s), perf_counter()
            refined, refined_eval = run_priced_local_search(deepcopy(repaired), s.solution_evaluator,
                                                           s.insertion_pricer, max_iterations=1)
            ls_seconds, ls_work = perf_counter()-call, work(before, snapshot(s))
            valid = s._is_valid_full_solution(refined) and (not kernel or not kernel.records[-1]['strategy_error'])
            result['valid'] &= valid
            row = {'case_id': case['case_id'], 'index': index, 'instance_id': case['instance_id'],
                   'band': case['band'], 'repair': raw_eval.makespan, 'post_ls': refined_eval.makespan,
                   'repair_seconds': repair_seconds, 'ls_seconds': ls_seconds,
                   'repair_work': repair_work, 'ls_work': ls_work, 'valid': bool(valid),
                   'partial_trace': trace(p_eval), 'repair_trace': trace(raw_eval), 'post_ls_trace': trace(refined_eval),
                   'kernel': kernel.records[-1] if kernel else None}
            # Fixed early representatives only. Extra passes are explanatory and never used for selection.
            if index in config['extra_ls_case_indices']:
                before, call = snapshot(s), perf_counter()
                _, extra = run_priced_local_search(deepcopy(repaired), s.solution_evaluator,
                    s.insertion_pricer, max_iterations=config['extra_ls_iterations'])
                row['extra_ls'] = {'makespan': extra.makespan, 'seconds': perf_counter()-call,
                                   'work': work(before,snapshot(s)), 'iterations_cap': config['extra_ls_iterations']}
            result['cases'].append(row)
    result['executor'] = policy.statistics() if policy else None
    result['wall_seconds'] = perf_counter()-started
    result['summary'] = {key: mean(r[key] for r in result['cases']) for key in
                         ('repair','post_ls','repair_seconds','ls_seconds')}
    save(target, result)
    print(json.dumps({'label': label, 'valid': result['valid'], **result['summary']}), flush=True)
    return result


def capability(config_path):
    config = read(config_path)
    out = ROOT / config['output_dir']
    out.mkdir(parents=True, exist_ok=False)
    save(out/'config.json', config)
    # Record design and code identities before observing outcomes.
    files = [Path(__file__), ROOT/'src/mrta_rect_coverage/heuristics/bounded_repair_search.py',
             ROOT/'src/mrta_rect_coverage/heuristics/alns_solver.py']
    save(out/'source_hashes.json', {str(p.relative_to(ROOT)): digest(p) for p in files})
    cases = deepcopy(read(ROOT/config['replay'])['cases'])
    requested = list(dict.fromkeys([c['instance_id'] for c in cases]+config['added_instances']))
    if len(config['added_instances']) > 2:
        raise ValueError('at most two additional inputs')
    entries = [e for e in read(DATA/'manifest.json')['entries'] if e['instance_id'] in requested]
    if len(entries) != len(requested) or any(e['split']!='development' for e in entries):
        raise ValueError('invalid development selection')
    save(out/'entries.json', entries)
    collection = []
    for identity in config['added_instances']:
        entry = next(e for e in entries if e['instance_id']==identity)
        s = make_solver(entry, config['trace_seed'], iterations=config['trace_iterations'],
                        destroy_fraction=config['trace_removed']/entry['n_tasks'])
        baseline = s.solve()
        collection.append({'instance_id': identity, 'config': asdict(s.config),
                           'history': baseline.iteration_history, 'seconds': baseline.runtime_seconds})
        for band, row in _sample_trace(baseline.iteration_history, config['stagnation_patience']):
            cases.append({'instance_id': identity, 'band': band, 'partial_routes': row['partial_routes'],
                          'removed_tasks': row['removed_tasks'], 'baseline_repaired_routes': row['repaired_routes'],
                          'baseline_repair_operator': row['repair'], 'trace_seed': config['trace_seed'],
                          'trace_iteration': row['iteration'], 'seed': config['trace_seed']+row['iteration']})
    for case in cases:
        case['case_id'] = hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest()[:16]
    save(out/'collection.json', collection)
    save(out/'cases.json', cases)
    finish_capability(out)


def finish_capability(out):
    config = read(out/'config.json')
    fresh(out/'capability.json')
    rows = {label: read(out/f'paired_{label}.json') if (out/f'paired_{label}.json').exists()
            else paired(out, config, label) for label in ['trace', *MANUAL, 'reference']}
    ref = rows['reference']['cases']
    gains = {metric: [min(rows[m]['cases'][i][metric] for m in MANUAL)-r[metric] for i,r in enumerate(ref)]
             for metric in ('repair','post_ls')}
    gate = {'gains_over_best_manual_per_state': gains,
            'useful_action_space': any(v>1e-9 for vs in gains.values() for v in vs),
            'scope': '12 predeclared consumed/development states; manual envelope is an offline diagnostic, not deployed oracle'}
    save(out/'capability.json', gate)
    print(json.dumps(gate), flush=True)


def feedback(out, parent_label):
    cases = read(out/'cases.json')
    labels = [*MANUAL, 'reference'] + (['generation_1'] if parent_label=='generation_1' else [])
    evaluations = {label: read(out/f'paired_{label}.json') for label in labels}
    parent = evaluations[parent_label]
    raw_gain = [min(evaluations[m]['cases'][i]['repair'] for m in MANUAL)-r['repair'] for i,r in enumerate(parent['cases'])]
    ls_gain = [min(evaluations[m]['cases'][i]['post_ls'] for m in MANUAL)-r['post_ls'] for i,r in enumerate(parent['cases'])]
    # Keep one negative, one positive, and two predeclared larger-state examples.
    selected = list(dict.fromkeys([min(range(len(cases)),key=lambda i:(ls_gain[i],i)),
                                  max(range(len(cases)),key=lambda i:(raw_gain[i],-i)), 6,9]))
    if parent_label != 'reference':
        # First largest set difference, fixed before looking at the child's result.
        ref_cases = evaluations['reference']['cases']
        changed = max(range(len(cases)), key=lambda i:(
            len(set(parent['cases'][i]['kernel']['selected_pairs']) ^
                set(ref_cases[i]['kernel']['selected_pairs'])), -i))
        if changed not in selected:
            selected.append(changed)
    snippets = []
    for i in selected:
        row, case = parent['cases'][i], cases[i]
        k = row['kernel']
        manual = min(MANUAL, key=lambda m: evaluations[m]['cases'][i]['post_ls'])
        snippets.append({'case_id': case['case_id'], 'index': i, 'instance': case['instance_id'],
            'removed': case['removed_tasks'], 'features': k['features'],
            'selected_pairs': k['selected_pairs'], 'repair': row['repair'], 'post_ls': row['post_ls'],
            'manual_best_post_ls': evaluations[manual]['cases'][i]['post_ls'],
            'greedy': k['greedy_makespan'],
            'completed_branches': [{key: x[key] for key in ('branch','makespan','costs')} for x in k['completions']],
            'joint_branch_table': [{key:x[key] for key in ('pair','order','first_rank','robots','positions','costs','makespan')} for x in k['joint_branches']],
            'actual_state_chains': {'partial':row['partial_trace'], 'repair':row['repair_trace']},
            'evidence_ref': f'paired_{parent_label}.json#/cases/{i}',
            'note': 'Only expanded branches have known joint outcomes. Unexpanded pairs are unmeasured; no oracle targets.'})
    return {'current_deployment': {'manual_repairs': MANUAL, 'generated': []},
            'case_selection_rule': 'worst post-LS vs manual envelope; best raw vs manual; fixed first added state of each larger instance; in revision also first largest pair-set change vs reference; de-duplicate',
            'overall': [{'label':lab, 'repair':[r['repair'] for r in ev['cases']],
                         'post_ls':[r['post_ls'] for r in ev['cases']],
                         'mean_repair_seconds':ev['summary']['repair_seconds'],
                         'selected_pairs':[r['kernel']['selected_pairs'] if r['kernel'] else None for r in ev['cases']],
                         'completed_outcomes':[[{'pair':x['branch']['pair'],'makespan':x['makespan']} for x in r['kernel']['completions']] if r['kernel'] else None for r in ev['cases']],
                         'price_requests':[r['kernel']['price_requests'] if r['kernel'] else r['repair_work']['prices']['insertion_prices'] for r in ev['cases']]}
                        for lab,ev in evaluations.items()], 'cases': snippets,
            'limits': 'Development only; no independent data. Post-LS uses one identical pass. Current deployed pool remains manual pending matched short search.'}


def prompt_for(out, config, parent_label, parent_source):
    info = feedback(out, parent_label)
    contract = '''Implement def rank_pairs(features, rng) -> list[str], a permutation of ALL features["pairs"][i]["id"].
One batched call per repair. Only rank task pairs; DO NOT return routes, task IDs, a solver, or a pricing implementation.
Pure Python with math as the only permitted optional import. Do not mutate imported state, use IO, inspect runtime, or hardcode instance/task IDs. No task identifier may be treated as a geometric feature. Use IDs solely for lookup/tie breaking. Bounded arithmetic/list logic (<=150 ms after import).
Feature schema: pairs=[{id,tasks:[a,b],regret_sum,same_best_robot,same_best_slot,center_distance}]; tasks has STRING task-ID keys, with best/top_slots/best_by_robot entries {robot,position,cost,makespan,total}, regret, center. These are exact SINGLE insertion prices on the original partial solution, not joint estimates. routes, route_costs, budget, prices_remaining are shared context.
Host sorts all available first insertion slots by (makespan,total,robot,position), keeps 3, then prices second insertions against each ACTUAL new route and keeps 2. Both task orders, any robot/slot, depth exactly 2. It keeps two distinct leaves per pair by exact partial makespan/total, completes remaining tasks by the existing exact greedy repair, and returns the best of those completions and its common greedy incumbent. It expands at most two pairs selected by your ranking; 36 materialized branch expansions and 4096 exact insertion requests INCLUDING feature calculation, greedy incumbent and all tail completions. Up to six tasks enter pair pool, chosen by singleton regret then ID. Identical cap and features for reference/LLM.
Your only decision is allocating the two pair expansions. Hypothesize which joint interactions are missed by singleton-regret ranking (e.g. competing slots versus alternative-robot slack), using actual results below. Do not assume same slot or proximity implies a true joint benefit. Do not change the host kernel or LS.
Return ONE JSON object {"name":..., "description":"specific falsifiable revision hypothesis", "code":"complete Python source"}. Keep implementation compact but meaningful; no fixed-instance memorization.
'''
    prompt = contract + '\nFrozen budget: ' + json.dumps(config['search']) + '\nActual parent source:\n' + parent_source
    prompt += '\nActual paired feedback (full raw traces remain at stable refs):\n' + json.dumps(info,ensure_ascii=False,separators=(',',':'))
    if parent_label != 'reference':
        prompt += '\nRevision instruction: compare the actual parent to the reference. Distinguish changed ordering from a changed top-two SET and from a changed completed repair. If two expansions repeatedly lead to the same completion, hypothesize a concrete adaptive second-pair allocation that may recover useful coverage without discarding the useful first pair. This is a hypothesis, not evidence that any untested pair wins. Preserve observed positive cases and acknowledge failures; do not merely perturb coefficients or random seeds. The kernel and budgets cannot change.'
    return prompt, info


def request_generation(out, round_id):
    config = read(out/'config.json')
    if not (round_id in (1,2) and round_id <= config['max_rounds'] and config['max_requests'] <= 6):
        raise ValueError('outside authorized batch')
    if not read(out/'capability.json')['useful_action_space']:
        raise ValueError('reference action-space gate failed; no provider call')
    parent_label = 'reference' if round_id==1 else 'generation_1'
    if round_id==2 and not read(out/'paired_generation_1.json')['valid']:
        raise ValueError('invalid parent: needs explicit engineering repair, not algorithm revision')
    parent_path = out/'reference.py' if round_id==1 else out/'request_01/candidate.py'
    if round_id==1:
        fresh(parent_path)
        parent_path.write_text(inspect.getsource(reference_rank_pairs).replace('reference_rank_pairs','rank_pairs'),encoding='utf-8')
    parent_source = parent_path.read_text(encoding='utf-8')
    prompt, info = prompt_for(out, config, parent_label, parent_source)
    folder = out/f'request_{round_id:02d}'
    folder.mkdir(exist_ok=False)
    save(folder/'feedback.json', info)
    (folder/'prompt.txt').write_text(prompt,encoding='utf-8')
    ledger = read(out/'requests.json') if (out/'requests.json').exists() else []
    if len(ledger) >= min(config['max_requests'],6):
        raise ValueError('hard actual-request budget exhausted')
    runtime = replace(load_from_env(), max_retries=0, temperature=None, max_output_tokens=config['max_output_tokens'])
    if runtime.provider not in ('langchain_openai_compatible', 'langchain'):
        raise ValueError('expected existing configured real provider')
    provider = LangChainOperatorEvolutionProvider(chat_model=build_langchain_chat_model(runtime),
                                                   requested_temperature=None)
    provider._raw_dir = folder
    row = {'request':len(ledger)+1, 'round':round_id, 'parent_label':parent_label,
           'parent_hash':digest(parent_path), 'model':runtime.model, 'provider':runtime.provider,
           'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
           'prompt_chars':len(prompt), 'prompt_bytes':len(prompt.encode()),
           'max_output_tokens':runtime.max_output_tokens, 'max_retries':0, 'status':'started'}
    ledger.append(row)
    save(out/'requests.json',ledger)  # charge before actual request, failures included
    started = perf_counter()
    try:
        drafts = provider.revise_operator_candidates(prompt,{},n=1,operator_type='pair_strategy',round_id=round_id)
        row.update(status='success' if drafts else 'parse_failure',metadata=provider.last_call_metadata)
    except Exception as exc:
        row.update(status='provider_failure',error_type=type(exc).__name__,status_code=getattr(exc,'status_code',None))
        drafts = []
    row['seconds'] = perf_counter()-started
    save(out/'requests.json',ledger)
    if drafts:
        draft = drafts[0]
        (folder/'candidate.py').write_text(draft.code,encoding='utf-8')
        (folder/'parent.diff').write_text(''.join(difflib.unified_diff(parent_source.splitlines(True),draft.code.splitlines(True),fromfile=parent_label,tofile=f'generation_{round_id}')),encoding='utf-8')
        save(folder/'lineage.json',{'parent_hash':digest(parent_path),'hash':digest(folder/'candidate.py'),
                                   'parent_evaluation':f'paired_{parent_label}.json', 'hypothesis':draft.description,
                                   'request':row['request'], 'source':'real_provider'})
    print(json.dumps(row),flush=True)


def deploy(out):
    config, entries = read(out/'config.json'), read(out/'entries.json')
    fresh(out/'deployment.json')
    groups = ['manual', 'reference'] + [f'generation_{i}' for i in (1,2)
        if (out/f'paired_generation_{i}.json').exists() and read(out/f'paired_generation_{i}.json')['valid']]
    # No addition subsets: a single new kernel member competes alongside the same manual pool.
    rows = []
    for mode in ('iterations','time'):
        for entry in entries:
            for seed in config['deployment_seeds']:
                for label in groups:
                    started = perf_counter()
                    kwargs = (dict(iterations=config['deployment_iterations'],max_runtime_seconds=None) if mode=='iterations'
                              else dict(iterations=None,max_runtime_seconds=config['deployment_seconds'],capture_operator_states=False))
                    s = make_solver(entry,seed,**kwargs)
                    with ExitStack() as stack:
                        policy = None
                        if label.startswith('generation_'):
                            i = int(label[-1])
                            policy_path = out/f'request_{i:02d}/candidate.py'
                            policy = stack.enter_context(StrategyExecutor(policy_path,
                                expected_hash=read(policy_path.parent/'lineage.json')['hash']))
                        kernel = None
                        if label != 'manual':
                            kernel = BoundedRepairSearch(s, ranker=policy or reference_rank_pairs,budget=SearchBudget(**config['search']))
                            s.register_bounded_repair(kernel,name='bounded_'+label)
                        weights = dict(s.repair_weights)
                        result = s.solve()
                    stats = {name:{'calls':r.uses,'shared_reward':r.score,
                        'accepted':sum(h['repair']==name and h['accepted'] for h in result.iteration_history),
                        'best_improvements':sum(h['repair']==name and h['score_raw']>=8 for h in result.iteration_history),
                        'seconds':result.operator_time_stats['repair'][name][0]}
                        for name,r in result.operator_usage_stats['repair'].items()}
                    rows.append({'mode':mode,'group':label,'instance_id':entry['instance_id'],'seed':seed,
                        'makespan':result.best_evaluation.makespan,'solve_seconds':result.runtime_seconds,
                        'end_to_end_seconds':perf_counter()-started,'iterations':result.iterations_completed,
                        'overshoot_seconds':max(0.,result.runtime_seconds-config['deployment_seconds']) if mode=='time' else 0.,
                        'best_routes':result.best_solution.routes,'valid':s._is_valid_full_solution(result.best_solution),
                        'fallbacks':result.fallback_events,'config':asdict(s.config),'initial_repair_weights':weights,
                        'repair_stats':stats,'work':snapshot(s),'kernel_records':kernel.records if kernel else [],
                        'executor':policy.statistics() if policy else None,
                        'history':result.iteration_history})
                    print(json.dumps({k:rows[-1][k] for k in ('mode','group','instance_id','seed','makespan','iterations')}),flush=True)
        save(out/f'deployment_{mode}.json',rows[-len(entries)*len(config['deployment_seeds'])*len(groups):])
    save(out/'deployment.json',rows)
    summary = {mode:{label:mean(r['makespan'] for r in rows if r['mode']==mode and r['group']==label)
                     for label in groups} for mode in ('iterations','time')}
    eligible = [lab for lab in groups if lab.startswith('generation_') and
        all(r['valid'] and not r['fallbacks'] and r['executor']['calls']>0 and
            not any(k['strategy_error'] for k in r['kernel_records']) for r in rows if r['group']==lab) and
        summary['time'][lab] <= min(summary['time']['manual'],summary['time']['reference'])-1]
    selected = min(eligible,key=lambda lab:summary['time'][lab]) if eligible else None
    save(out/'decision.json',{'means':summary,'retained_generated':selected,'manual_pool':MANUAL,
         'stop_reason':'two evaluated generations complete; no additional generation authorized in this run',
         'selection_rule':config['selection_rule']})
    print(json.dumps(summary),flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=ROOT/'configs/bounded_repair_search.json')
    parser.add_argument('--stage',choices=('capability','capability-evaluate','request','evaluate','deploy'),required=True)
    parser.add_argument('--round',type=int,default=1)
    args = parser.parse_args()
    out = ROOT/read(args.config)['output_dir']
    if args.stage=='capability':
        capability(args.config)
    elif args.stage=='capability-evaluate':
        finish_capability(out)
    elif args.stage=='request':
        request_generation(out,args.round)
    elif args.stage=='evaluate':
        paired(out,read(out/'config.json'),f'generation_{args.round}',out/f'request_{args.round:02d}/candidate.py')
    else:
        deploy(out)


if __name__=='__main__':
    main()
