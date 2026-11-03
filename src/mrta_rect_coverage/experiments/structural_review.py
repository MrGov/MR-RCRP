"""Frozen-source, corrected-kernel review of structural-population run_001."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import random
import shutil
from time import perf_counter

from .structural_population import ROOT, Study, read, save, sha

SOURCE=ROOT/'outputs/structural_population/run_001'
DEST=ROOT/'outputs/structural_population/review_002'


def pair_set(value):
    if value is None:
        return None
    if len(value)==2 and all(isinstance(item,str) for item in value):
        return [list(value)]
    return [list(pair) for pair in value]


def implementation_hashes():
    files=[Path(__file__),ROOT/'src/mrta_rect_coverage/experiments/structural_population.py',
        ROOT/'src/mrta_rect_coverage/heuristics/structural_search.py',
        ROOT/'src/mrta_rect_coverage/heuristics/alns_solver.py',
        ROOT/'src/mrta_rect_coverage/heuristics/search_budget.py',
        ROOT/'src/mrta_rect_coverage/llm/operator_evolution/candidate_security.py',
        ROOT/'src/mrta_rect_coverage/llm/operator_evolution/persistent_candidate_execution.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in files}


def make_study():
    cfg=read(SOURCE/'config.json')
    cfg['output_dir']=str(DEST.relative_to(ROOT)).replace('\\','/')
    if DEST.exists():
        if not (DEST/'config.json').exists():
            raise FileExistsError(f'incomplete review directory without config: {DEST}')
        study=Study(DEST/'config.json',resume=True)
        frozen=read(DEST/'frozen_sources.json')
        if any(sha(ROOT/v['source'])!=v['sha256_bytes'] for v in frozen.values()):
            raise ValueError('candidate source changed after review freeze')
        save(DEST/'source_hashes.json',implementation_hashes())
        protocol=read(DEST/'protocol.json')
        protocol['groups']=['manual','manual_pairs','reference','single_r4_c2','multi_r4_replace',
            'r1_c3','r2_c3','r3_c3_suspect_duplicate','r1_join','r1_replace','r1_cross',
            'r3_join','r3_replace','r3_cross','multi_without_r4_c2','multi_without_r2_c2','single_r2_c2']
        protocol['regression_only_reserved_groups']=['manual','manual_pairs','reference','single_r4_c2',
            'multi_r4_replace','multi_without_r2_c2']
        save(DEST/'protocol.json',protocol)
        return study
    DEST.mkdir(parents=True)
    entries=read(SOURCE/'entries.json')
    archive=read(SOURCE/'archive.json')
    # Freeze exact candidate bytes before any corrected evaluation.
    identities={name:{'source':a['source'],'sha256_bytes':sha(ROOT/a['source']),
                       'normalized_hash':a['hash'],'parents':a['parents'],
                       'fingerprint':a.get('fingerprint'),'duplicate_of':a.get('duplicate_of')}
                for name,a in archive.items()}
    save(DEST/'config.json',cfg); save(DEST/'entries.json',entries)
    save(DEST/'archive.json',archive); save(DEST/'frozen_sources.json',identities)
    save(DEST/'protocol.json',{
        'source_run':str(SOURCE.relative_to(ROOT)),
        'semantics':'Corrected shared deadline and price budget; disjoint per-phase timing. Every incomplete structural iteration aborts without acceptance/reward; existing complete current/best solution is retained.',
        'model_requests':0,
        'groups':['manual','manual_pairs','reference','single_r4_c2','multi_r4_replace',
                  'r1_c3','r2_c3','r3_c3_suspect_duplicate','r1_join','r1_replace','r1_cross',
                  'r3_join','r3_replace','r3_cross','multi_without_r4_c2','multi_without_r2_c2',
                  'single_r2_c2'],
        'regression_only_reserved_groups':['manual','manual_pairs','reference','single_r4_c2','multi_r4_replace',
                                           'multi_without_r2_c2'],
        'reference_executor_check':'One BASE/R2/T20 seed-23 matched full solve plus fixed-state decision equality check.',
        'not_replayed':['r2 compositions (neither member nor lineage contains r1_c3)',
                        'r4 single/multi lineages (neither lineage contains r1_c3)',
                        'all unaffected candidate groups']})
    save(DEST/'source_hashes.json',implementation_hashes())
    study=object.__new__(Study)
    study.cfg=cfg; study.out=DEST; study.entries=entries; study.archive=archive
    baseline=ROOT/'outputs/structural_population/review_001'
    for role in ('development','reserved'):
        (DEST/role).mkdir(parents=True,exist_ok=True)
        for label in ('manual','manual_pairs'):
            shutil.copy2(baseline/role/f'{label}.json',DEST/role/f'{label}.json')
    study.ledger=[]; study.groups=read(baseline/'groups.json'); study.rng=random.Random(1103)
    return study


def main():
    study=make_study()
    start=perf_counter()
    manual=study.evaluate('manual',None)
    manual_pairs=study.evaluate('manual_pairs',[list(p) for p in __import__(
        'mrta_rect_coverage.heuristics.structural_search',fromlist=['MANUAL_PAIRS']).MANUAL_PAIRS])
    pairs={
        'reference':list(SOURCE.joinpath('freeze.json') and read(SOURCE/'freeze.json')['selected']['pairs']),
        'single_r4_c2':read(SOURCE/'freeze.json')['single']['pairs'],
        'multi_r4_replace':read(SOURCE/'freeze.json')['multi_proposal']['pairs'],
        'r1_c3':pair_set(study.archive['r1_c3']['pair']),
        'r2_c3':pair_set(study.archive['r2_c3']['pair']),
        'r3_c3_suspect_duplicate':pair_set(study.archive['r3_c3']['pair']),
        'r1_join':read(SOURCE/'development/r1_join.json')['pairs'],
        'r1_replace':read(SOURCE/'development/r1_replace.json')['pairs'],
        'r1_cross':read(SOURCE/'development/r1_cross.json')['pairs'],
        'r3_join':read(SOURCE/'development/r3_join.json')['pairs'],
        'r3_replace':read(SOURCE/'development/r3_replace.json')['pairs'],
        'r3_cross':read(SOURCE/'development/r3_cross.json')['pairs'],
    }
    for member in ('r4_c2','r2_c2'):
        pairs[f'multi_without_{member}']=[pair for pair in pairs['multi_r4_replace']
                                           if all(not operator.startswith(member+':') for operator in pair)]
    pairs['single_r2_c2']=[list(pair) for pair in __import__(
        'mrta_rect_coverage.heuristics.structural_search',fromlist=['MANUAL_PAIRS']).MANUAL_PAIRS]
    pairs['single_r2_c2'].append(study.archive['r2_c2']['pair'])
    groups={}
    for label,pairset in pairs.items():
        groups[label]=study.evaluate(label,pairset)
    reserved_groups={label:study.evaluate(label,pairs.get(label),role='reserved')
                     for label in ('manual','manual_pairs','reference','single_r4_c2','multi_r4_replace',
                                   'multi_without_r2_c2')}
    # Complete-solve executor comparison on one predeclared small instance/seed.
    entry=next(e for e in study.entries['development'] if e['instance_id']=='development/BASE/R2_T20_0')
    matched={}
    for executor in (False,True):
        name='reference_executor' if executor else 'reference_native'
        matched[name]=study.run_one(entry,23,pairs['reference'],reference_executor=executor)
        save(DEST/f'{name}.json',matched[name])
    source=Path(study.archive['reference']['source'])
    ref_source=ROOT/source
    matched['fixed_state_decisions']=fixed_state_check(study,ref_source)
    save(DEST/'executor_check.json',matched)
    report=build_report(study,groups,manual,manual_pairs,reserved_groups,matched,start)
    save(DEST/'analysis.json',report)
    print(json.dumps({'output':str(DEST),'groups':{k:{'mean_improvement_percent':v.get('mean_relative',0)*100,
        'valid':v['valid']} for k,v in groups.items()},'analysis':report['paired_summary'],
        'executor':report['executor_summary'],'wall_seconds':perf_counter()-start},ensure_ascii=True),flush=True)


def fixed_state_check(study,path):
    from ..core.instance_loader import load_instance
    from ..heuristics.alns_solver import ALNSConfig
    from ..heuristics.structural_search import PairPortfolioSolver,StructuralKernel,StructuralExecutor,reference_step
    entry=next(e for e in study.entries['development'] if e['instance_id']=='development/BASE/R2_T20_0')
    instance=load_instance(ROOT/'data/structural_benchmark_v1'/entry['path'])
    s=PairPortfolioSolver(instance,config=ALNSConfig.enhanced(iterations=1,random_seed=23))
    k=StructuralKernel(s,reference_step)
    ev=s.solution_evaluator.evaluate(s.initial_solution)
    destroy=k.destroy_features(s.initial_solution,ev,4)
    ref_destroy=reference_step(deepcopy(destroy),random.Random(701))
    digest=sha(path)
    with __import__('mrta_rect_coverage.heuristics.structural_search',fromlist=['StructuralExecutor']).StructuralExecutor(
            path,expected_hash=digest) as executor:
        exec_destroy=executor(deepcopy(destroy),random.Random(701))
        partial,_=s._remove_tasks(s.initial_solution,ref_destroy)
        partial_eval=s.solution_evaluator.evaluate_partial(partial)
        # Same repair branch and same policy RNG isolate action selection.
        probe=StructuralKernel(s,reference_step); probe._new_record()
        branch={'routes':deepcopy(partial.routes),'costs':list(partial_eval.per_robot_costs),
                'remaining':list(ref_destroy)}
        options=[]
        for task in branch['remaining']:
            for robot,route in enumerate(branch['routes']):
                vals=s.insertion_pricer.insertion_costs(route,task)
                for pos,cost in enumerate(vals):
                    costs=list(branch['costs']); costs[robot]=cost
                    options.append({'task':task,'robot':robot,'position':pos,'cost':cost,
                        'makespan':max(costs),'total':sum(costs),
                        'bottleneck':max(range(len(costs)),key=lambda r:costs[r])})
        features={'phase':'repair','branches':[{**branch,'options':options}],
                  'depth':0,'width':3,'prices_remaining':study.cfg['price_cap']}
        ref_repair=reference_step(deepcopy(features),random.Random(702))
        exec_repair=executor(deepcopy(features),random.Random(702))
        exec_stats=deepcopy(executor.samples)
    return {'instance_id':entry['instance_id'],'seed':23,
        'destroy_actions_equal':ref_destroy==exec_destroy,
        'repair_actions_equal':ref_repair==exec_repair,
        'reference_destroy':ref_destroy,'executor_destroy':exec_destroy,
        'reference_repair':ref_repair,'executor_repair':exec_repair,
        'executor_samples':exec_stats,'same_features_and_rng':True}


def build_report(study,groups,manual,manual_pairs,reserved_groups,matched,start):
    def details_for(data,baseline):
        base={r['instance_id']+'#'+str(r['seed']):r for r in baseline['rows']}
        details=[]
        for row in data['rows']:
            b=base[row['instance_id']+'#'+str(row['seed'])]
            details.append({'instance_id':row['instance_id'],'seed':row['seed'],
                'makespan':row.get('makespan'),'manual_makespan':b.get('makespan'),
                'improvement_percent':(100*(b['makespan']-row['makespan'])/b['makespan']) if row.get('makespan') is not None else None,
                'iterations_completed':row.get('iterations'),'iterations_attempted':row.get('iterations_attempted'),
                'first_legal_complete_seconds':row.get('first_legal_complete_seconds'),
                'first_final_best_seconds':row.get('first_final_best_seconds'),
                'end_to_end_seconds':row['end_to_end_seconds'],'overshoot_seconds':row['overshoot_seconds'],
                'incomplete_iterations':row.get('incomplete_iterations',0),
                'pair_stats':row.get('pair_stats',{}),'structural_work':row.get('structural_work',{}),
                'executors':row.get('executors',{}),'error':row['error'],'valid':row['valid']})
        return details
    rows={'manual':details_for(manual,manual),'manual_pairs':details_for(manual_pairs,manual),
          **{label:details_for(data,manual) for label,data in groups.items()}}
    reserved_rows={f'reserved_{label}':details_for(data,reserved_groups['manual'])
                   for label,data in reserved_groups.items()}
    def add_pair_control(details,control):
        by_key={r['instance_id']+'#'+str(r['seed']):r for r in control['rows']}
        for row in details:
            baseline=by_key[row['instance_id']+'#'+str(row['seed'])]
            row['pair_control_makespan']=baseline['makespan']
            row['improvement_vs_pair_control_percent']=(
                100*(baseline['makespan']-row['makespan'])/baseline['makespan']
                if row.get('makespan') is not None else None)
    for label,details in rows.items():
        if label not in ('manual','manual_pairs'): add_pair_control(details,manual_pairs)
    reserved_control=reserved_groups['manual_pairs']
    for label,details in reserved_rows.items():
        if label not in ('reserved_manual','reserved_manual_pairs'):
            add_pair_control(details,reserved_control)
    def summarize(data):
        summary={}
        for label,details in data.items():
            vals=[x['improvement_percent'] for x in details if x['improvement_percent'] is not None]
            summary[label]={'rows':len(details),'mean_improvement_percent':sum(vals)/len(vals) if vals else None,
                'wins':sum(v>1e-9 for v in vals),'losses':sum(v< -1e-9 for v in vals),
                'ties':sum(abs(v)<=1e-9 for v in vals),
                'mean_improvement_vs_pair_control_percent':(
                    sum(x['improvement_vs_pair_control_percent'] for x in details
                        if x.get('improvement_vs_pair_control_percent') is not None)/
                    max(1,sum(x.get('improvement_vs_pair_control_percent') is not None for x in details))),
                'pair_control_wins':sum(x.get('improvement_vs_pair_control_percent',0)>1e-9 for x in details),
                'pair_control_losses':sum(x.get('improvement_vs_pair_control_percent',0)<-1e-9 for x in details),
                'incomplete_iterations':sum(x['incomplete_iterations'] for x in details),
                'max_end_to_end_seconds':max((x['end_to_end_seconds'] for x in details),default=0.)}
        return summary
    summaries=summarize(rows); reserved_summaries=summarize(reserved_rows)
    native,isolated=matched['reference_native'],matched['reference_executor']
    group_labels=read(DEST/'protocol.json')['groups']
    evaluation_wall=sum(read(DEST/'development'/f'{label}.json').get('wall_seconds',0.)
                        for label in group_labels)
    evaluation_wall+=sum(read(DEST/'reserved'/f'{label}.json').get('wall_seconds',0.)
                         for label in reserved_groups)
    evaluation_wall+=native['end_to_end_seconds']+isolated['end_to_end_seconds']
    scheduled_budget=sum(row['budget_seconds'] for label in group_labels
        for row in read(DEST/'development'/f'{label}.json')['rows'])
    scheduled_budget+=sum(row['budget_seconds'] for label in reserved_groups
        for row in read(DEST/'reserved'/f'{label}.json')['rows'])
    return {'version':'corrected_kernel_review_002','source_run':'run_001','model_requests':0,
        'historical_provenance':{'r1_c3_old_record':{
            'request_8_prompt_included_old_r1_c3_group':True,
            'request_8_parent':'r1_c3',
            'r1_population_member_rounds':[1,2,3,4],
            'r1_composition_groups':['r1_join','r1_replace','r1_cross'],
            'r3_composition_groups':['r3_join','r3_replace','r3_cross'],
            'direct_descendant':'r2_c3','grandchild_duplicate':'r3_c3',
            'final_single_or_multi_lineage_affected':False,
            'freeze_selected_affected':False,
            'evidence':'Frozen lineage parents, round population records, request/08 prompt feedback, request/08 parent source, and saved group member lists.'}},
        'dedup':{'r2_c3_source_hash':study.archive['r2_c3']['hash'],
            'r3_c3_source_hash':study.archive['r3_c3']['hash'],
            'same_source':study.archive['r2_c3']['hash']==study.archive['r3_c3']['hash'],
            'same_local_fingerprint':study.archive['r2_c3'].get('fingerprint')==study.archive['r3_c3'].get('fingerprint'),
            'both_full_evaluated':all(x in groups for x in ('r2_c3','r3_c3_suspect_duplicate'))},
        'rows':rows,'paired_summary':summaries,'reserved_rows':reserved_rows,
        'reserved_paired_summary':reserved_summaries,
        'executor_summary':{'native':{k:native.get(k) for k in ('makespan','iterations','end_to_end_seconds','structural_work')},
            'isolated':{k:isolated.get(k) for k in ('makespan','iterations','end_to_end_seconds','structural_work')},
            'fixed_state_decisions':matched['fixed_state_decisions']},
        'offline_evaluation_wall_seconds':evaluation_wall,
        'scheduled_online_budget_seconds':scheduled_budget,
        'conclusion_limits':'Two prior-view development instances are regression data, not independent validation.'}


if __name__=='__main__': main()
