"""Frozen V1/AUX on E10 structure: shared partials and complete B1 solves."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import math
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter

from .e3_alns import ROOT, write_json
from .e5_destroy_repair import read, digest, load_choice, D_NAME, R_NAME
from .e6_pair_selection import config_for
from .e8_repair_portfolio import portfolio_solver, repair_usage, AUX_NAME
from .e2_c1_pilot import _write_csv
from .e1_real_llm_pilot import compute_exact_dp_behavior
from .r3_diagnostics import objective_decomposition, state_chain_diff
from .dataset_protocol import STRUCTURAL_SCENARIOS
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..core.cost_matrix import CostMatrix
from ..core.state_generator import generate_all_states
from ..core.dp_evaluator import RouteDPEvaluator
from ..core.solution_evaluator import MultiRobotSolutionEvaluator
from ..heuristics.alns_solver import ALNSSolver
from ..llm.operator_evolution.evaluator import (DestroyBenchmarkCase, PairedRepairBenchmarkCase,
    prepare_paired_repair_cases,evaluate_paired_repair_candidates)

DATA=ROOT/'data/e10_structural_development'
METHODS=('V1','AUX')
SEEDS=(0,1)


def entries():return read(DATA/'manifest.json')['entries']


def load(entry):
    path=DATA/entry['file_path']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['file_hash']:raise ValueError('instance hash mismatch')
    instance=load_instance(path)
    instance.name=entry['instance_id']  # in-memory evidence identity; original TXT untouched
    return instance


def parent_routes(entry):
    base=next(e for e in entries() if e['scenario']=='BASE' and e['replicate_id']==entry['replicate_id'])
    solver=ALNSSolver(load(base),constructor='spatial_sort')
    return solver.initial_solution.routes


def evaluator_for(instance):
    states=generate_all_states(instance)
    return MultiRobotSolutionEvaluator(RouteDPEvaluator(CostMatrix(instance.depot,states,
        travel_speed=instance.travel_speed),states),instance=instance)


def snapshot(instance,solution,evaluation):
    """Persist evaluator-optimal state chains and canonical decompositions, not proxies."""
    task_by_id={t.task_id:t for t in instance.tasks};routes=[];states=[]
    for robot,route in enumerate(evaluation.route_evaluations):
        coverage=turning=0.
        for position,s in enumerate(route.chosen_states):
            t=task_by_id[s.task_id];length=t.width if s.sweep_mode.value=='H' else t.height
            coverage+=s.n_sweeps*length/instance.sweep_speed
            turning+=max(0,s.n_sweeps-1)*instance.turning_time
            states.append(dict(task_id=s.task_id,robot=robot,position=position,mode=s.sweep_mode.value,
                entry=s.entry_corner.value,exit=s.exit_corner.value,sweeps=s.n_sweeps,
                processing_time=s.processing_time,entry_point=list(s.entry_point),exit_point=list(s.exit_point)))
        travel=sum(route.transition_costs)
        assert abs(travel+coverage+turning-route.total_cost)<1e-6
        routes.append(dict(robot=robot,tasks=solution.routes[robot],total_cost=route.total_cost,
            travel_time=travel,coverage_traversal_time=coverage,turning_time=turning,
            turning_share=turning/route.total_cost if route.total_cost else 0.,transition_costs=route.transition_costs))
    bottlenecks=[r['robot'] for r in routes if abs(r['total_cost']-evaluation.makespan)<1e-8]
    return dict(makespan=evaluation.makespan,per_robot_costs=evaluation.per_robot_costs,routes=routes,states=states,
        bottlenecks=bottlenecks,critical_route=routes[bottlenecks[0]],objective=objective_decomposition(instance,evaluation),
        H_fraction=mean(s['mode']=='H' for s in states))


def service_proxy_residual(instance,snap,removed_tasks):
    """Observed chosen-state service minus the auxiliary's min(H,V) feature.

    This offline diagnostic is not a new DP metric, fitness or online evaluator.
    It does not include the center-to-corner insertion error or prove its cause.
    """
    tasks={t.task_id:t for t in instance.tasks}
    rows=[]
    critical=set(snap['bottlenecks'])
    for s in snap['states']:
        t=tasks[s['task_id']]
        nh=math.ceil(t.height/instance.sweep_width);nv=math.ceil(t.width/instance.sweep_width)
        ph=nh*t.width/instance.sweep_speed+(nh-1)*instance.turning_time
        pv=nv*t.height/instance.sweep_speed+(nv-1)*instance.turning_time
        rows.append(dict(task_id=t.task_id,robot=s['robot'],is_removed=t.task_id in removed_tasks,
            is_critical_route=s['robot'] in critical,processing_H=ph,processing_V=pv,
            min_processing=min(ph,pv),chosen_processing=s['processing_time'],
            service_residual=s['processing_time']-min(ph,pv)))
    return rows


def paired_summary(rows):
    index={}
    for r in rows:
        key=(r['method'],r['instance_id'],r['seed'])
        if key in index:raise ValueError('duplicate paired row')
        index[key]=r
    keys={(r['instance_id'],r['seed']) for r in rows}
    if any((m,i,s) not in index for i,s in keys for m in METHODS):raise ValueError('missing matched pair')
    pairs=[(index['AUX',i,s],index['V1',i,s]) for i,s in sorted(keys)]
    return dict(pairs=len(pairs),V1_mean=mean(b['makespan'] for a,b in pairs),AUX_mean=mean(a['makespan'] for a,b in pairs),
        paired_improvement_pct=mean(100*(1-a['makespan']/b['makespan']) for a,b in pairs),
        wtl=[sum(a['makespan']<b['makespan']-1e-8 for a,b in pairs),
             sum(abs(a['makespan']-b['makespan'])<=1e-8 for a,b in pairs),
             sum(a['makespan']>b['makespan']+1e-8 for a,b in pairs)])


def setup(output):
    output.mkdir(parents=True,exist_ok=True);target=output/'experiment_config.json'
    if not target.exists():
        decision=read(ROOT/'outputs/e8_repair_portfolio/selection_decision.json')
        frozen=[DATA/'manifest.json',DATA/'structure_features.csv']+[DATA/e['file_path'] for e in entries()]
        frozen += [ROOT/'src/mrta_rect_coverage'/p for p in ('heuristics/alns_solver.py','core/dp_evaluator.py',
            'core/state_generator.py','core/models.py','llm/operator_evolution/evaluator.py','llm/operator_evolution/candidate_execution.py',
            'experiments/e8_repair_portfolio.py','experiments/r3_diagnostics.py','experiments/e1_real_llm_pilot.py')]
        frozen += [Path(decision[k]['source_path']) for k in ('destroy','main','aux')]
        for key in ('destroy','main','aux'):assert digest(decision[key]['source_path'])==decision[key]['source_hash']
        write_json(target,dict(phase='E10-B',git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            decision=decision,entries=entries(),methods=METHODS,seeds=SEEDS,
            fixed_partial_plan='one D* removal per each of 21 instances, seed 0, remove_count=10; exact saved partial shared by R*/aux',
            fixed_parent='same BASE spatial_sort complete parent routes within each replicate, all seven scenarios',
            full_ALNS='84 serial runs; V1/AUX order alternates seed; original spatial_sort initial constructor; task_count seconds',
            canonical_behavior_source='E1 compute_exact_dp_behavior using R3 state_chain_diff and objective_decomposition unchanged',
            label_source='E10-A manifest, unchanged; all development, no confirmatory interpretation',
            frozen_hashes={str(p):digest(p) for p in frozen},llm_calls=0,post_result_tuning=False,
            commands=[f'python -m mrta_rect_coverage.experiments.e10b_structural_dp_analysis --stage {s}' for s in ('prepare','fixed','benchmark','analyze')]))
    config=read(target)
    for p,h in config['frozen_hashes'].items():
        if digest(p)!=h:raise ValueError(f'frozen input changed: {p}')
    return config


def prepare(output):
    config=setup(output);destroy=load_choice(config['decision']['destroy'],'destroy')
    for e in config['entries']:
        path=output/'inputs'/f"{e['instance_id']}.json"
        if path.exists():continue
        instance=load(e);ev=evaluator_for(instance);full=MultiRobotSolution(parent_routes(e));evaluation=ev.evaluate(full)
        case=DestroyBenchmarkCase(instance,ev,full,evaluation)
        paired=prepare_paired_repair_cases([case],fixed_destroy=destroy,seeds=[0],timeout_ms=2000,parent_label='common_BASE_parent')[0]
        write_json(path,dict(instance_id=e['instance_id'],entry=e,seed=0,input_id=paired.input_id,
            fixed_destroy_hash=paired.fixed_destroy_hash,destroy_runtime_ms=paired.destroy_runtime_ms,
            parent_routes=full.routes,partial_routes=paired.partial_solution.routes,removed_tasks=paired.removed_tasks,
            parent_snapshot=snapshot(instance,full,evaluation)))
    print('Saved 21 real D* partials and common-parent Exact-DP snapshots.',flush=True)


def input_case(output,e):
    r=read(output/'inputs'/f"{e['instance_id']}.json");instance=load(e);ev=evaluator_for(instance)
    full=MultiRobotSolution(r['parent_routes']);partial=MultiRobotSolution(r['partial_routes'])
    return PairedRepairBenchmarkCase(instance,ev,full,ev.evaluate(full),partial,ev.evaluate_partial(partial),
        r['removed_tasks'],r['seed'],r['fixed_destroy_hash'],r['destroy_runtime_ms'],r['input_id'])


def fixed(output):
    config=setup(output);d=config['decision']
    loaded={'V1':load_choice(d['main'],'repair'),'AUX':load_choice(d['aux'],'repair')}
    for e in config['entries']:
        trials={}
        for method in METHODS:
            path=output/'fixed'/f"{e['instance_id']}_{method}.json"
            if path.exists():trials[method]=read(path);continue
            case=input_case(output,e)
            row=evaluate_paired_repair_candidates([loaded[method]],[case],timeout_ms=2000,
                behavior_callback=compute_exact_dp_behavior,reference_trials=trials['V1']['trials'] if method=='AUX' else None)[0]
            row.update(method=method,entry=e)
            for t in row['trials']:
                if t['feasible']:
                    solution=MultiRobotSolution(t['candidate_routes']);evaluation=case.evaluator.evaluate(solution)
                    t['snapshot']=snapshot(case.instance,solution,evaluation)
            write_json(path,row);trials[method]=row
        print(e['instance_id'],'fixed',[(m,trials[m]['mean_makespan'],trials[m]['feasible_count']) for m in METHODS],flush=True)


def run_one(output,e,seed,method,decision):
    path=output/'runs'/f"{e['instance_id']}_{method}_s{seed}.json"
    instance=load(e);expected=asdict(config_for(instance,seed,'V1'))
    if path.exists():
        saved=read(path);assert saved['config']==expected and saved['decision']==decision and saved['entry']==e
        return saved
    started=perf_counter()
    try:
        solver=portfolio_solver(instance,seed,dict(destroy=decision['destroy'],repair=decision['main']),decision['aux'],method)
        setup_seconds=perf_counter()-started;result=solver.solve()
        verified=solver.solution_evaluator.evaluate(result.best_solution);assert verified.makespan==result.best_evaluation.makespan
        usage=repair_usage(result.iteration_history,result.initial_makespan)
        row=dict(method=method,instance_id=e['instance_id'],scenario=e['scenario'],replicate_id=e['replicate_id'],seed=seed,
            feasible=True,status='fallback' if result.fallback_events else 'ok',makespan=verified.makespan,
            initial_makespan=result.initial_makespan,runtime_seconds=result.runtime_seconds,setup_seconds=setup_seconds,
            iterations=result.iterations_completed,route_dp_calls=result.route_dp_calls,route_dp_cache_misses=result.route_dp_cache_misses,
            llm_destroy_uses=sum(h['destroy']==D_NAME for h in result.iteration_history),
            llm_repair_uses=sum(h['repair'] in (R_NAME,AUX_NAME) for h in result.iteration_history),
            fallback_count=len(result.fallback_events),**result.timing_breakdown_seconds)
        saved=dict(result=row,entry=e,decision=decision,config=asdict(solver.config),initial_routes=solver.initial_solution.routes,
            best_routes=result.best_solution.routes,history=result.iteration_history,repair_usage=usage,
            snapshot=snapshot(instance,result.best_solution,verified),
            initial_to_best_behavior=compute_exact_dp_behavior(solver.initial_solution,result.best_solution,
                solver.solution_evaluator.evaluate(solver.initial_solution),verified,instance=instance),
            operator_pools=dict(destroy=list(solver.destroy_ops),repair=list(solver.repair_ops)),
            generated_operator_execution=result.generated_operator_execution,fallback_events=result.fallback_events)
        write_json(path,saved)
    except Exception as exc:
        write_json(path.with_suffix('.error.json'),dict(method=method,entry=e,seed=seed,status='error',error=f'{type(exc).__name__}: {exc}'))
        raise
    print(f"{e['instance_id']} seed {seed} {method}: M={row['makespan']:.3f}, iters={row['iterations']}, generated D/R={row['llm_destroy_uses']}/{row['llm_repair_uses']}, fallback={row['fallback_count']}",flush=True)
    return saved


def benchmark(output):
    config=setup(output)
    # Alternate scenario order across replicate, method order across solver seed.
    ordered=sorted(config['entries'],key=lambda e:(e['replicate_id'],STRUCTURAL_SCENARIOS.index(e['scenario'])))
    for e in ordered:
        for seed in SEEDS:
            for method in (METHODS if seed==0 else tuple(reversed(METHODS))):run_one(output,e,seed,method,config['decision'])


def analyze(output):
    config=setup(output);fixed_rows=[];full_rows=[];saved_runs=[];fixed_pairs=[];examples=[];proxy_rows=[]
    for e in config['entries']:
        instance=load(e);evaluator=evaluator_for(instance)
        input_record=read(output/'inputs'/f"{e['instance_id']}.json")
        fixed_records={m:read(output/'fixed'/f"{e['instance_id']}_{m}.json") for m in METHODS}
        for method in METHODS:
            record=fixed_records[method];trial=record['trials'][0]
            assert record['feasible_count']==1 and trial['feasible']
            assert trial['partial_routes']==input_record['partial_routes'] and trial['removed_tasks']==input_record['removed_tasks']
            verified=evaluator.evaluate(MultiRobotSolution(trial['candidate_routes']))
            assert abs(verified.makespan-trial['candidate_makespan'])<1e-8
            snap=trial['snapshot'];assert snapshot(instance,MultiRobotSolution(trial['candidate_routes']),verified)==snap
            proxy_rows.extend(dict(instance_id=e['instance_id'],scenario=e['scenario'],method=method,**r)
                for r in service_proxy_residual(instance,snap,trial['removed_tasks']))
            original=set(trial['bottleneck_before']);after=set(trial['bottleneck_after'])
            reference=fixed_records['V1']['trials'][0]
            fixed_rows.append(dict(method=method,instance_id=e['instance_id'],scenario=e['scenario'],replicate_id=e['replicate_id'],seed=0,
                feasible=trial['feasible'],makespan=trial['candidate_makespan'],parent_makespan=trial['parent_makespan'],
                parent_relief=trial['parent_makespan']-trial['candidate_makespan'],
                repair_run_request_ms=trial['repair_runtime_ms'],trial_wall_seconds=trial['wall_seconds'],
                route_dp_calls=trial['route_dp_calls'],route_dp_cache_misses=trial['route_dp_cache_misses'],
                new_bottleneck=bool(after-original),bottleneck_set_changed=after!=original,
                old_bottleneck_route_relief=mean(trial['parent_route_costs'][r]-trial['candidate_route_costs'][r] for r in original),
                new_bottleneck_vs_R_star=bool(after-set(reference['bottleneck_after'])),
                **snap['objective'],H_fraction=snap['H_fraction'],
                critical_turning_share=snap['critical_route']['turning_share'],
                **{f'parent_{k}':v for k,v in trial['parent_to_candidate_behavior'].items()}))
        a=fixed_records['AUX']['trials'][0];b=fixed_records['V1']['trials'][0]
        fixed_pairs.append(dict(instance_id=e['instance_id'],scenario=e['scenario'],replicate_id=e['replicate_id'],
            paired_gain_pct=100*(1-a['candidate_makespan']/b['candidate_makespan']),
            R_star_bottleneck=b['bottleneck_after'],AUX_bottleneck=a['bottleneck_after'],
            R_star_critical_route_cost_after_AUX=a['candidate_route_costs'][b['bottleneck_after'][0]],
            new_bottleneck_vs_R_star=bool(set(a['bottleneck_after'])-set(b['bottleneck_after'])),
            **a['exact_dp_behavior']))
        examples.append(dict(entry=e,input=input_record,original_repair=b,aux_repair=a,
            paired_gain_pct=100*(1-a['candidate_makespan']/b['candidate_makespan'])))
        for seed in SEEDS:
            pair=[]
            for method in METHODS:
                d=read(output/'runs'/f"{e['instance_id']}_{method}_s{seed}.json");r=d['result']
                assert d['config']==asdict(config_for(instance,seed,'V1')) and d['decision']==config['decision']
                assert d['entry']==e and len(d['operator_pools']['destroy'])==len(d['operator_pools']['repair'])==4
                solution=MultiRobotSolution(d['best_routes']);verified=evaluator.evaluate(solution)
                assert r['feasible'] and abs(verified.makespan-r['makespan'])<1e-8
                assert snapshot(instance,solution,verified)==d['snapshot']
                assert d['repair_usage']==repair_usage(d['history'],r['initial_makespan'])
                assert r['iterations']==len(d['history'])
                assert all(h2['best_makespan']<=h1['best_makespan']+1e-8 for h1,h2 in zip(d['history'],d['history'][1:]))
                pair.append(d);saved_runs.append(d)
                generated=[x for g in d['generated_operator_execution'].values() for x in g.values()]
                usages=[v for k,v in d['repair_usage'].items() if k in (R_NAME,AUX_NAME)]
                full_rows.append(dict(**r,**d['snapshot']['objective'],H_fraction=d['snapshot']['H_fraction'],
                    generated_execution_wall_seconds=sum(x['wall_time_seconds'] for x in generated),
                    generated_run_request_seconds=sum(x['run_request_seconds'] for x in generated),
                    generated_successes=sum(x['successes'] for x in generated),generated_failures=sum(x['failures'] for x in generated),
                    llm_repair_use_fraction=r['llm_repair_uses']/max(1,r['iterations']),
                    llm_repair_accepted=sum(x['accepted'] for x in usages),
                    llm_repair_global_best=sum(x['global_best'] for x in usages),
                    critical_turning_share=d['snapshot']['critical_route']['turning_share']))
            assert pair[0]['initial_routes']==pair[1]['initial_routes']
    assert len(full_rows)==84 and len(fixed_rows)==42
    _write_csv(output/'fixed_repair_results.csv',fixed_rows);_write_csv(output/'fixed_pair_DP_differences.csv',fixed_pairs)
    _write_csv(output/'fixed_service_proxy_residuals.csv',proxy_rows)
    _write_csv(output/'alns_results.csv',full_rows)
    summary=[];dp_summary=[]
    for scenario in STRUCTURAL_SCENARIOS:
        f=[r for r in fixed_rows if r['scenario']==scenario];a=[r for r in full_rows if r['scenario']==scenario]
        fs,als=paired_summary(f),paired_summary(a)
        summary.append(dict(scenario=scenario,fixed_V1=fs['V1_mean'],fixed_AUX=fs['AUX_mean'],fixed_gain_pct=fs['paired_improvement_pct'],
            fixed_wtl=fs['wtl'],ALNS_V1=als['V1_mean'],ALNS_AUX=als['AUX_mean'],ALNS_gain_pct=als['paired_improvement_pct'],ALNS_wtl=als['wtl']))
        diffs=[r for r in fixed_pairs if r['scenario']==scenario]
        for method in METHODS:
            fr=[r for r in f if r['method']==method];ar=[r for r in a if r['method']==method]
            dp_summary.append(dict(scenario=scenario,method=method,
                fixed_new_bottleneck_count=sum(r['new_bottleneck'] for r in fr),fixed_bottleneck_change_count=sum(r['bottleneck_set_changed'] for r in fr),
                fixed_mean_parent_relief=mean(r['parent_relief'] for r in fr),
                fixed_mean_old_bottleneck_relief=mean(r['old_bottleneck_route_relief'] for r in fr),
                fixed_mean_run_request_ms=mean(r['repair_run_request_ms'] for r in fr),
                fixed_mean_trial_wall_seconds=mean(r['trial_wall_seconds'] for r in fr),
                **{f'fixed_mean_{k}':mean(r[k] for r in fr) for k in ('travel_share','turning_share','H_fraction','critical_turning_share')},
                **{f'ALNS_mean_{k}':mean(r[k] for r in ar) for k in ('travel_time','coverage_traversal_time','turning_time','travel_share','turning_share','critical_turning_share','H_fraction','runtime_seconds','iterations','route_dp_calls','route_dp_cache_misses','llm_destroy_uses','llm_repair_uses')},
                **{f'AUX_vs_R_star_mean_{k}':mean(r[k] for r in diffs) for k in ('hv_mode_switch_fraction','entry_corner_switch_fraction','exit_corner_switch_fraction','dp_cascade_ratio','travel_change','coverage_change','turning_change')}))
    _write_csv(output/'scenario_summary.csv',summary);write_json(output/'scenario_summary.json',summary)
    _write_csv(output/'scenario_DP_summary.csv',dp_summary)
    structures=structure_summary()
    _write_csv(output/'structure_summary.csv',structures)
    global_summary=dict(fixed=paired_summary(fixed_rows),ALNS=paired_summary(full_rows),
        methods=[dict(method=m,**{f'mean_{k}':mean(r[k] for r in full_rows if r['method']==m) for k in
            ('runtime_seconds','iterations','route_dp_calls','route_dp_cache_misses','llm_destroy_uses','llm_repair_uses',
             'llm_repair_use_fraction','generated_execution_wall_seconds','generated_run_request_seconds',
             'llm_repair_accepted','llm_repair_global_best')}) for m in METHODS])
    fallback_keys={(r['instance_id'],r['seed']) for r in full_rows if r['fallback_count']}
    global_summary['fallbacks_by_method']={m:sum(r['fallback_count'] for r in full_rows if r['method']==m) for m in METHODS}
    global_summary['fallback_affected_pairs']=sorted(fallback_keys)
    clean=[r for r in full_rows if (r['instance_id'],r['seed']) not in fallback_keys]
    global_summary['secondary_no_fallback_pairs']=paired_summary(clean) if clean else None
    # Primary analysis always retains the actual deployed fallback outcomes.
    write_json(output/'fallback_events.json',[dict(instance_id=d['result']['instance_id'],method=d['result']['method'],
        seed=d['result']['seed'],events=d['fallback_events']) for d in saved_runs if d['fallback_events']])
    write_json(output/'summary.json',global_summary)
    # Within-instance six ALNS comparisons are grouped over the three independent geometries.
    replicate_summary=[]
    for e in config['entries']:
        group=[r for r in full_rows if r['instance_id']==e['instance_id']]
        replicate_summary.append(dict(instance_id=e['instance_id'],scenario=e['scenario'],replicate_id=e['replicate_id'],**paired_summary(group)))
    _write_csv(output/'per_instance_summary.csv',replicate_summary)
    _write_csv(output/'scenario_no_fallback_sensitivity.csv',[
        dict(scenario=s,**paired_summary([r for r in clean if r['scenario']==s]))
        for s in STRUCTURAL_SCENARIOS if any(r['scenario']==s for r in clean)])
    write_json(output/'representative_cases.json',choose_examples(examples))
    controlled=controlled_responses(output,config['entries'])
    _write_csv(output/'common_route_structural_responses.csv',controlled)
    # Compare the saved full ALNS solutions only on the same instance. These are
    # descriptive end-solution differences, not repair-only causal responses.
    final_diffs=[]
    for e in config['entries']:
        instance=load(e);ev=evaluator_for(instance)
        for seed in SEEDS:
            b=next(d for d in saved_runs if d['result']['instance_id']==e['instance_id'] and d['result']['seed']==seed and d['result']['method']=='V1')
            a=next(d for d in saved_runs if d['result']['instance_id']==e['instance_id'] and d['result']['seed']==seed and d['result']['method']=='AUX')
            before=MultiRobotSolution(b['best_routes']);after=MultiRobotSolution(a['best_routes'])
            final_diffs.append(dict(instance_id=e['instance_id'],scenario=e['scenario'],seed=seed,
                R_star_bottlenecks=b['snapshot']['bottlenecks'],AUX_bottlenecks=a['snapshot']['bottlenecks'],
                R_star_route_costs=b['snapshot']['per_robot_costs'],AUX_route_costs=a['snapshot']['per_robot_costs'],
                **compute_exact_dp_behavior(before,after,ev.evaluate(before),ev.evaluate(after),instance=instance)))
    _write_csv(output/'final_ALNS_DP_differences.csv',final_diffs)
    failures=sum(x['failures'] for d in saved_runs for g in d['generated_operator_execution'].values() for x in g.values())
    write_json(output/'verification_summary.json',dict(fixed_inputs=21,fixed_feasible_repairs=42,ALNS_complete_feasible_runs=84,
        fallback_count=sum(d['result']['fallback_count'] for d in saved_runs),generated_failures=failures,
        generated_calls=sum(x['calls'] for d in saved_runs for g in d['generated_operator_execution'].values() for x in g.values()),
        same_initial_routes_within_pair=True,all_complete_solutions_independently_reevaluated=True,
        frozen_hashes_verified=True,llm_calls=0,labels_and_data_unchanged=True,runner_hash=digest(Path(__file__))))
    report(output,summary,global_summary,dp_summary,controlled,replicate_summary,structures)
    plot_results(output,fixed_rows,full_rows)
    print(global_summary,flush=True)


def controlled_responses(output,instance_entries):
    """Common BASE task sequences across scenarios isolate state optimization,
    with cross-parameter cost subtraction done from each own evaluator snapshot.
    """
    rows=[]
    for e in instance_entries:
        base=next(x for x in instance_entries if x['scenario']=='BASE' and x['replicate_id']==e['replicate_id'])
        before=read(output/'inputs'/f"{base['instance_id']}.json")['parent_snapshot']
        after=read(output/'inputs'/f"{e['instance_id']}.json")['parent_snapshot']
        b={s['task_id']:(s['mode'],s['entry'],s['exit']) for s in before['states']}
        a={s['task_id']:(s['mode'],s['entry'],s['exit']) for s in after['states']}
        diff=state_chain_diff(b,a,affected_task_ids=set(b),directly_moved_task_ids=set())
        rows.append(dict(instance_id=e['instance_id'],scenario=e['scenario'],replicate_id=e['replicate_id'],
            common_route_makespan=after['makespan'],common_route_makespan_change=after['makespan']-before['makespan'],
            turning_share=after['objective']['turning_share'],critical_turning_share=after['critical_route']['turning_share'],
            travel_share=after['objective']['travel_share'],
            **{f'{k}_change':after['objective'][k]-before['objective'][k] for k in ('travel_time','coverage_traversal_time','turning_time')},
            **diff))
    return rows


def choose_examples(examples):
    # Descriptive representatives, not candidate selection or subsequent tuning.
    # A large benefit, a nonpositive case, and an H/V case expose different decisions.
    ordered=sorted(examples,key=lambda x:x['paired_gain_pct'],reverse=True)
    chosen=[ordered[0]]
    losses=[x for x in reversed(ordered) if x['paired_gain_pct']<=0]
    if losses:chosen.append(losses[0])
    hv=[x for x in ordered if x['entry']['scenario']=='HV-GEOM' and x not in chosen]
    if hv:chosen.append(hv[0])
    else:chosen.append(next(x for x in ordered if x not in chosen))
    return chosen[:3]


def structure_summary():
    """Summarize E10-A's pre-existing intrinsic labels; no solution-derived labels."""
    with (DATA/'structure_features.csv').open(encoding='utf-8',newline='') as handle:
        rows=list(csv.DictReader(handle))
    keys=('sweep_width','sweep_speed','travel_speed','turning_time','unoriented_aspect_mean',
          'relative_hv_gap_mean','spatial_dispersion','centroid_distance_mean','sweeps_h_mean','sweeps_v_mean',
          'preferred_turning_share_mean','travel_processing_pressure_ratio','workload_cv')
    return [dict(scenario=scenario,n_instances=3,n_tasks=40,n_robots=4,
        **{f'{k}_{stat}':fn(float(r[k]) for r in rows if r['scenario']==scenario)
           for k in keys for stat,fn in (('mean',mean),('min',min),('max',max))})
        for scenario in STRUCTURAL_SCENARIOS]


