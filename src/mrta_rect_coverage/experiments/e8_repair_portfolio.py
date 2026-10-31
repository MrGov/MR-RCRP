"""Small historical repair portfolio; unchanged B1 independent roulette and DP."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean
import subprocess
from time import perf_counter

from .e3_alns import ROOT, INSTANCES, SEEDS, write_json
from .e5_destroy_repair import D_NAME, R_NAME, digest, read, load_choice
from .e6_pair_selection import config_for, make_solver, _registered_proxy
from .e7_cooperative_evolution import SELECTION, load_inputs
from .e1_real_llm_pilot import compute_exact_dp_behavior
from .e2_c1_pilot import _write_csv
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..heuristics.alns_solver import ALNSSolver
from ..llm.operator_evolution.candidate_loader import load_and_validate_candidate
from ..llm.operator_evolution.evaluator import evaluate_paired_repair_candidates

E7 = ROOT/'outputs/e7_cooperative_evolution'
E5 = ROOT/'outputs/e5_llm_destroy_repair'
AUX_NAME = 'e8_aux_repair'
# Retain exact greedy and regret insertion; replace the other balancing variant.
# This slot is fixed before any E8 evaluation, never chosen from final results.
REPLACE_SLOT = 'bottleneck_balancing_insertion'
METHODS = ('V1','AUX','PORT')


def discover_candidates():
    """Only recorded real-provider sources with matching raw-response code."""
    raw = {}
    roots = [ROOT/'outputs'/p for p in ('e2_c1_pilot/evolution','e4a_decision_feedback',
                                      'e4b_geometry_feedback','e7_cooperative_evolution')]
    for root in roots:
        for path in sorted(root.rglob('*_raw.txt')):
            text=path.read_text(encoding='utf-8').strip()
            clean=re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
            try:
                items=json.loads(clean)
            except json.JSONDecodeError:
                items=[]
            if isinstance(items,list):
                for item in items:
                    if isinstance(item,dict) and isinstance(item.get('code'),str):
                        key=item['code'].replace('\r\n','\n').strip()
                        raw.setdefault(key,[]).append(dict(path=str(path),description=item.get('description','')))
    records=[]
    for mode in ('L0','F1','F2'):
        path=ROOT/f'outputs/e2_c1_pilot/evolution/{mode}/candidate_metrics.jsonl'
        for row in map(json.loads,path.read_text(encoding='utf-8').splitlines()):
            records.append((f'E2-R/{mode}',path,row))
    for phase,label in (('e4a_decision_feedback','E4-A'),('e4b_geometry_feedback','E4-B')):
        path=ROOT/'outputs'/phase/'candidate_metrics.json'
        for mode,rows in read(path).items():
            for row in rows:
                records.append((f'{label}/{mode}',path,row))
    for row in read(E7/'generated_candidates.json'):
        records.append(('E7',E7/'generated_candidates.json',row))
    for label,path,key in (('E5/R*',E5/'selected_operators.json','repair'),
                           ('E7/parent',E7/'selected_operators.json','repair')):
        records.append((label,path,read(path)[key]))
    unique={}
    for alias,evidence,row in records:
        path=Path(row['source_path'])
        if not path.is_absolute():path=ROOT/path
        source=path.read_text(encoding='utf-8')
        h=hashlib.sha256(source.encode()).hexdigest()
        if h!=row['source_hash']:
            raise ValueError(f'historical hash mismatch: {path}')
        matches=raw.get(source.strip(),[])
        if not matches:
            raise ValueError(f'no matching real-provider raw source: {path}')
        identity=unique.setdefault(h,dict(source_hash=h,source_path=str(path.resolve()),
            operator_id=row['operator_id'],generation=row['generation'],aliases=[],raw_response_sources=[],
            description=row.get('description') or matches[0]['description'],historical_fixed=[]))
        if alias not in identity['aliases']:identity['aliases'].append(alias)
        identity['raw_response_sources']=sorted(set(identity['raw_response_sources'])|{m['path'] for m in matches})
        if 'avg_relative_improvement' in row:
            identity['historical_fixed'].append(dict(experiment=alias,source=str(evidence),
                avg_relative_improvement=row['avg_relative_improvement'],feasible=row.get('feasible_count'),
                trials=row.get('executed_count'),comparison='historical baseline and partials; not directly comparable across phases'))
        if alias=='E5/R*':identity['source_path']=str(path.resolve())
    return sorted(unique.values(),key=lambda c:c['source_hash'])


def structure_features(instance):
    """Intrinsic labels fixed independently of all algorithm outcomes."""
    n=instance.task_count
    hs=[max(1,math.ceil(t.height/instance.sweep_width)) for t in instance.tasks]
    vs=[max(1,math.ceil(t.width/instance.sweep_width)) for t in instance.tasks]
    ph=[h*t.width/instance.sweep_speed+(h-1)*instance.turning_time for t,h in zip(instance.tasks,hs)]
    pv=[v*t.height/instance.sweep_speed+(v-1)*instance.turning_time for t,v in zip(instance.tasks,vs)]
    centers=[((t.x_left+t.x_right)/2,(t.y_bottom+t.y_top)/2) for t in instance.tasks]
    pairs=[abs(a[0]-b[0])+abs(a[1]-b[1]) for i,a in enumerate(centers) for b in centers[i+1:]]
    work=mean(min(a,b) for a,b in zip(ph,pv))
    gap=mean(abs(a-b)/max(1e-12,min(a,b)) for a,b in zip(ph,pv))
    spread=mean(pairs) if pairs else 0.
    turnshare=mean(((h-1) if a<=b else (v-1))*instance.turning_time/max(1e-12,min(a,b)) for h,v,a,b in zip(hs,vs,ph,pv))
    return dict(instance=instance.name,tasks=n,robots=instance.robot_count,tasks_per_robot=n/instance.robot_count,
        scale='small' if n<=20 else 'medium' if n<=60 else 'large',
        load_label='high_load' if n/instance.robot_count>=12 else 'moderate_load',
        geometry_label='HV_sensitive' if gap>=.15 else 'HV_similar',
        travel_label='dispersed' if spread/instance.travel_speed>=work else 'processing_heavy',
        mean_pair_manhattan=spread,mean_depot_manhattan=mean(abs(x-instance.depot[0])+abs(y-instance.depot[1]) for x,y in centers),
        mean_H_sweeps=mean(hs),mean_V_sweeps=mean(vs),mean_min_processing=work,
        mean_relative_HV_gap=gap,mean_preferred_turning_share=turnshare)


def complementarity(parent, candidate):
    """Predeclared small-pilot screening, not a statistical reliability claim.

    Average gains cannot compensate for invalid execution. Require >=0.5% gain
    on two distinct instances of hard incumbents, gains on R* degraded cases,
    plus an observed loss elsewhere (a real crossover). Seeds share deterministic
    initial parents; they are never counted as independent supporting instances.
    """
    refs={t['input_id']:t for t in parent['trials']}
    valid=(len(candidate['trials'])==len(refs) and candidate['executed_count']==len(refs)
        and candidate['feasible_count']==len(refs) and all(t.get('feasible') for t in candidate['trials'])
        and {t['input_id'] for t in candidate['trials']}==set(refs))
    if not valid:return dict(eligible=False,reasons=['incomplete, unpaired or failed execution'])
    pairs=[(t,refs[t['input_id']]) for t in candidate['trials']]
    gains=[100*(1-a['candidate_makespan']/b['candidate_makespan']) for a,b in pairs]
    hard=[(a,b) for a,b in pairs if '/manual_B1_100_iterations/' in a['input_id']]
    by_instance={n:mean(100*(1-a['candidate_makespan']/b['candidate_makespan']) for a,b in hard if a['instance_id']==n)
                 for n in sorted({a['instance_id'] for a,b in hard})}
    weak=[(a,b) for a,b in hard if b['candidate_makespan']>b['parent_makespan']+1e-9]
    weak_gain=mean(100*(1-a['candidate_makespan']/b['candidate_makespan']) for a,b in weak) if weak else 0.
    runtime_limit=max(100.,10*parent['avg_runtime_ms'])
    reasons=[]
    if mean(gains)<-2:reasons.append('mean paired degradation exceeds 2%')
    if candidate['avg_runtime_ms']>runtime_limit:reasons.append('mean execution exceeds max(100ms,10x parent)')
    if sum(v>=.5 for v in by_instance.values())<2:reasons.append('fewer than two hard-parent instance gains >=0.5%')
    if weak_gain<1:reasons.append('R* degraded cases mean gain below 1%')
    if not any(g<-.1 for g in gains):reasons.append('no observed crossover loss vs R*')
    return dict(eligible=not reasons,reasons=reasons,paired_improvement_pct=mean(gains),
        weak_case_improvement_pct=weak_gain,hard_instance_improvements_pct=by_instance,
        supporting_instances=sum(v>=.5 for v in by_instance.values()),
        wtl=[sum(g>1e-9 for g in gains),sum(abs(g)<=1e-9 for g in gains),sum(g< -1e-9 for g in gains)],
        runtime_ms=candidate['avg_runtime_ms'],runtime_limit_ms=runtime_limit,
        caveat='exploratory evidence across three selection instances; no significance or generalization claim')


def portfolio_solver(instance,seed,selected,aux,method,*,iterations=None,budget=None,executor='original',config_overrides=None):
    """Fixed four repair slots; all calls still use existing loader/registry.

    V1 is constructed without mutation. AUX replaces only the generated main
    slot. PORT replaces the predeclared manual balancing slot with aux, keeping
    R* in its original slot. Insert order, initial weights and stats stay aligned.

    ``executor`` selects how generated operators are invoked: ``original`` keeps
    the historical per-call process spawn, ``warm`` reuses one resident worker
    per operator for the whole solve. The candidate code and every per-call
    check are unchanged in both modes; only the process lifetime differs.
    """
    if method not in METHODS:raise ValueError(method)
    choice=dict(selected)
    if method=='AUX':choice['repair']=aux
    solver=make_solver(instance,seed,choice,'V1',iterations=iterations,executor=executor,config_overrides=config_overrides)
    if budget is not None:solver.config.max_runtime_seconds=budget
    if method=='V1':return solver
    if method=='AUX':
        old=R_NAME
    else:
        old=REPLACE_SLOT
        # Remove just the declared slot and all of its existing selection stats.
        for group in (solver.repair_ops,solver.repair_weights,solver.operator_stats['repair'],solver.segment_stats['repair'],
                      solver.operator_time_stats['repair'],solver.segment_time_stats['repair']):
            group.pop(old)
        created=[]
        solver.register_development_repair(
            _registered_proxy(aux,'repair',executor,created),name=AUX_NAME)
        solver.extra_executors=list(getattr(solver,'extra_executors',[]))+created
        order=['greedy_insertion','regret_k_insertion',AUX_NAME,R_NAME]
        for group in (solver.repair_ops,solver.repair_weights,solver.operator_stats['repair'],solver.segment_stats['repair'],
                      solver.operator_time_stats['repair'],solver.segment_time_stats['repair']):
            ordered={name:group[name] for name in order}
            group.clear();group.update(ordered)
        return solver
    # AUX needs an aux wrapper/name; remove the temporary original registry name.
    for group in (solver.repair_ops,solver.repair_weights,solver.operator_stats['repair'],solver.segment_stats['repair'],
                  solver.operator_time_stats['repair'],solver.segment_time_stats['repair']):
        group.pop(old)
    solver.frozen_repair_ops.remove(old)
    created=[]
    solver.register_development_repair(
        _registered_proxy(aux,'repair',executor,created),name=AUX_NAME)
    solver.extra_executors=list(getattr(solver,'extra_executors',[]))+created
    return solver


def repair_usage(history,initial_makespan):
    """Conservative marginal selection statistics; local search is included.

    Exclude any fallback-affected iteration from accepted/best contribution.
    These counts describe outcomes after selecting a repair, not causal credit.
    """
    result={};previous=initial_makespan
    for h in history:
        row=result.setdefault(h['repair'],dict(uses=0,no_fallback_uses=0,accepted=0,global_best=0,fallback_affected_uses=0))
        row['uses']+=1
        if h['fallback_used']:row['fallback_affected_uses']+=1
        else:
            row['no_fallback_uses']+=1
            row['accepted']+=int(h['accepted'])
            row['global_best']+=int(h['best_makespan']<previous-1e-9)
        previous=h['best_makespan']
    return result


def setup(output):
    output.mkdir(parents=True,exist_ok=True)
    target=output/'experiment_config.json'
    if not target.exists():
        frozen=read(E7/'experiment_config.json')['frozen_hashes']
        for p,h in frozen.items():assert digest(p)==h
        pool=discover_candidates()
        inputs=read(E7/'pair_inputs.json')
        assert {r['instance_id'] for r in inputs}==set(SELECTION)
        assert not set(SELECTION)&set(INSTANCES)
        write_json(output/'candidate_pool.json',pool)
        write_json(output/'pair_inputs.json',inputs)
        write_json(output/'structure_manifest.json',[structure_features(load_instance(ROOT/'data'/f'{n}.txt')) for n in SELECTION+INSTANCES])
        write_json(target,dict(phase='E8',git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            selected=read(E5/'selected_operators.json'),selection_instances=SELECTION,comparison_instances=INSTANCES,seeds=SEEDS,
            selection_inputs='12 saved E7 D* partials: initial + manual B1 100-iteration incumbent, 3 instances x 2 seeds',
            source_E7_inputs=str(E7/'pair_inputs.json'),source_E7_inputs_hash=digest(E7/'pair_inputs.json'),
            structural_rules='small<=20,medium<=60,large>60; high load tasks/robots>=12; H/V sensitive mean relative processing gap>=0.15; dispersed mean centroid Manhattan/travel_speed>=mean min(H,V) processing',
            fixed_quality_rule='all 12 feasible; paired mean degradation <=2%; average candidate execution<=max(100ms,10x R*)',
            complementarity_rule='hard-incumbent gain>=0.5% on >=2 distinct instances; mean gain>=1% on R* degraded hard cases; observed crossover loss>0.1% elsewhere',
            shortlist_rule='up to two eligible candidates by weak-case gain, supporting instances, runtime then source hash; no mean-top-two selection',
            short_budget='max(5,0.1*task_count) seconds; 3 selection instances x 2 seeds; independent V1 framework',
            short_quality_rule='every short run feasible and no fallback; mean paired degradation<=3%; choose by frozen complementarity ranking among survivors',
            replacement_slot=REPLACE_SLOT,pools='V1:3manual+R*; AUX:3manual+R_aux; PORT:2manual+R*+R_aux; destroy pool always 3manual+D*',
            comparison_budget='task_count seconds',constructor='spatial_sort',methods=METHODS,
            frozen_hashes=frozen,candidate_hashes={c['source_path']:c['source_hash'] for c in pool},
            llm_calls=0,final_test_accessed=False,interpretation='development/exploratory; no post-comparison reselection, no oracle deployment; PORT member replacement is a confound',
            commands=[f'python -m mrta_rect_coverage.experiments.e8_repair_portfolio --stage {s}' for s in
                ('inventory','evaluate','screen','short','select','smoke','benchmark','analyze')]))
    config=read(target)
    for p,h in {**config['frozen_hashes'],**config['candidate_hashes']}.items():
        if digest(p)!=h:raise ValueError(f'frozen source changed: {p}')
    assert digest(config['source_E7_inputs'])==config['source_E7_inputs_hash']
    return config


def inventory(output):
    config=setup(output)
    pool=read(output/'candidate_pool.json')
    histories=historical_alns(pool)
    for c in pool:
        target=output/'validations'/f"{c['source_hash']}.json"
        if not target.exists():
            loaded=load_and_validate_candidate(path=Path(c['source_path']),operator_type='repair',round_id=c['generation'],
                source='langchain_openai_compatible',description=c['description'],allow_unsafe_candidate_execution=True)
            write_json(target,dict(validation=asdict(loaded.validation),eligible=loaded.callable_obj is not None))
        c['current_validation']=read(target)
        c['historical_alns']=histories.get(c['source_hash'],[])
    write_json(output/'candidate_inventory.json',pool)
    print(f"{len(pool)} unique real repairs; {sum(c['current_validation']['eligible'] for c in pool)} current loader-valid",flush=True)


def historical_alns(pool):
    result={c['source_hash']:[] for c in pool}
    e2=ROOT/'outputs/e2r_c1_pilot'
    choices=read(e2/'selected_operators.json')
    with (e2/'alns_results.csv').open(encoding='utf-8',newline='') as f:
        rows=list(csv.DictReader(f))
    for m in ('L0','L1','L2'):
        group=[r for r in rows if r['method']==m and r['feasible'].lower()=='true']
        if group:result[choices[m]['source_hash']].append(dict(experiment='E2-R/'+m,source=str(e2/'alns_results.csv'),runs=len(group),
            mean_makespan=mean(float(r['final_makespan']) for r in group),mean_runtime=mean(float(r['runtime_sec']) for r in group),
            settings='24 instances x 2 seeds, historical 200-iteration ALNS; not B1 time-budget comparable'))
    for phase,sub in (('e4a_decision_feedback','short_b1'),('e4b_geometry_feedback','b1_comparison')):
        o=ROOT/'outputs'/phase
        rows=read(o/sub/'results.json');selected=read(o/'selected_operators.json')
        for m,choice in selected.items():
            group=[r for r in rows if r['method']==m and r['feasible']]
            if group:result[choice['source_hash']].append(dict(experiment=phase+'/'+m,source=str(o/sub/'results.json'),runs=len(group),
                mean_makespan=mean(r['makespan'] for r in group),mean_runtime=mean(r['runtime_seconds'] for r in group),
                settings='historical E4 short B1; instance/time/Destroy settings differ from E8'))
    short=read(E7/'short_evaluations.json')
    for h,rows in short.items():
        result[h].append(dict(experiment='E7/short',source=str(E7/'short_evaluations.json'),runs=len(rows),
            mean_makespan=mean(r['makespan'] for r in rows),mean_runtime=mean(r['runtime_seconds'] for r in rows),
            settings='same selection instances, coupled E6 selection; differs from independent E8'))
    parent=read(E5/'selected_operators.json')['repair']['source_hash']
    e5_rows=read(E5/'results.json')
    for method in ('B1+R','B1+D+R'):
        group=[r for r in e5_rows if r['method']==method and r['feasible']]
        result[parent].append(dict(experiment='E5/'+method,source=str(E5/'results.json'),runs=len(group),
            mean_makespan=mean(r['makespan'] for r in group),mean_runtime=mean(r['runtime_seconds'] for r in group),
            settings='historical B1, task-count seconds; 3x4 for repair-only, 4x4 for destroy+repair; not reused as E8 results'))
    return result


def evaluate(output):
    config=setup(output)
    pool=read(output/'candidate_inventory.json')
    p=config['selected']['repair']['source_hash']
    order=sorted(pool,key=lambda c:(c['source_hash']!=p,c['source_hash']))
    rows={}
    for c in order:
        h=c['source_hash'];target=output/'fixed_evaluations'/f'{h}.json'
        if target.exists():row=read(target)
        elif not c['current_validation']['eligible']:
            row=dict(source_hash=h,executed_count=12,feasible_count=0,trials=[],failure='current loader validation failed')
            write_json(target,row)
        else:
            # Fresh evaluator/cache per candidate; reuse exact same saved D* outputs.
            inputs=load_inputs(output)
            loaded=load_choice(c,'repair')
            row=evaluate_paired_repair_candidates([loaded],inputs,timeout_ms=2000,
                behavior_callback=compute_exact_dp_behavior,reference_trials=rows[p]['trials'] if h!=p else None)[0]
            row.update(source_hash=h,aliases=c['aliases'])
            write_json(target,row)
        rows[h]=row
        print(f"{','.join(c['aliases'][:2])} {h[:10]}: feasible {row['feasible_count']}/{row['executed_count']}, mean={row.get('mean_makespan')}",flush=True)
    write_json(output/'fixed_evaluations.json',rows)


def screen(output):
    config=setup(output)
    pool=read(output/'candidate_inventory.json');rows=read(output/'fixed_evaluations.json')
    p=config['selected']['repair']['source_hash']
    analysis=[]
    for c in pool:
        if c['source_hash']==p:continue
        score=complementarity(rows[p],rows[c['source_hash']])
        analysis.append(dict(identity=c,**score))
    eligible=sorted([a for a in analysis if a['eligible']],key=lambda a:(-a['weak_case_improvement_pct'],-a['supporting_instances'],a['runtime_ms'],a['identity']['source_hash']))
    shortlist=[a['identity'] for a in eligible[:2]]
    write_json(output/'complementarity_analysis.json',analysis)
    write_json(output/'shortlist.json',shortlist)
    print('Eligible complementary repairs:',[(a['identity']['source_hash'][:10],a['weak_case_improvement_pct'],a['hard_instance_improvements_pct']) for a in eligible],flush=True)
    print('Frozen shortlist:',[c['source_hash'][:10] for c in shortlist],flush=True)


def run_one(output,name,seed,method,selected,aux,*,budget=None):
    target=output/'runs'/f'{name}_{method}_s{seed}.json'
    instance=load_instance(ROOT/'data'/f'{name}.txt')
    expected=config_for(instance,seed,'V1')
    if budget is not None:expected.max_runtime_seconds=budget
    identities=dict(destroy=selected['destroy'],main=selected['repair'] if method!='AUX' else None,
                    aux=aux if method!='V1' else None)
    if target.exists():
        saved=read(target)
        assert saved['config']==asdict(expected) and saved['identities']==identities
        return saved
    started=perf_counter()
    try:
        solver=portfolio_solver(instance,seed,selected,aux,method,budget=budget)
        setup_seconds=perf_counter()-started
        result=solver.solve()
        verified=solver.solution_evaluator.evaluate(result.best_solution)
        assert verified.makespan==result.best_evaluation.makespan
        usage=repair_usage(result.iteration_history,result.initial_makespan)
        zero=dict(uses=0,no_fallback_uses=0,accepted=0,global_best=0,fallback_affected_uses=0)
        main,aux_stats=usage.get(R_NAME,zero),usage.get(AUX_NAME,zero)
        row=dict(method=method,instance=name,seed=seed,feasible=True,
            status='fallback' if result.fallback_events else 'ok',makespan=verified.makespan,
            initial_makespan=result.initial_makespan,runtime_seconds=result.runtime_seconds,setup_seconds=setup_seconds,
            budget_seconds=expected.max_runtime_seconds,iterations=result.iterations_completed,
            route_dp_calls=result.route_dp_calls,route_dp_cache_misses=result.route_dp_cache_misses,
            fallback_count=len(result.fallback_events),main_uses=main['uses'],main_accepted=main['accepted'],main_global_best=main['global_best'],
            aux_uses=aux_stats['uses'],aux_accepted=aux_stats['accepted'],aux_global_best=aux_stats['global_best'],
            llm_destroy_uses=sum(h['destroy']==D_NAME for h in result.iteration_history),
            global_best_improvements=sum(b<a-1e-9 for a,b in zip([result.initial_makespan]+[h['best_makespan'] for h in result.iteration_history],
                                                                   [h['best_makespan'] for h in result.iteration_history])),
            **result.timing_breakdown_seconds)
        saved=dict(result=row,identities=identities,config=asdict(solver.config),initial_routes=solver.initial_solution.routes,
            best_routes=result.best_solution.routes,per_robot_costs=verified.per_robot_costs,history=result.iteration_history,
            repair_usage=usage,operator_stats={g:{n:asdict(rec) for n,rec in rs.items()} for g,rs in result.operator_usage_stats.items()},
            operator_pools=dict(destroy=list(solver.destroy_ops),repair=list(solver.repair_ops)),
            generated_operator_execution=result.generated_operator_execution,fallback_events=result.fallback_events,
            final_weights=dict(destroy=solver.destroy_weights,repair=solver.repair_weights))
        write_json(target,saved)
    except Exception as exc:
        write_json(target.with_suffix('.error.json'),dict(method=method,instance=name,seed=seed,feasible=False,
            status='error',error=f'{type(exc).__name__}: {exc}',wall_seconds=perf_counter()-started,identities=identities))
        raise
    print(f"{name} s{seed} {method}: M={row['makespan']:.1f}, {row['iterations']} iters, R*={row['main_uses']}, aux={row['aux_uses']}, fallback={row['fallback_count']}",flush=True)
    return saved


def short(output):
    config=setup(output)
    shortlist=read(output/'shortlist.json')
    all_rows={config['selected']['repair']['source_hash']:[]}
    all_rows.update({c['source_hash']:[] for c in shortlist})
    for name in SELECTION:
        instance=load_instance(ROOT/'data'/f'{name}.txt')
        for seed in SEEDS:
            conditions=[('V1',None)]+[(c['source_hash'],c) for c in shortlist]
            for label,c in (conditions if seed==0 else list(reversed(conditions))):
                saved=run_one(output/'selection'/label,name,seed,'V1' if c is None else 'AUX',
                    config['selected'],c,budget=max(5.,.1*instance.task_count))
                all_rows[c['source_hash'] if c else config['selected']['repair']['source_hash']].append(saved['result'])
    write_json(output/'short_evaluations.json',all_rows)


def select(output):
    config=setup(output)
    target=output/'selection_decision.json'
    if target.exists():
        print('Reuse frozen auxiliary decision; no reselection',flush=True);return
    shortlist=read(output/'shortlist.json');rows=read(output/'short_evaluations.json')
    p=config['selected']['repair']['source_hash'];base=rows[p]
    assert len(base)==6 and all(r['feasible'] and not r['fallback_count'] for r in base)
    diagnostics=[];survivors=[]
    for c in shortlist:
        group=rows[c['source_hash']]
        assert [(r['instance'],r['seed']) for r in group]==[(r['instance'],r['seed']) for r in base]
        improvement=mean(100*(1-a['makespan']/b['makespan']) for a,b in zip(group,base))
        eligible=all(r['feasible'] and not r['fallback_count'] for r in group) and improvement>=-3.
        diagnostics.append(dict(source_hash=c['source_hash'],short_paired_improvement_pct=improvement,
            feasible_runs=sum(r['feasible'] for r in group),fallbacks=sum(r['fallback_count'] for r in group),eligible=eligible))
        if eligible:survivors.append(c)
    aux=survivors[0] if survivors else None
    decision=dict(aux=aux,main=config['selected']['repair'],destroy=config['selected']['destroy'],
        diagnostics=diagnostics,short_ranking_not_used=True,shortlist_priority_preserved=True,
        selection_instances=SELECTION,comparison_instances=INSTANCES,replacement_slot=REPLACE_SLOT,
        rationale='eligible fixed-pair crossover + complements R* degraded incumbents; passes independent short-ALNS quality bound' if aux else
                  'no historical candidate passed both complementarity and full-ALNS quality checks; retain V1',
        real_generation_calls=0,final_results_seen=False)
    write_json(target,decision)
    write_json(output/'deployment_config.json',dict(decision=decision,methods=METHODS if aux else ('V1',),
        configs={m:asdict(config_for(load_instance(ROOT/'data/R2_T10_0.txt'),0,'V1')) for m in METHODS},
        registry_names=dict(main=R_NAME,aux=AUX_NAME,destroy=D_NAME),time_per_task=1.,
        selector='existing B1 independent roulette; existing segment rewards',pool_sizes=[4,4],
        member_change='PORT replaces manual bottleneck_balancing_insertion with R_aux; R* retained. AUX replaces R* with R_aux only.',
        caveat='fixed pool sizes control count, not member replacement effects; no pure causal complementarity attribution'))
    print('Frozen R_aux:',aux['source_hash'] if aux else None,'short diagnostics:',diagnostics,flush=True)


def smoke(output):
    config=setup(output);decision=read(output/'selection_decision.json');aux=decision['aux']
    if aux is None:
        write_json(output/'smoke.json',dict(portfolio_deployed=False,reason=decision['rationale']));return
    solver=portfolio_solver(load_instance(ROOT/'data/R2_T10_0.txt'),0,config['selected'],aux,'PORT',iterations=4)
    names=iter([R_NAME,AUX_NAME,R_NAME,AUX_NAME])
    solver._select_operators=lambda context:(D_NAME,next(names),'E8_integration_only')
    result=solver.solve()
    assert not result.fallback_events
    assert solver.solution_evaluator.evaluate(result.best_solution).makespan==result.best_evaluation.makespan
    usage=repair_usage(result.iteration_history,result.initial_makespan)
    assert usage[R_NAME]['no_fallback_uses']==usage[AUX_NAME]['no_fallback_uses']==2
    write_json(output/'smoke.json',dict(portfolio_deployed=True,feasible=True,usage=usage,
        history=result.iteration_history,generated_operator_execution=result.generated_operator_execution))
    print('PORT bounded integration: both repairs executed twice; feasible, no fallback',flush=True)


def benchmark(output):
    config=setup(output);decision=read(output/'selection_decision.json');aux=decision['aux']
    assert (output/'smoke.json').exists()
    methods=METHODS if aux else ('V1',)
    rows=[]
    for name in INSTANCES:
        for seed in SEEDS:
            for m in (methods if seed==0 else tuple(reversed(methods))):
                rows.append(run_one(output,name,seed,m,config['selected'],aux)['result'])
                write_json(output/'results.json',rows);_write_csv(output/'results.csv',rows)


def candidate_analysis(output):
    config=setup(output);pool=read(output/'candidate_inventory.json');rows=read(output/'fixed_evaluations.json')
    p=config['selected']['repair']['source_hash'];parent=rows[p]
    structures={r['instance']:r for r in read(output/'structure_manifest.json')}
    scores={r['identity']['source_hash']:r for r in read(output/'complementarity_analysis.json')}
    table=[];responses=[]
    for c in pool:
        h=c['source_hash'];r=rows[h]
        table.append(dict(identity=h[:12],aliases=';'.join(c['aliases']),source_path=c['source_path'],source_hash=h,
            description=c['description'],valid=c['current_validation']['eligible'],feasible=r['feasible_count'],trials=r['executed_count'],
            mean_makespan=r.get('mean_makespan'),mean_runtime_ms=r.get('avg_runtime_ms'),
            mean_trial_wall_seconds=mean(t['wall_seconds'] for t in r['trials']) if r['trials'] else None,
            paired_improvement_pct=scores[h].get('paired_improvement_pct') if h!=p else 0.,
            complementary=scores[h]['eligible'] if h!=p else 'main',
            historical_fixed=c['historical_fixed'],historical_alns=c['historical_alns']))
        for i,t in enumerate(r['trials']):
            if not t.get('feasible'):continue
            before=set(t['bottleneck_before']);after=set(t['bottleneck_after'])
            responses.append(dict(source_hash=h,input_id=t['input_id'],instance=t['instance_id'],seed=t['solver_seed'],
                parent_state='incumbent' if '/manual_B1_' in t['input_id'] else 'initial',
                scale=structures[t['instance_id']]['scale'],load_label=structures[t['instance_id']]['load_label'],
                geometry_label=structures[t['instance_id']]['geometry_label'],travel_label=structures[t['instance_id']]['travel_label'],
                makespan=t['candidate_makespan'],relative_improvement_vs_R_star=0. if h==p else t['relative_improvement'],
                new_bottleneck_robots=sorted(after-before),removed_task_moves=t['removed_task_moves'],
                parent_to_result_behavior=t['parent_to_candidate_behavior'],
                R_star_to_result_behavior='same repair' if h==p else t['exact_dp_behavior'],
                source=str(output/'fixed_evaluations'/f'{h}.json')+f'#/trials/{i}'))
    _write_csv(output/'candidate_table.csv',table);write_json(output/'candidate_table.json',table)
    write_json(output/'dp_response_analysis.json',responses)
    structured=[]
    for c in pool:
        h=c['source_hash']
        for n in SELECTION:
            subset=[r for r in responses if r['source_hash']==h and r['instance']==n]
            if not subset:continue
            structured.append(dict(source_hash=h,instance=n,**{k:structures[n][k] for k in
                ('scale','robots','tasks_per_robot','travel_label','geometry_label','mean_relative_HV_gap','mean_preferred_turning_share')},
                mean_makespan=mean(r['makespan'] for r in subset),paired_improvement_pct=mean(100*r['relative_improvement_vs_R_star'] for r in subset),
                mean_HV_switch=mean(r['parent_to_result_behavior']['hv_mode_switch_fraction'] for r in subset),
                mean_cascade_ratio=mean(r['parent_to_result_behavior']['dp_cascade_ratio'] for r in subset),
                mean_travel_change=mean(r['parent_to_result_behavior']['travel_change'] for r in subset)))
    _write_csv(output/'candidate_by_structure.csv',structured)
    return table,responses


def analyze(output):
    config=setup(output);decision=read(output/'selection_decision.json');aux=decision['aux']
    methods=METHODS if aux else ('V1',)
    saved=[read(output/'runs'/f'{n}_{m}_s{s}.json') for n in INSTANCES for s in SEEDS for m in methods]
    rows=[d['result'] for d in saved];index={(r['method'],r['instance'],r['seed']):r for r in rows}
    for n in INSTANCES:
        verifier=ALNSSolver(load_instance(ROOT/'data'/f'{n}.txt'),constructor='spatial_sort')
        for d in (d for d in saved if d['result']['instance']==n):
            r=d['result']
            assert r['feasible'] and verifier.solution_evaluator.evaluate(MultiRobotSolution(d['best_routes'])).makespan==r['makespan']
            assert d['initial_routes']==verifier.initial_solution.routes
            assert d['config']==asdict(config_for(verifier.instance,r['seed'],'V1'))
            assert len(d['operator_pools']['repair'])==len(d['operator_pools']['destroy'])==4
            assert d['repair_usage']==repair_usage(d['history'],r['initial_makespan'])
            assert len(d['history'])==r['iterations']
            assert all(b['best_makespan']<=a['best_makespan'] for a,b in zip(d['history'],d['history'][1:]))
    summary=[]
    fields=('makespan','runtime_seconds','iterations','route_dp_calls','route_dp_cache_misses','main_uses','aux_uses',
            'main_accepted','aux_accepted','main_global_best','aux_global_best','global_best_improvements','llm_destroy_uses')
    for m in methods:
        group=[r for r in rows if r['method']==m]
        out=dict(method=m,**{f'mean_{k}':mean(r[k] for r in group) for k in fields},
            fallback_count=sum(r['fallback_count'] for r in group),
            generated_repair_selection_fraction=sum(r['main_uses']+r['aux_uses'] for r in group)/sum(r['iterations'] for r in group))
        for base in methods:
            pairs=[(r,index[base,r['instance'],r['seed']]) for r in group]
            out[f'paired_improvement_vs_{base}_pct']=mean(100*(1-a['makespan']/b['makespan']) for a,b in pairs)
            out[f'wtl_vs_{base}']=[sum(a['makespan']<b['makespan'] for a,b in pairs),sum(a['makespan']==b['makespan'] for a,b in pairs),sum(a['makespan']>b['makespan'] for a,b in pairs)]
        summary.append(out)
    write_json(output/'summary.json',summary);_write_csv(output/'summary.csv',summary)
    features={r['instance']:r for r in read(output/'structure_manifest.json')}
    by_instance=[dict(instance=n,scale=features[n]['scale'],load=features[n]['load_label'],geometry=features[n]['geometry_label'],travel=features[n]['travel_label'],
        **{m:mean(r['makespan'] for r in rows if r['instance']==n and r['method']==m) for m in methods}) for n in INSTANCES]
    _write_csv(output/'per_instance_results.csv',by_instance)
    _write_csv(output/'repair_usage.csv',[dict(instance=d['result']['instance'],seed=d['result']['seed'],method=d['result']['method'],repair=name,**stats)
                                       for d in saved for name,stats in d['repair_usage'].items()])
    write_json(output/'verification_summary.json',dict(feasible_runs=len(rows),expected_runs=8*len(methods),
        fallback_count=sum(r['fallback_count'] for r in rows),full_solutions_independently_reevaluated=True,
        same_initial_routes_and_B1_config=True,same_pool_sizes=True,canonical_DP_metrics_reused=True,
        selection_comparison_disjoint=True,final_results_not_used_for_selection=True,llm_calls=0,
        frozen_hashes_verified=True,generated_execution_calls=sum(x['calls'] for d in saved for g in d['generated_operator_execution'].values() for x in g.values()),
        generated_execution_failures=sum(x['failures'] for d in saved for g in d['generated_operator_execution'].values() for x in g.values())))
    table,responses=candidate_analysis(output)
    plot(output,saved,methods)
    report(output,config,decision,summary,table,by_instance,responses)
    print(json.dumps(summary,indent=2),flush=True)


def plot(output,saved,methods):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    fig,axes=plt.subplots(2,4,figsize=(13,5.4))
    for j,n in enumerate(INSTANCES):
        for seed in SEEDS:
            ax=axes[seed,j]
            for m,color,style in zip(methods,('#0072B2','#D55E00','#009E73'),('-','--',':')):
                d=next(d for d in saved if d['result']['instance']==n and d['result']['seed']==seed and d['result']['method']==m)
                r=d['result'];h=d['history']
                ax.step([0]+[x['elapsed_seconds'] for x in h]+[r['runtime_seconds']],
                    [r['initial_makespan']]+[x['best_makespan'] for x in h]+[r['makespan']],where='post',color=color,linestyle=style,label=m)
            ax.set(title=f'{n}, seed {seed}',xlabel='Solve time (s)',ylabel='Best makespan');ax.grid(alpha=.15)
    axes[0,0].legend(frameon=False);fig.tight_layout()
    fig.savefig(output/'convergence.png',dpi=300);fig.savefig(output/'convergence.pdf');plt.close(fig)


def report(output,config,decision,summary,table,by_instance,responses):
    aux=decision['aux']
    lines=['# E8: Exact-DP-aware complementary repair portfolio','',
        'Development/exploratory pilot. No significance/generalization claim. No LLM requests. Frozen B1, DP and all historical candidate sources unchanged.','',
        'Algorithm: trace and deduplicate real historical sources -> validate bounded execution -> compare all candidates on identical D* partials -> screen measured incumbent crossovers/weak-case relief -> short independent ALNS quality check -> freeze <=1 auxiliary -> existing adaptive independent roulette over fixed 4 x 4 pools. No oracle is used at deployment.','',
        f"Selection instances: {', '.join(SELECTION)}. Comparison instances: {', '.join(INSTANCES)}; all seeds 0/1. The comparison instances have historical exposure and are not held out for confirmation.",'',
        'Labels use intrinsic size/load, centroid Manhattan spread and H/V sweep processing gaps. Numeric feature values and frozen thresholds are in structure_manifest.json and experiment_config.json; labels never use makespan outcomes.','',
        '## Candidate inventory and uniform evaluation','',
        '| Source aliases | Hash prefix | Uniform fixed makespan | Candidate execution ms | Paired gain vs R* | Complement screen |',
        '|---|---|---:|---:|---:|---|']
    for r in table:
        lines.append(f"| {r['aliases']} | {r['identity']} | {r['mean_makespan']:.3f} | {r['mean_runtime_ms']:.3f} | {(r['paired_improvement_pct'] or 0):+.3f}% | {r['complementary']} |")
    lines+=['','Full strategy descriptions, current validation, actual source paths/hashes, raw-response matches and historical results are in candidate_table.json/csv and candidate_inventory.json. Historical results use different partials, budgets, operator pools and selectors; only the new uniform fixed evaluation is ranked within this stage. Candidate execution time excludes subprocess startup; mean_trial_wall_seconds includes bounded invocation, evaluation and DP diagnostics. Complete ALNS timing includes process overhead.','',
        'Screening is intentionally distinct from mean ranking: all trials valid; mean paired degradation <=2%; execution <=max(100ms,10x R*); hard-parent gain >=0.5% on at least two distinct instances; mean gain >=1% on R* degraded cases; at least one loss elsewhere. These thresholds are pilot screening rules, not statistical evidence. Initial duplicate seeds are not independent support.','',
        'Shortlist priority is weak-case relief, breadth and overhead; up to two candidates undergo short independent B1 runs. Short-ALNS average paired degradation must be <=3%, with no feasibility failures or fallback. A slightly weaker standalone auxiliary can qualify because complementarity, rather than replacement superiority, is the question.','',
        f"Frozen decision: {decision['rationale']}."]
    if aux:
        lines += ['',f"R_aux: {','.join(aux['aliases'])}; `{aux['source_hash']}`.",
            f"R*: `{decision['main']['source_hash']}`. D*: `{decision['destroy']['source_hash']}`.",'',
            'The retained R* uses scaled area workload, Euclidean centroid insertion detours, large-first ordering and measured route slack. The auxiliary uses minimum H/V sweep processing time including turns, Manhattan centroid detours, dynamic regret task ordering and an updated projected bottleneck. These online estimates do not call or replace Route-DP. Canonical DP evidence is used offline to select and explain measured crossovers; state switching itself is never rewarded.','',
            f"V1: three manual repairs + R*. AUX: the same manual repairs + R_aux. PORT: keep R* and replace `{REPLACE_SLOT}` with R_aux. Every method has the original three manual destroys + D*, and 4 repair slots. V1 code/config/RNG selection behavior is unchanged.",'',
            'PORT changes a member, not only diversity. Equal pool counts do not isolate causal complementarity from removing the manual balancing repair or increasing generated-repair selection probability. Rewards and accepted/best counts are marginal selection outcomes that include local search. Fallback-affected iterations are excluded from credited accepted/best counts.','',
            '## Complete ALNS results','',
            '| Method | Mean makespan | Paired gain vs V1 | W/T/L vs V1 | Mean seconds | Mean iterations |',
            '|---|---:|---:|---|---:|---:|']
        for r in summary:
            lines.append(f"| {r['method']} | {r['mean_makespan']:.3f} | {r['paired_improvement_vs_V1_pct']:+.3f}% | {r['wtl_vs_V1']} | {r['mean_runtime_seconds']:.3f} | {r['mean_iterations']:.2f} |")
        port=next(r for r in summary if r['method']=='PORT')
        base=next(r for r in summary if r['method']=='V1')
        lines+=['','| Method | Mean DP calls | Mean cache misses | R* use/accept/best (totals) | Aux use/accept/best (totals) | LLM repair selection share |',
            '|---|---:|---:|---|---|---:|']
        for r in summary:
            main='/'.join(str(round(8*r['mean_main_'+k])) for k in ('uses','accepted','global_best'))
            auxiliary='/'.join(str(round(8*r['mean_aux_'+k])) for k in ('uses','accepted','global_best'))
            lines.append(f"| {r['method']} | {r['mean_route_dp_calls']:.1f} | {r['mean_route_dp_cache_misses']:.1f} | {main} | {auxiliary} | {100*r['generated_repair_selection_fraction']:.2f}% |")
        lines+=['',f"PORT vs AUX: paired gain {port['paired_improvement_vs_AUX_pct']:+.3f}%, W/T/L {port['wtl_vs_AUX']}.",
            'Positive paired rates average all 8 matched instance x seed relative changes; they are not ratios of overall means. Actual time may exceed the budget because stopping is at iteration boundaries. All fallbacks/errors remain in saved runs.','',
            '| Instance | Intrinsic labels | V1 | AUX | PORT |','|---|---|---:|---:|---:|']
        for r in by_instance:lines.append(f"| {r['instance']} | {r['scale']}, {r['load']}, {r['geometry']}, {r['travel']} | {r['V1']:.1f} | {r['AUX']:.1f} | {r['PORT']:.1f} |")
        lines+=['','## Measured DP interpretation','']
        h=aux['source_hash']
        parent_rows={r['input_id']:r for r in responses if r['source_hash']==decision['main']['source_hash']}
        comparison=[r for r in responses if r['source_hash']==h and r['parent_state']=='incumbent']
        for r in comparison:
            b=parent_rows[r['input_id']];dp=r['R_star_to_result_behavior']
            lines.append(f"- `{r['input_id']}`: R* {b['makespan']:.0f} -> aux {r['makespan']:.0f}; "
                f"travel {dp['travel_change']:+.0f}, coverage {dp['coverage_change']:+.0f}, turning {dp['turning_change']:+.0f}, "
                f"H/V switch {dp['hv_mode_switch_fraction']:.3f}, cascade ratio {dp['dp_cascade_ratio']:.3f}.")
        lines+=['','DP state changes occur in both gains and losses, and have no separate reward. Cost deltas above are totals across robots, not critical-route cost deltas. See full routes, removed-task destinations, bottleneck identities and canonical behavior in dp_response_analysis.json. Associations do not establish the cause of advantage. The three selection instances all fall below the predeclared H/V-sensitive threshold; this pilot cannot establish an H/V-specific structural advantage. Load, scale and travel labels also co-vary in this small sample.','',
            f"Observed PORT paired gain vs V1 is {port['paired_improvement_vs_V1_pct']:+.3f}% with W/T/L {port['wtl_vs_V1']}. "
            'Retain V1 as stable reference; this single development pilot does not justify a stable superiority claim or any post-result reselection. The portfolio is an optional reproducible configuration.','',
            f"PORT changes generated-repair selection share from {100*base['generated_repair_selection_fraction']:.2f}% to {100*port['generated_repair_selection_fraction']:.2f}%, "
            f"with {100*(1-port['mean_iterations']/base['mean_iterations']):.2f}% fewer mean iterations. "
            'The large dispersed comparison instance benefits, while the other three instance means degrade. The auxiliary alone beats the portfolio in six pairs and ties in two. Thus fixed-partial crossovers did not establish a useful ensemble under this time budget. More generated invocation overhead and loss of the manual balancing member are plausible explanations, not isolated causes. The next useful check would keep the manual replacement slot and invocation budget controlled in a small ablation; no new selector or generation was performed here.']
    lines += ['','## Reproduce','',
        'The existing environment is sufficient. Saved stages resume without generating or editing operators. A fresh output repeats evaluation; it still uses the frozen historical candidate pool and saved E7 partials.','',
        '```powershell',"$env:PYTHONPATH='src'",
        "foreach ($stage in @('inventory','evaluate','screen','short','select','smoke','benchmark','analyze')) {",
        "  & 'G:\\Anaconda\\envs\\mrta_env\\python.exe' -m mrta_rect_coverage.experiments.e8_repair_portfolio --stage $stage",
        "  if ($LASTEXITCODE -ne 0) { throw \"E8 failed at $stage\" }",'}','```','',
        'Complete solutions, config identities, route-DP calls/cache misses, operator use/accepted/best counts, execution timings and fallback records are retained per run. See summary.csv, repair_usage.csv and convergence.png/pdf. Stop after E8; no C3 or new selector was implemented.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    stages={'inventory':inventory,'evaluate':evaluate,'screen':screen,'short':short,'select':select,
            'smoke':smoke,'benchmark':benchmark,'analyze':analyze}
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=stages,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/e8_repair_portfolio')
    args=parser.parse_args();stages[args.stage](args.output.resolve())


if __name__=='__main__':main()
