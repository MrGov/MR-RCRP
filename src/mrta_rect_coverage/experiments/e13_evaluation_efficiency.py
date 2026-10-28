"""E13: development-only Exact/Greedy and original/warm-process comparison."""
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
from ..core.models import MultiRobotSolution
from ..llm.operator_evolution.persistent_candidate_execution import PersistentCandidateProxy, IDENTITY

DEFAULT_OUTPUT = ROOT/'outputs/e13_evaluation_efficiency'
METHODS = tuple(f'{m}-{mode}' for mode in ('greedy','exact') for m in MODULES) + ('B1','Proposed-original','Proposed-vNext')


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


def setup(output):
    output.mkdir(parents=True,exist_ok=True)
    old = read(ROOT/'outputs/e11_structural_benchmark/experiment_config.json')
    for p,h in old['frozen_hashes'].items():
        if byte_hash(p)!=h:raise ValueError(f'E11 original implementation changed: {p}')
    files = list((ROOT/'src/mrta_rect_coverage/comparison_algorithms').glob('*.py'))
    files += [Path(__file__),ROOT/'src/mrta_rect_coverage/llm/operator_evolution/persistent_candidate_execution.py']
    config = dict(phase='E13 development/exploratory',
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        entries=entries(),seeds=list(SEEDS),methods=list(METHODS),operators=identities(),
        search_configs={m:asdict(baseline_config(m,10,0)) for m in MODULES},
        alpha_seconds_per_task=1.,evaluation_modes=['exact','greedy'],
        unchanged_original_hashes=old['frozen_hashes'],source_hashes={str(p):byte_hash(p) for p in files},
        timing='TXT load excluded. Setup, loader smoke, initialization and online search included in task_count seconds. Final independent Exact-DP recheck and worker cleanup timed separately; total includes both. Atomic route evaluation may finish; nested literature loops unwind on Deadline. Unchanged B1/original/vNext ALNS stops at iteration boundaries; overrun reported.',
        bootstrap='One spatial_sort complete reference evaluation is mandatory even if setup alone exceeds a tiny budget. Thereafter each route evaluation checks Deadline.',
        selection='Greedy history and incumbent use greedy estimates exclusively. Recheck only frozen incumbent allocation/order; no post-search reselection.',
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


def solve_one(entry,seed,method):
    instance=load_entry(entry);budget=float(instance.task_count)
    proxies=[]
    if method not in ('B1','Proposed-original','Proposed-vNext'):
        base,mode=method.rsplit('-',1)
        cfg=baseline_config(base,instance.task_count,seed);cfg.evaluation_mode=mode
        result=import_module('mrta_rect_coverage.comparison_algorithms.'+MODULES[base]).solve(instance,cfg)
        routes=result.best_solution.routes;verification=result.best_evaluation
        row=dict(makespan=verification.makespan,search_makespan=result.search_makespan,
            search_seconds=result.runtime_seconds,final_recheck_seconds=result.final_recheck_seconds,
            total_seconds=result.total_runtime_seconds,cleanup_seconds=0.,
            initialization_seconds=result.initialization_seconds,iterations=result.iterations,
            route_dp_calls=result.route_dp_calls,cache_misses=result.cache_misses,
            greedy_calls=result.greedy_calls,greedy_cache_misses=result.greedy_cache_misses,
            final_route_dp_calls=result.final_route_dp_calls,evaluations=result.evaluations,
            initial_makespan=result.initial_makespan,fallback_count=0,status='ok',
            deadline_reached=result.deadline_reached,generated_calls=0,generated_wall_seconds=0.,worker_starts=0)
        history=result.history;extras=dict(config=asdict(cfg),phase_counts=result.phase_counts,
            convergence_cost_mode=mode)
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


def run(output):
    config=setup(output)
    for i,entry in enumerate(config['entries']):
        for seed in SEEDS:
            order=METHODS[i%len(METHODS):]+METHODS[:i%len(METHODS)]
            if seed:order=tuple(reversed(order))
            for method in order:
                path=output/'runs'/entry['instance_id']/f'{method}_s{seed}.json'
                if path.exists():continue
                try:record=solve_one(entry,seed,method)
                except Exception as exc:
                    write_json(output/'failures'/entry['instance_id']/f'{method}_s{seed}.json',
                        dict(method=method,seed=seed,error_type=type(exc).__name__,error=str(exc)))
                    raise
                write_json(path,record);r=record['result']
                print(f"{entry['instance_id']} s{seed} {method}: M={r['makespan']:.3f}, search={r['search_seconds']:.4f}s, iters={r['iterations']}, fallback={r['fallback_count']}",flush=True)


def analyze(output):
    config=setup(output);records=[]
    for entry in config['entries']:
        evaluator=evaluator_for(load_entry(entry))
        for seed in SEEDS:
            for method in METHODS:
                rec=read(output/'runs'/entry['instance_id']/f'{method}_s{seed}.json')
                check=evaluator.evaluate(MultiRobotSolution(rec['best_routes']))
                if abs(check.makespan-rec['result']['makespan'])>1e-8:raise ValueError('Exact verification mismatch')
                records.append(rec)
    rows=[r['result'] for r in records]
    _write_csv(output/'results.csv',rows)
    summaries=[];pairs=[]
    for dimension in ('overall','tasks','scenario'):
        for label in (['all'] if dimension=='overall' else sorted({r[dimension] for r in rows})):
            group=[r for r in rows if dimension=='overall' or r[dimension]==label]
            for method in METHODS:
                subset=[r for r in group if r['method']==method]
                summaries.append(dict(dimension=dimension,label=label,method=method,
                    mean_makespan=mean(r['makespan'] for r in subset),mean_search_seconds=mean(r['search_seconds'] for r in subset),
                    mean_final_recheck_seconds=mean(r['final_recheck_seconds'] for r in subset),
                    mean_total_seconds=mean(r['total_seconds'] for r in subset),mean_iterations=mean(r['iterations'] for r in subset),
                    mean_route_dp_calls=mean(r['route_dp_calls'] for r in subset),mean_cache_misses=mean(r['cache_misses'] for r in subset),
                    mean_generated_calls=mean(r['generated_calls'] for r in subset),
                    mean_generated_wall_seconds=mean(r['generated_wall_seconds'] for r in subset),
                    fallback_count=sum(r['fallback_count'] for r in subset),max_overrun_seconds=max(r['budget_overrun_seconds'] for r in subset)))
            comparisons=[(f'{m}-greedy',f'{m}-exact') for m in MODULES]
            comparisons += [('Proposed-vNext',m) for m in METHODS if m!='Proposed-vNext']
            for target,reference in comparisons:
                a={(r['instance_id'],r['seed']):r for r in group if r['method']==target}
                b={(r['instance_id'],r['seed']):r for r in group if r['method']==reference}
                gains=[100*(1-a[k]['makespan']/b[k]['makespan']) for k in a]
                pairs.append(dict(dimension=dimension,label=label,target=target,reference=reference,
                    paired_improvement_pct=mean(gains),wins=sum(g>1e-8 for g in gains),ties=sum(abs(g)<=1e-8 for g in gains),losses=sum(g< -1e-8 for g in gains)))
    _write_csv(output/'summary.csv',summaries);_write_csv(output/'paired_comparisons.csv',pairs)
    write_json(output/'best_solutions.json',[dict(result=r['result'],routes=r['best_routes'],per_robot_costs=r['per_robot_costs']) for r in records])
    plot(output,records)
    lines=['# E13 development evaluation and execution efficiency','',
        'Four E12 manifest-qualified development instances, seeds 0/1; 88 real runs. No test/validation solves, LLM calls, model changes or frozen operator edits. No historical timing reuse.','',
        '| Method | Exact final makespan | Search s | Recheck s | Total s | Iterations | Fallback | Max search overrun s |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        if s['dimension']=='overall':lines.append(f"| {s['method']} | {s['mean_makespan']:.3f} | {s['mean_search_seconds']:.4f} | {s['mean_final_recheck_seconds']:.4f} | {s['mean_total_seconds']:.4f} | {s['mean_iterations']:.1f} | {s['fallback_count']} | {s['max_overrun_seconds']:.4f} |")
    lines+=['','## Paired comparisons','', '| Target | Reference | Mean paired gain | W/T/L |','|---|---|---:|---|']
    for p in pairs:
        if p['dimension']=='overall':lines.append(f"| {p['target']} | {p['reference']} | {p['paired_improvement_pct']:+.3f}% | {p['wins']}/{p['ties']}/{p['losses']} |")
    lines+=['','Search time includes state/matrix setup, loader smoke, initialization and online search. Final independent Exact-DP and warm-worker cleanup are separately recorded and included in total time. Literature algorithms check Deadline before every route evaluation; one indivisible route evaluation may finish. B1/Proposed retain their frozen iteration-boundary stopping semantics; their overrun is measured, not hidden.','',
        'Greedy selects a single legal state from incoming Manhattan travel plus processing at each task, with final depot return included at the last task. Its history is an estimated-score history; only its frozen best route allocation/order is independently reoptimized by Exact-DP. The exact final value must not be confused with the greedy search estimate. No Exact-DP reranking is used during greedy search.','',
        'Proposed-original keeps the E11 AUX factory and per-call spawned executor unchanged. Proposed-vNext uses the same frozen candidate files, pool order, weights and B1 settings; dedicated warm workers reuse trusted imports. Every call still runs the original hash/AST-validated worker in a fresh candidate namespace, sends arguments/results over a pipe, bounds logs, enforces timeout, and preserves ALNS feasibility/fallback checks. Failed workers are discarded. This preserves process isolation from the solver but does not provide a fresh interpreter per call or an OS sandbox; deployment is limited to the frozen stateless operators.','',
        'Small development sample confounds scale and scenario; timed algorithms are not bit-for-bit replayable. No significance, generalization or SOTA claim. All configurations were fixed before these results; no outcome-driven tuning.','',
        '## Reproduce','', '```powershell',"$env:PYTHONPATH='src'",
        r"& 'G:\Anaconda\envs\mrta_env\python.exe' -m pytest tests/test_e13_evaluation.py tests/test_e13_persistent_execution.py tests/test_comparison_algorithms.py tests/test_e12_comparison.py tests/test_dp_evaluator.py tests/test_solution_evaluator.py -q",
        r"& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e13_evaluation_efficiency --stage run",
        r"& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e13_evaluation_efficiency --stage analyze",'```','',
        'Run resumes completed records without replacement; use a fresh --output for independent measurement. Windows idle sleep is temporarily suppressed during run and restored on exit. Source/data hashes and original frozen hashes are verified in experiment_config.json. All best routes and histories are retained.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_json(output/'verification.json',dict(records=len(rows),feasible=len(rows),llm_calls=0,test_accessed=False,
        independent_exact_recheck=True,original_hashes_verified=True,fallback_count=sum(r['fallback_count'] for r in rows)))
    print('\n'.join(lines[:20]),flush=True)


def plot(output,records):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    entry=entries()[-1]
    groups=[tuple(m for m in METHODS if m.endswith('-exact'))+('B1',),('B1','Proposed-original','Proposed-vNext')]
    for ax,methods in zip(axes,groups):
        for method in methods:
            rec=next(r for r in records if r['result']['instance_id']==entry['instance_id'] and r['result']['seed']==0 and r['result']['method']==method)
            ax.step([h['elapsed_seconds'] for h in rec['history']],[h['best_makespan'] for h in rec['history']],where='post',label=method)
        ax.set(xlabel='Setup + search elapsed (s)',ylabel='Best exact makespan',title=entry['instance_id'].removeprefix('development/'))
        ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(output/'convergence.png',dpi=220);fig.savefig(output/'convergence.svg');plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('run','analyze'),required=True)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    if args.stage=='run':
        import ctypes,sys
        if sys.platform=='win32':ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:run(args.output.resolve())
        finally:
            if sys.platform=='win32':ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    else:analyze(args.output.resolve())


if __name__=='__main__':main()