def plot_results(output,fixed_rows,full_rows):
    """Show actual paired measurements, without confidence or significance claims."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,
        'axes.spines.right':False,'legend.frameon':False,'pdf.fonttype':42,'savefig.dpi':300})
    fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    colors=('#0072B2','#D55E00')
    for source,offset,color,marker,label in ((fixed_rows,-.14,colors[0],'o','Fixed repair (3 inputs)'),
                                            (full_rows,.14,colors[1],'^','Full ALNS (6 pairs)')):
        index={(r['method'],r['instance_id'],r['seed']):r for r in source}
        for y,scenario in enumerate(STRUCTURAL_SCENARIOS):
            base=sorted((r for r in source if r['scenario']==scenario and r['method']=='V1'),
                        key=lambda r:(r['replicate_id'],r['seed']))
            gains=[100*(1-index['AUX',r['instance_id'],r['seed']]['makespan']/r['makespan']) for r in base]
            positions=[y+offset+(i-(len(gains)-1)/2)*.024 for i in range(len(gains))]
            axes[0].scatter(gains,positions,s=24,marker=marker,color=color,alpha=.8,
                label=label if y==0 else None)
            axes[0].plot([mean(gains)]*2,[y+offset-.1,y+offset+.1],color=color,lw=2.5)
    axes[0].axvline(0,color='.5',lw=.8)
    axes[0].set(yticks=range(7),yticklabels=STRUCTURAL_SCENARIOS,
        xlabel='Paired AUX improvement over R* / V1 (%)',title='(a) Same-partial gains versus complete search')
    axes[0].invert_yaxis();axes[0].grid(axis='x',alpha=.2)
    axes[0].legend(fontsize=8,loc='upper center',bbox_to_anchor=(.5,-.21),ncol=1)
    # Predefined representative, not selected for the direction of the outcome.
    for method,color,style in zip(METHODS,colors,('-','--')):
        d=read(output/'runs'/f'E10_SPATIAL_r0_{method}_s0.json')
        h=d['history']
        axes[1].step([0]+[r['elapsed_seconds'] for r in h],
            [d['result']['initial_makespan']]+[r['best_makespan'] for r in h],
            where='post',color=color,ls=style,lw=1.8,label=method)
    axes[1].set(xlabel='B1 search time (seconds)',ylabel='Global-best makespan',
        title='(b) SPATIAL replicate 0, solver seed 0')
    axes[1].grid(alpha=.2);axes[1].legend()
    for extension in ('png','pdf'):fig.savefig(output/f'structural_comparison.{extension}')
    plt.close(fig)


def report(output,summary,global_summary,dp_summary,controlled,replicates,structures):
    lines=['# E10-B structural generalization and Exact-DP response','',
        'Development/exploratory analysis, 21 pre-existing structural instances, two frozen algorithms, no LLM calls or post-result tuning. Three independent geometric replicates per scenario; solver seeds are repeated measurements, not six independent datasets. No significance or stable structural generalization claim.','',
        'One D* partial per instance (seed 0, ten removals), evaluated by both repairs. Within each replicate, all seven fixed parents have identical BASE spatial_sort sequences. Full ALNS uses each original spatial_sort constructor and 40-second budgets, seeds 0/1; each pool has three manual operators and one generated operator (4 destroy x 4 repair), unchanged. Runs execute serially with alternating method order.','',
        '## Frozen intrinsic structures','',
        '| Scenario | Width / travel speed / turn time | Mean aspect | Intrinsic H/V relative gap | Spatial dispersion | Workload CV |',
        '|---|---|---:|---:|---:|---:|']
    for r in structures:
        lines.append(f"| {r['scenario']} | {r['sweep_width_mean']:.1f} / {r['travel_speed_mean']:.1f} / {r['turning_time_mean']:.1f} | {r['unoriented_aspect_mean_mean']:.2f} | {r['relative_hv_gap_mean_mean']:.3f} | {r['spatial_dispersion_mean']:.2f} | {r['workload_cv_mean']:.3f} |")
    lines+=['','All instances have 40 tasks, four homogeneous robots and sweep speed 1. The seven labels and all intrinsic features are inherited from E10-A, before these solver results. structure_summary.csv includes means and ranges; the source feature file and manifest are frozen by hash.','',
        '## Fixed repair versus complete ALNS','',
        '| Scenario | Fixed R* | Fixed aux | Fixed paired gain | Fixed W/T/L | ALNS V1 | ALNS AUX | ALNS paired gain | ALNS W/T/L |',
        '|---|---:|---:|---:|---|---:|---:|---:|---|']
    for r in summary:lines.append(f"| {r['scenario']} | {r['fixed_V1']:.2f} | {r['fixed_AUX']:.2f} | {r['fixed_gain_pct']:+.3f}% | {r['fixed_wtl']} | {r['ALNS_V1']:.2f} | {r['ALNS_AUX']:.2f} | {r['ALNS_gain_pct']:+.3f}% | {r['ALNS_wtl']} |")
    lines+=['',f"Overall fixed paired result: {global_summary['fixed']}. Overall full ALNS paired result: {global_summary['ALNS']}.",'',
        'Paired gains average within-instance relative changes, not ratios of means. Fixed repair has three inputs per scenario; full ALNS has six matched instance/seed pairs. One spatial_sort parent is a deliberately limited sample of neighborhoods; it does not establish incumbent-repair generalization.','',
        '## Replicate consistency of complete ALNS','',
        '| Scenario | Replicate 0 paired gain | Replicate 1 paired gain | Replicate 2 paired gain |',
        '|---|---:|---:|---:|']
    for scenario in STRUCTURAL_SCENARIOS:
        group=sorted((r for r in replicates if r['scenario']==scenario),key=lambda r:r['replicate_id'])
        lines.append('| '+scenario+' | '+' | '.join(f"{r['paired_improvement_pct']:+.3f}%" for r in group)+' |')
    lines+=['','Each cell averages the two matched solver-seed ratios on one independently generated geometry, avoiding treating the two seeds as independent structures.','',
        '## Common-route structural response','',
        '| Scenario | H/V switching | Entry switching count | Mean turning share | Mean travel share | Mean travel delta |',
        '|---|---:|---:|---:|---:|---:|']
    for scenario in STRUCTURAL_SCENARIOS:
        group=[r for r in controlled if r['scenario']==scenario]
        lines.append(f"| {scenario} | {mean(r['mode_switch_fraction'] for r in group):.3f} | {mean(r['entry_corner_changed_count'] for r in group):.2f} | {mean(r['turning_share'] for r in group):.3f} | {mean(r['travel_share'] for r in group):.3f} | {mean(r['travel_time_change'] for r in group):+.2f} |")
    lines+=['','These rows use exactly the same complete task sequences across scenarios, optimized only over DP states under each instance parameters. TURN/TRAVEL/SWEEP are paired single-parameter contrasts. HV-GEOM also changes perimeter/corners/work, SPATIAL changes depot distance, and BOTTLENECK changes task area; their effects are not isolated single-parameter causes. Canonical state diff is used as a descriptive same-task comparison across instances; its cascade denominator is unchanged and the count is the existing boolean any-cascade indicator, not a number of events.','',
        'Square BASE tasks have equal H/V service time; mode changes can reflect equivalent-state tie breaking. Mode/entry/exit switching is not automatically an improvement. The displayed DP state chains minimize cost only for their supplied task sequence. All travel/coverage/turning deltas and shares aggregate all robot routes unless explicitly called critical-route; their sum is total route cost, not the makespan objective. The unchanged canonical E1 wrapper identifies directly moved tasks by robot reassignment, so same-robot reordering can enter its indirect/cascade group; this is a descriptive signature, not proof of a pure propagation effect.','',
        '## Repair responses on the same partial','',
        '| Scenario | Method | New bottleneck / 3 | Mean parent makespan relief | Mean travel share | Mean turning share | Aux-vs-R* H/V switch | Aux-vs-R* cascade ratio |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in dp_summary:lines.append(f"| {r['scenario']} | {r['method']} | {r['fixed_new_bottleneck_count']} | {r['fixed_mean_parent_relief']:+.2f} | {r['fixed_mean_travel_share']:.3f} | {r['fixed_mean_turning_share']:.3f} | {r['AUX_vs_R_star_mean_hv_mode_switch_fraction']:.3f} | {r['AUX_vs_R_star_mean_dp_cascade_ratio']:.3f} |")
    lines+=['','New bottleneck means a robot absent from the parent bottleneck set becomes critical; a shrinking tied set is not called a transfer. Both versions can relieve the original bottleneck while creating another critical route. All deltas use the real evaluator; state changes/cascade are not quality rewards and occur in wins as well as losses.','',
        '## Complete ALNS final-route DP decomposition','',
        '| Scenario | Method | Travel time | Coverage traversal | Turning time | Travel share | Turning share | Critical-route turning share |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in dp_summary:
        lines.append('| '+r['scenario']+' | '+r['method']+' | '+' | '.join(f"{r['ALNS_mean_'+k]:.3f}" for k in
            ('travel_time','coverage_traversal_time','turning_time','travel_share','turning_share','critical_turning_share'))+' |')
    lines+=['','Final-route costs describe the solution actually returned by each search. They include assignment/order changes and must not be interpreted as repair-only parameter effects. final_ALNS_DP_differences.csv retains matched endpoint differences and canonical mode/corner/cascade fields.','',
        '## Concrete decision cases','']
    for case in read(output/'representative_cases.json'):
        e=case['entry'];a=case['aux_repair'];b=case['original_repair'];inp=case['input'];dp=a['exact_dp_behavior']
        lines += [f"### {e['instance_id']}",'',
            f"Removed tasks {inp['removed_tasks']}. Parent routes cost {inp['parent_snapshot']['per_robot_costs']}. R* makespan {b['candidate_makespan']:.3f} -> aux {a['candidate_makespan']:.3f} ({case['paired_gain_pct']:+.3f}%). "
            f"R* costs {b['candidate_route_costs']}; aux costs {a['candidate_route_costs']}. Bottlenecks {b['bottleneck_after']} -> {a['bottleneck_after']}.",
            f"Identical partial route costs: {b['partial_route_costs']}. R* critical-route travel/coverage/turn: "
            f"{b['snapshot']['critical_route']['travel_time']:.3f}/{b['snapshot']['critical_route']['coverage_traversal_time']:.3f}/{b['snapshot']['critical_route']['turning_time']:.3f}; "
            f"aux critical-route travel/coverage/turn: {a['snapshot']['critical_route']['travel_time']:.3f}/{a['snapshot']['critical_route']['coverage_traversal_time']:.3f}/{a['snapshot']['critical_route']['turning_time']:.3f}.",
            f"Actual all-route cost changes (aux minus R*): travel {dp['travel_change']:+.2f}, coverage {dp['coverage_change']:+.2f}, turning {dp['turning_change']:+.2f}; "
            f"H/V switching {dp['hv_mode_switch_fraction']:.3f}, cascade ratio {dp['dp_cascade_ratio']:.3f}.",'',
            '| Task | Original robot | R* robot/position | Aux robot/position |','|---|---:|---|---|']
        am={x['task_id']:x for x in a['removed_task_moves']}
        for x in b['removed_task_moves']:
            y=am[x['task_id']]
            lines.append(f"| {x['task_id']} | {x['origin_robot']} | {x['destination_robot']}/{x['destination_position']} | {y['destination_robot']}/{y['destination_position']} |")
        before_states={s['task_id']:s for s in b['snapshot']['states']}
        after_states={s['task_id']:s for s in a['snapshot']['states']}
        mode_changes=[t for t in before_states if before_states[t]['mode']!=after_states[t]['mode']]
        lines+=['','| Mode-changed task | R* mode/entry/exit | Aux mode/entry/exit | R* processing time | Aux processing time |',
            '|---|---|---|---:|---:|']
        for t in mode_changes:
            bs,ast=before_states[t],after_states[t]
            lines.append(f"| {t} | {bs['mode']}/{bs['entry']}/{bs['exit']} | {ast['mode']}/{ast['entry']}/{ast['exit']} | {bs['processing_time']:.3f} | {ast['processing_time']:.3f} |")
        instance=load(e)
        residuals={m:service_proxy_residual(instance,t['snapshot'],t['removed_tasks'])
            for m,t in (('R*',b),('aux',a))}
        lines+=['', 'Offline service-feature check (chosen processing time minus min(H,V), not a canonical DP reward): '+
            '; '.join(f"{m}: all-route residual {sum(r['service_residual'] for r in rs):.3f}, "
                f"critical-route residual {sum(r['service_residual'] for r in rs if r['is_critical_route']):.3f}"
                for m,rs in residuals.items())+'.']
        lines+=['','All task positions are zero-based, evaluated on the final restored sequence. Full predecessors/successors, route sequences, mode/corner states and per-critical-route decomposition are retained in representative_cases.json.','']
    strongest=max(summary,key=lambda r:r['ALNS_gain_pct'])
    consistent=[s for s in STRUCTURAL_SCENARIOS if all(r['paired_improvement_pct']>0 for r in replicates if r['scenario']==s)]
    hv=next(r for r in summary if r['scenario']=='HV-GEOM')
    lines+=['## Interpretation and next research step','',
        f"{sum(r['ALNS_gain_pct']>0 for r in summary)} of seven scenario mean paired gains favor AUX in this exploratory batch, while {global_summary['ALNS']['wtl'][2]} of {global_summary['ALNS']['pairs']} individual matched runs favor V1. "
        f"{strongest['scenario']} has the largest scenario mean paired gain ({strongest['ALNS_gain_pct']:+.3f}%). Scenarios with positive mean gain on all three geometric replicates: {consistent}. "
        f"HV-GEOM W/T/L is {hv['ALNS_wtl']}. Consult replicate consistency before interpreting any label as a reliable repair preference. These summaries do not establish a structure-grounded two-expert split.",'',
        'R* uses scaled area and Euclidean center detour while aux uses min(H,V) sweep+turning workload and Manhattan center detour, dynamic regret and updated projected loads. This provides concrete decision differences, not proof that any individual heuristic feature caused a win. Both use point proxies and no online DP evaluator.','',
        'Use the fixed_pair_DP_differences.csv coverage_change/turning_change fields to check whether service totals actually differ before attributing a gain to fewer turns. Distribution of service and travel across critical and noncritical robots can matter even when total costs do not change. The detailed cases retain critical-route decompositions to distinguish those effects.','',
        'Assess C1 from end-to-end ALNS, not isolated repair gains. C2 has no portfolio deployment in this experiment; any V1/AUX crossover is only a motivation for further investigation, not portfolio benefit. Do not promote a fixed complementary set from three geometric replicates or derive structure labels from results. Keep V1 stable and AUX as a comparator until stronger independent evidence.','',
        'The concrete next C1 target is projection error: distinguish approximate service workload from endpoint-sensitive Manhattan insertion effects, and show cases where a favorable projected destination becomes the actual bottleneck. Real critical-route costs and mode/corner changes can ground a later revision. This experiment does not alter feedback, fitness, selector or operator code.','',
        '## Runtime and execution evidence','',
        '| Method | Runtime (s) | Iterations | DP calls | DP cache misses | Generated D uses | Generated R uses |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in global_summary['methods']:
        lines.append('| '+r['method']+' | '+' | '.join(f"{r['mean_'+k]:.2f}" for k in ('runtime_seconds','iterations','route_dp_calls','route_dp_cache_misses','llm_destroy_uses','llm_repair_uses'))+' |')
    lines+=['','Fixed repair_run_request_ms measures the bounded executor run request, while trial_wall_seconds includes process/IPC overhead, feasibility evaluation and DP diagnostics. Full-solver runtime uses the frozen B1 timer and can overrun the 40-second boundary by one iteration. Per-run timing and generated execution statistics are retained, not inferred from selection frequencies.','',
        f"Primary results include every fallback-affected run. Fallback events by method: {global_summary['fallbacks_by_method']}; affected pairs: {global_summary['fallback_affected_pairs']}. "
        f"Secondary descriptive sensitivity, excluding both methods of any affected pair: {global_summary['secondary_no_fallback_pairs']}. "
        'The exact timeout/error details are retained in fallback_events.json. No records were rerun to replace unfavorable or fallback outcomes.','',
        '## Reproduce','',
        '```powershell',"$env:PYTHONPATH='src'",
        "foreach ($stage in @('prepare','fixed','benchmark','analyze')) {",
        r"  & 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e10b_structural_dp_analysis --stage $stage",
        '  if ($LASTEXITCODE -ne 0) { throw "E10-B failed at $stage" }','}','```','',
        'Existing records resume without repeating calls. Use a fresh --output directory for a new run. experiment_config.json freezes input hashes, exact identities, parent design and seeds. Runs retain full routes, history, DP snapshots, generated execution timing and fallback. Stop after E10-B.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',choices=('prepare','fixed','benchmark','analyze'),required=True)
    p.add_argument('--output',type=Path,default=ROOT/'outputs/e10b_structural_dp_analysis')
    args=p.parse_args();globals()[args.stage](args.output.resolve())


if __name__=='__main__':main()
