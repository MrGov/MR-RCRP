"""E13-Fix: fully Greedy literature evaluation; historical E13 outputs retained."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from importlib import import_module
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter

from .e3_alns import ROOT, write_json
from .e5_destroy_repair import read, load_choice, D_NAME
from .e6_pair_selection import config_for
from .e8_repair_portfolio import AUX_NAME
from .e11_structural_benchmark import identities, make_solver, byte_hash, load_entry
from .e12_comparison import entries, MODULES, SEEDS, baseline_config
from .e10b_structural_dp_analysis import evaluator_for
from .e2_c1_pilot import _write_csv
from ..heuristics.alns_solver import ALNSSolver
from ..core.models import MultiRobotSolution, RouteEvaluation, SolutionEvaluation, State
from ..core.enums import Corner, SweepMode
from ..comparison_algorithms.common import validate_selected_evaluation
from ..llm.operator_evolution.persistent_candidate_execution import PersistentCandidateProxy, IDENTITY

DEFAULT_OUTPUT = ROOT/'outputs/e13_fix_fully_greedy'
METHODS = tuple(f'{m}-{mode}' for mode in ('Greedy','Exact') for m in MODULES) + ('B1','Proposed-original','Proposed-vNext')


def make_vnext(instance, seed, *, iterations=None):
    """Same AUX pool/order/config; only validated proxy execution lifetime changes."""
    solver = ALNSSolver(instance,constructor='spatial_sort',config=config_for(instance,seed,'V1',iterations=iterations))
    ids = identities(); proxies = []
    try:
        for kind,key,name in [('destroy','destroy',D_NAME),('repair','aux',AUX_NAME)]:
            validated = load_choice(ids[key],kind).callable_obj
            proxy = PersistentCandidateProxy.from_validated(validated)
            proxies.append(proxy)
            getattr(solver,'register_development_'+kind)(proxy,name=name)
        return solver,proxies
    except BaseException:
        for proxy in proxies:proxy.close()
        raise


def setup(output, *, smoke=False):
    output.mkdir(parents=True,exist_ok=True)
    old = read(ROOT/'outputs/e11_structural_benchmark/experiment_config.json')
    for p,h in old['frozen_hashes'].items():
        if byte_hash(p)!=h:raise ValueError(f'E11 original implementation changed: {p}')
    files = list((ROOT/'src/mrta_rect_coverage/comparison_algorithms').glob('*.py'))
    files += [Path(__file__),ROOT/'src/mrta_rect_coverage/llm/operator_evolution/persistent_candidate_execution.py']
    config = dict(phase='E13-Fix fully Greedy development smoke' if smoke else 'E13-Fix fully Greedy development',smoke=smoke,
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        entries=[entries()[i] for i in (0,2)] if smoke else entries(),seeds=list(SEEDS),
        methods=[m for m in METHODS if m.endswith(('-Greedy','-Exact'))] if smoke else list(METHODS),operators=identities(),
        search_configs={m:asdict(baseline_config(m,10,0)) for m in MODULES},
        smoke_budget_seconds=1.0 if smoke else None,alpha_seconds_per_task=1.,evaluation_modes=['exact','greedy'],
        unchanged_original_hashes=old['frozen_hashes'],source_hashes={str(p):byte_hash(p) for p in files},
        timing='TXT load excluded. Setup, loader smoke, initialization and online search included in task_count seconds. Greedy fixed-state validation or Exact-mode independent DP recheck, and worker cleanup timed separately; total includes both. Atomic route evaluation may finish; nested literature loops unwind on Deadline. Unchanged B1/original/vNext ALNS stops at iteration boundaries; overrun reported.',
        bootstrap='One spatial_sort complete reference evaluation is mandatory even if setup alone exceeds a tiny budget. Thereafter each route evaluation checks Deadline.',
        selection='Greedy retains its actual selected state chain and costs, with fixed-chain validation only. No DP object, DP call or state reselection in initialization, search, finish or analysis. Exact retains independent DP recheck.',
        initial_solution='spatial_sort common reference; original paper-specific population seeds retained inside budget',
        executor=dict(original='timeout_only_subprocess_v1',vnext=IDENTITY,
            semantics='Same existing worker per call, fresh module/hash/AST/timeout/log/contract checks. Warm trusted imports and dedicated process per frozen operator per solve. Discard worker on timeout/error. Not an OS sandbox; no process-global reset guarantee for arbitrary candidate imports.',
            allowed='Frozen stateless E5 Destroy and E7 AUX Repair only'),
        order='serial cyclic method rotation by instance, reverse for seed 1',
        llm_calls=0,test_accessed=False,validation_accessed=False,reuse='No historical timed runs reused')
    p=output/'experiment_config.json'
    if p.exists() and read(p)!=config:raise ValueError('Config changed; preserve results and use a fresh output')
    if not p.exists():write_json(p,config)
    return config


def solve_one(entry,seed,method,*,budget_seconds=None):
    instance=load_entry(entry);budget=float(instance.task_count) if budget_seconds is None else budget_seconds
    proxies=[]
    if method not in ('B1','Proposed-original','Proposed-vNext'):
        base,mode=method.rsplit('-',1);mode=mode.lower()
        cfg=baseline_config(base,instance.task_count,seed);cfg.evaluation_mode=mode;cfg.max_time=budget
        result=import_module('mrta_rect_coverage.comparison_algorithms.'+MODULES[base]).solve(instance,cfg)
        routes=result.best_solution.routes;verification=result.best_evaluation
        row=dict(makespan=verification.makespan,search_makespan=result.search_makespan,
            search_seconds=result.runtime_seconds,final_recheck_seconds=result.final_recheck_seconds,
            final_validation_seconds=result.final_validation_seconds,
            total_seconds=result.total_runtime_seconds,cleanup_seconds=0.,
            initialization_seconds=result.initialization_seconds,iterations=result.iterations,
            route_dp_calls=result.route_dp_calls,cache_misses=result.cache_misses,
            greedy_calls=result.greedy_calls,greedy_cache_misses=result.greedy_cache_misses,
            final_route_dp_calls=result.final_route_dp_calls,evaluations=result.evaluations,
            initial_makespan=result.initial_makespan,fallback_count=0,status='ok',
            deadline_reached=result.deadline_reached,generated_calls=0,generated_wall_seconds=0.,worker_starts=0)
        history=result.history;extras=dict(config=asdict(cfg),phase_counts=result.phase_counts,
            convergence_cost_mode=mode,final_evaluation=asdict(verification),
            selected_route_details=result.selected_route_details,
            final_evaluation_kind='greedy_selected_states' if mode=='greedy' else 'exact_dp')
    else:
        started=perf_counter()
        try:
            if method=='Proposed-vNext':solver,proxies=make_vnext(instance,seed)
            else:solver=make_solver(instance,seed,'B1' if method=='B1' else 'AUX')
            setup_seconds=perf_counter()-started
            if setup_seconds>=budget:raise TimeoutError('setup exhausted budget')
            solver.config.max_runtime_seconds=budget-setup_seconds
            result=solver.solve();search_seconds=perf_counter()-started
            recheck_started=perf_counter()
            verification=evaluator_for(instance).evaluate(result.best_solution)
            recheck_seconds=perf_counter()-recheck_started
            assert abs(verification.makespan-result.best_evaluation.makespan)<1e-8
            routes=result.best_solution.routes
            generated=[rec for group in result.generated_operator_execution.values() for rec in group.values()]
            row=dict(makespan=verification.makespan,search_makespan=result.best_evaluation.makespan,
                search_seconds=search_seconds,final_recheck_seconds=recheck_seconds,
                initialization_seconds=setup_seconds,iterations=result.iterations_completed,
                route_dp_calls=result.route_dp_calls,cache_misses=result.route_dp_cache_misses,
                greedy_calls=0,greedy_cache_misses=0,final_route_dp_calls=instance.robot_count,evaluations=None,
                initial_makespan=result.initial_makespan,fallback_count=len(result.fallback_events),
                status='fallback' if result.fallback_events else 'ok',deadline_reached=search_seconds>=budget,
                generated_calls=sum(r['calls'] for r in generated),
                generated_wall_seconds=sum(r['wall_time_seconds'] for r in generated),
                worker_starts=sum(p.process_starts for p in proxies))
            history=[dict(h,elapsed_seconds=h['elapsed_seconds']+setup_seconds) for h in result.iteration_history]
            history.insert(0,dict(elapsed_seconds=setup_seconds,best_makespan=result.initial_makespan))
            extras=dict(config=asdict(solver.config),generated_execution=result.generated_operator_execution,
                fallback_events=result.fallback_events,pools=dict(destroy=list(solver.destroy_ops),repair=list(solver.repair_ops)),
                timing_breakdown_seconds=result.timing_breakdown_seconds,convergence_cost_mode='exact')
        finally:
            cleanup_started=perf_counter()
            for p in proxies:p.close()
            cleanup_seconds=perf_counter()-cleanup_started
        row.update(cleanup_seconds=cleanup_seconds,total_seconds=perf_counter()-started)
    row.update(instance_id=entry['instance_id'],scenario=entry['scenario'],tasks=instance.task_count,
        robots=instance.robot_count,seed=seed,method=method,budget_seconds=budget,
        budget_overrun_seconds=max(0.,row['search_seconds']-budget),feasible=True)
    return dict(result=row,entry=entry,best_routes=routes,per_robot_costs=verification.per_robot_costs,history=history,**extras)


def run(output, *, smoke=False):
    config=setup(output,smoke=smoke)
    methods=tuple(config['methods'])
    for i,entry in enumerate(config['entries']):
        for seed in SEEDS:
            order=methods[i%len(methods):]+methods[:i%len(methods)]
            if seed:order=tuple(reversed(order))
            for method in order:
                path=output/'runs'/entry['instance_id']/f'{method}_s{seed}.json'
                if path.exists():continue
                try:
                    if smoke and method.endswith('-Greedy'):
                        from unittest.mock import patch
                        from ..core.dp_evaluator import RouteDPEvaluator
                        with patch.object(RouteDPEvaluator,'__init__',side_effect=AssertionError('Greedy DP construction forbidden')), patch.object(RouteDPEvaluator,'evaluate_route',side_effect=AssertionError('Greedy DP call forbidden')):
                            record=solve_one(entry,seed,method,budget_seconds=config['smoke_budget_seconds'])
                    else:record=solve_one(entry,seed,method,budget_seconds=config['smoke_budget_seconds'])
                except Exception as exc:
                    write_json(output/'failures'/entry['instance_id']/f'{method}_s{seed}.json',
                        dict(method=method,seed=seed,error_type=type(exc).__name__,error=str(exc)))
                    raise
                write_json(path,record);r=record['result']
                print(f"{entry['instance_id']} s{seed} {method}: M={r['makespan']:.3f}, search={r['search_seconds']:.4f}s, iters={r['iterations']}, fallback={r['fallback_count']}",flush=True)


def validate_record(instance, record):
    """Validate saved Greedy states verbatim; Exact records keep their DP check."""
    solution=MultiRobotSolution(record['best_routes'])
    if record['result']['method'].endswith('-Greedy'):
        data=record['final_evaluation']
        routes=[]
        for route in data['route_evaluations']:
            values=dict(route)
            values['chosen_states']=[State(**dict(s,
                entry_corner=Corner(s['entry_corner']),exit_corner=Corner(s['exit_corner']),
                sweep_mode=SweepMode(s['sweep_mode']),entry_point=tuple(s['entry_point']),
                exit_point=tuple(s['exit_point']))) for s in route['chosen_states']]
            for field in ('entry_points','exit_points'):
                values[field]=[tuple(p) for p in route[field]]
            routes.append(RouteEvaluation(**values))
        evaluation=SolutionEvaluation(data['per_robot_costs'],routes,data['makespan'])
        evidence=validate_selected_evaluation(instance,solution,evaluation)
        if record['selected_route_details'] != evidence:
            raise ValueError('saved selected route decomposition mismatch')
        if any(record['result'][k] != 0 for k in ('route_dp_calls','cache_misses','final_route_dp_calls','final_recheck_seconds')):
            raise ValueError('fully Greedy record cannot contain DP work')
        if evaluation.makespan != record['result']['search_makespan']:
            raise ValueError('Greedy final result changed after search')
    else:
        evaluation=evaluator_for(instance).evaluate(solution)
        evidence=None
    if abs(evaluation.makespan-record['result']['makespan'])>1e-8 or evaluation.per_robot_costs != record['per_robot_costs']:
        raise ValueError('saved final costs mismatch')
    return evidence


def analyze(output):
    saved=read(output/'experiment_config.json')
    config=setup(output,smoke=saved.get('smoke',False));records=[]
    methods=tuple(config['methods'])
    for entry in config['entries']:
        instance=load_entry(entry)
        for seed in SEEDS:
            for method in methods:
                rec=read(output/'runs'/entry['instance_id']/f'{method}_s{seed}.json')
                validate_record(instance,rec)
                records.append(rec)
    rows=[r['result'] for r in records]
    _write_csv(output/'results.csv',rows)
    summaries=[];pairs=[]
    for dimension in ('overall','tasks','scenario'):
        for label in (['all'] if dimension=='overall' else sorted({r[dimension] for r in rows})):
            group=[r for r in rows if dimension=='overall' or r[dimension]==label]
            for method in methods:
                subset=[r for r in group if r['method']==method]
                summaries.append(dict(dimension=dimension,label=label,method=method,
                    mean_makespan=mean(r['makespan'] for r in subset),mean_search_seconds=mean(r['search_seconds'] for r in subset),
                    mean_final_recheck_seconds=mean(r['final_recheck_seconds'] for r in subset),
                    mean_final_validation_seconds=mean(r.get('final_validation_seconds',0.0) for r in subset),
                    mean_total_seconds=mean(r['total_seconds'] for r in subset),mean_iterations=mean(r['iterations'] for r in subset),
                    mean_route_dp_calls=mean(r['route_dp_calls'] for r in subset),mean_cache_misses=mean(r['cache_misses'] for r in subset),
                    mean_generated_calls=mean(r['generated_calls'] for r in subset),
                    mean_generated_wall_seconds=mean(r['generated_wall_seconds'] for r in subset),
                    fallback_count=sum(r['fallback_count'] for r in subset),max_overrun_seconds=max(r['budget_overrun_seconds'] for r in subset)))
            comparisons=[(f'{m}-Greedy',f'{m}-Exact') for m in MODULES]
            if 'Proposed-vNext' in methods:comparisons += [('Proposed-vNext',m) for m in methods if m!='Proposed-vNext']
            for target,reference in comparisons:
                a={(r['instance_id'],r['seed']):r for r in group if r['method']==target}
                b={(r['instance_id'],r['seed']):r for r in group if r['method']==reference}
                gains=[100*(1-a[k]['makespan']/b[k]['makespan']) for k in a]
                pairs.append(dict(dimension=dimension,label=label,target=target,reference=reference,
                    paired_improvement_pct=mean(gains),wins=sum(g>1e-8 for g in gains),ties=sum(abs(g)<=1e-8 for g in gains),losses=sum(g< -1e-8 for g in gains)))
    _write_csv(output/'summary.csv',summaries);_write_csv(output/'paired_comparisons.csv',pairs)
    write_json(output/'best_solutions.json',[dict(result=r['result'],routes=r['best_routes'],per_robot_costs=r['per_robot_costs'],final_evaluation=r.get('final_evaluation'),selected_route_details=r.get('selected_route_details')) for r in records])
    if not config['smoke']:plot(output,records)
    lines=['# E13-Fix fully Greedy evaluation','',
        f"{len(config['entries'])} E12 manifest-qualified development instances, seeds 0/1; {len(rows)} real runs. No test/validation solves or LLM calls. Historical E13 outputs retained.",'',
        'Smoke uses a fixed 1-second setup+search budget per solve; normal run uses task_count seconds. No search parameters or Deadline rules changed.','',
        '| Method | Final makespan (Greedy actual / Exact DP) | Search s | Recheck s | Total s | Iterations | Fallback | Max search overrun s |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        if s['dimension']=='overall':lines.append(f"| {s['method']} | {s['mean_makespan']:.3f} | {s['mean_search_seconds']:.4f} | {s['mean_final_recheck_seconds']:.4f} | {s['mean_total_seconds']:.4f} | {s['mean_iterations']:.1f} | {s['fallback_count']} | {s['max_overrun_seconds']:.4f} |")
    lines+=['','## Paired comparisons','', '| Target | Reference | Mean paired gain | W/T/L |','|---|---|---:|---|']
    for p in pairs:
        if p['dimension']=='overall':lines.append(f"| {p['target']} | {p['reference']} | {p['paired_improvement_pct']:+.3f}% | {p['wins']}/{p['ties']}/{p['losses']} |")
    lines+=['','Search time includes state/matrix setup, loader smoke, initialization and online search. Final fixed-state validation (Greedy), independent DP recheck (Exact), and worker cleanup are separately recorded and included in total time. Literature algorithms check Deadline before every route evaluation; one indivisible route evaluation may finish. B1/Proposed retain their frozen iteration-boundary stopping semantics; their overrun is measured, not hidden.','',
        'Greedy selects legal states from incoming Manhattan travel plus processing, with depot return included at the final task. Final makespan is the actual cost of those same selected states, unchanged from the search incumbent. It is not Exact-DP rechecked or reoptimized. State IDs, H/V modes, entry/exit corners, traces and physical costs are saved in final_evaluation. Analysis validates only this fixed chain. Search and final DP calls are both zero; final_recheck_seconds=0, while final_validation_seconds records arithmetic/legality checks.','',
        'Proposed-original keeps the E11 AUX factory and per-call spawned executor unchanged. Proposed-vNext uses the same frozen candidate files, pool order, weights and B1 settings; dedicated warm workers reuse trusted imports. Every call still runs the original hash/AST-validated worker in a fresh candidate namespace, sends arguments/results over a pipe, bounds logs, enforces timeout, and preserves ALNS feasibility/fallback checks. Failed workers are discarded. This preserves process isolation from the solver but does not provide a fresh interpreter per call or an OS sandbox; deployment is limited to the frozen stateless operators.','',
        'Small development sample confounds scale and scenario; timed algorithms are not bit-for-bit replayable. No significance, generalization or SOTA claim. All configurations were fixed before these results; no outcome-driven tuning.','',
        '## Reproduce','', '```powershell',"$env:PYTHONPATH='src'",
        r"& 'G:\Anaconda\envs\mrta_env\python.exe' -m pytest tests/test_e13_evaluation.py tests/test_e13_persistent_execution.py tests/test_comparison_algorithms.py tests/test_e12_comparison.py tests/test_dp_evaluator.py tests/test_solution_evaluator.py -q",
        r"& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e13_evaluation_efficiency --stage smoke",
        r"& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e13_evaluation_efficiency --stage analyze",'```','',
        'Run resumes completed records without replacement; use a fresh --output for independent measurement. Windows idle sleep is temporarily suppressed during run and restored on exit. Source/data hashes and original frozen hashes are verified in experiment_config.json. All best routes and histories are retained.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_json(output/'verification.json',dict(records=len(rows),feasible=len(rows),llm_calls=0,test_accessed=False,
        greedy_dp_calls=sum(r['route_dp_calls']+r['final_route_dp_calls'] for r in rows if r['method'].endswith('-Greedy')),
        greedy_final_policy='unchanged selected state chain; no Exact-DP construction/calls',original_hashes_verified=True,fallback_count=sum(r['fallback_count'] for r in rows)))
    print('\n'.join(lines[:20]),flush=True)


def plot(output,records):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    entry=entries()[-1]
    groups=[tuple(m for m in METHODS if m.endswith('-Exact'))+('B1',),('B1','Proposed-original','Proposed-vNext')]
    for ax,methods in zip(axes,groups):
        for method in methods:
            rec=next(r for r in records if r['result']['instance_id']==entry['instance_id'] and r['result']['seed']==0 and r['result']['method']==method)
            ax.step([h['elapsed_seconds'] for h in rec['history']],[h['best_makespan'] for h in rec['history']],where='post',label=method)
        ax.set(xlabel='Setup + search elapsed (s)',ylabel='Best exact makespan',title=entry['instance_id'].removeprefix('development/'))
        ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(output/'convergence.png',dpi=220);fig.savefig(output/'convergence.svg');plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('run','smoke','analyze'),required=True)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    if args.stage in ('run','smoke'):
        import ctypes,sys
        if sys.platform=='win32':ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:run(args.output.resolve(),smoke=args.stage=='smoke')
        finally:
            if sys.platform=='win32':ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    else:analyze(args.output.resolve())


if __name__=='__main__':main()
