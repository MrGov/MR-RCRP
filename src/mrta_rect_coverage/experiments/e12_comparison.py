"""Development-only literature comparison; serial, total initialization+search budget."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from importlib import import_module
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter

from .e3_alns import ROOT, write_json
from .e5_destroy_repair import read
from .e11_structural_benchmark import catalog, load_entry, byte_hash, make_solver, identities
from .e2_c1_pilot import _write_csv
from .e10b_structural_dp_analysis import evaluator_for
from ..comparison_algorithms.common import SearchConfig
from ..core.models import MultiRobotSolution

METHODS=('B1','CDABC','RNSGA','SGA-TS','MRHDABC','Proposed')
MODULES={'CDABC':'cdabc','RNSGA':'rnsga','SGA-TS':'sga_ts','MRHDABC':'mrhdabc'}
SAMPLES=('development/BASE/R2_T10_0','development/HV-GEOM/R2_T20_0',
         'development/BOTTLENECK/R4_T40_0','development/TRAVEL-HIGH/R8_T80_0')
SEEDS=(0,1)
DEFAULT_OUTPUT=ROOT/'outputs/e12_literature_baselines'


def entries():
    index={e['instance_id']:e for e in catalog()['entries']}
    rows=[index[i] for i in SAMPLES]
    if any(e['split']!='development' for e in rows):raise ValueError('development only')
    return rows


def baseline_config(method,tasks,seed,*,generations=None):
    options=dict(max_time=float(tasks),seed=seed,population_size=12,max_generations=generations)
    if method=='CDABC':options.update(scout_limit=50)
    if method=='MRHDABC':options.update(scout_limit=150,local_depth=5)
    return SearchConfig(**options)


def setup(output):
    output.mkdir(parents=True,exist_ok=True)
    freeze=read(ROOT/'outputs/e11_structural_benchmark/algorithm_freeze.json')
    if freeze['recommended_proposed']!='AUX' or freeze['operators']!=identities():
        raise ValueError('E11 Proposed identity changed')
    old=read(ROOT/'outputs/e11_structural_benchmark/experiment_config.json')
    for p,h in old['frozen_hashes'].items():
        if byte_hash(p)!=h:raise ValueError(f'E11 frozen implementation changed: {p}')
    files=list((ROOT/'src/mrta_rect_coverage/comparison_algorithms').glob('*.py'))
    files+=[Path(__file__),ROOT/'src/mrta_rect_coverage/comparison_algorithms/ADAPTATIONS.md']
    files+=list((ROOT/'Com-alg').glob('*.pdf'))
    files+=[ROOT/'data/structural_benchmark_v1/manifest.json',ROOT/'outputs/e11_structural_benchmark/algorithm_freeze.json']
    config=dict(phase='E12 adapted literature development comparison',git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        entries=entries(),seeds=list(SEEDS),methods=list(METHODS),proposed=freeze,
        baseline_configs={m:asdict(baseline_config(m,10,0)) for m in MODULES},
        parameter_substitution='max_time/max_runtime_seconds=task_count seconds including initialization; seed=0,1',
        frozen_hashes={str(p):byte_hash(p) for p in files},unchanged_e11_hashes=old['frozen_hashes'],
        timing='After TXT load: start before state/matrix construction, candidate import and population initialization. B1/Proposed remaining solve budget is task_count minus setup elapsed; no core changes. Existing iteration-boundary overshoot recorded. Independent final verification excluded.',
        initial_solutions='All start with/evaluate spatial_sort reference. Population solvers additionally use paper-specific seeds and random initialization inside time budget.',
        order='serial; cyclic six-method rotation by instance, reversed for seed 1',
        reuse='No historical timed measurements reused: E11 excluded setup from its budget.',
        llm_calls=0,test_accessed=False,validation_accessed=False,
        reproduction='python -m mrta_rect_coverage.experiments.e12_comparison --stage run; then --stage analyze')
    path=output/'experiment_config.json'
    if path.exists():
        if read(path)!=config:raise ValueError('configuration changed: preserve output and use a fresh --output')
    else:write_json(path,config)
    return config


def solve_one(entry,seed,method):
    instance=load_entry(entry);budget=float(instance.task_count)
    if method in MODULES:
        cfg=baseline_config(method,instance.task_count,seed)
        result=import_module('mrta_rect_coverage.comparison_algorithms.'+MODULES[method]).solve(instance,cfg)
        row=dict(makespan=result.best_evaluation.makespan,runtime_seconds=result.runtime_seconds,
            initialization_seconds=result.initialization_seconds,iterations=result.iterations,
            evaluations=result.evaluations,route_dp_calls=result.route_dp_calls,cache_misses=result.cache_misses,
            initial_makespan=result.initial_makespan,fallback_count=0,status='ok')
        routes=result.best_solution.routes;history=result.history
        extras=dict(phase_counts=result.phase_counts,config=asdict(cfg))
    else:
        started=perf_counter()
        solver=make_solver(instance,seed,'B1' if method=='B1' else 'AUX')
        setup_seconds=perf_counter()-started
        if setup_seconds>=budget:raise TimeoutError('initialization exhausted total budget')
        solver.config.max_runtime_seconds=budget-setup_seconds
        result=solver.solve();total=perf_counter()-started
        row=dict(makespan=result.best_evaluation.makespan,runtime_seconds=total,
            initialization_seconds=setup_seconds,iterations=result.iterations_completed,
            evaluations=None,route_dp_calls=result.route_dp_calls,cache_misses=result.route_dp_cache_misses,
            initial_makespan=result.initial_makespan,fallback_count=len(result.fallback_events),
            status='fallback' if result.fallback_events else 'ok')
        routes=result.best_solution.routes
        history=[dict(h,elapsed_seconds=h['elapsed_seconds']+setup_seconds) for h in result.iteration_history]
        history.insert(0,dict(elapsed_seconds=setup_seconds,best_makespan=result.initial_makespan,generation=0))
        extras=dict(config=asdict(solver.config),generated_execution=result.generated_operator_execution,
            fallback_events=result.fallback_events,pools=dict(destroy=list(solver.destroy_ops),repair=list(solver.repair_ops)))
    # Independent evaluator enforces exactly-once allocation and identical objective.
    verification=evaluator_for(instance).evaluate(MultiRobotSolution(routes))
    if abs(verification.makespan-row['makespan'])>1e-8:raise ValueError('independent verification mismatch')
    row.update(instance_id=entry['instance_id'],scenario=entry['scenario'],tasks=instance.task_count,
        robots=instance.robot_count,seed=seed,method=method,budget_seconds=budget,
        budget_overrun_seconds=max(0,row['runtime_seconds']-budget),feasible=True)
    return dict(result=row,entry=entry,best_routes=routes,per_robot_costs=verification.per_robot_costs,
        history=history,**extras)


def run(output):
    config=setup(output)
    for i,entry in enumerate(config['entries']):
        for seed in SEEDS:
            order=METHODS[i%len(METHODS):]+METHODS[:i%len(METHODS)]
            if seed:order=tuple(reversed(order))
            for method in order:
                path=output/'runs'/entry['instance_id']/f'{method}_s{seed}.json'
                if path.exists():
                    record=read(path)
                    if record['entry']!=entry:raise ValueError('saved identity mismatch')
                    continue
                try:record=solve_one(entry,seed,method)
                except Exception as exc:
                    failure=output/'failures'/entry['instance_id']/f'{method}_s{seed}.json'
                    write_json(failure,dict(instance_id=entry['instance_id'],seed=seed,method=method,
                        error_type=type(exc).__name__,error=str(exc),action='stopped; completed measurements retained'))
                    raise
                write_json(path,record);r=record['result']
                print(f"{r['instance_id']} s{seed} {method}: {r['makespan']:.3f}, {r['runtime_seconds']:.3f}s, {r['iterations']} cycles, fallback={r['fallback_count']}",flush=True)


def analyze(output):
    config=setup(output);rows=[];records=[]
    for entry in config['entries']:
        evaluator=evaluator_for(load_entry(entry))
        for seed in SEEDS:
            for method in METHODS:
                record=read(output/'runs'/entry['instance_id']/f'{method}_s{seed}.json')
                actual=evaluator.evaluate(MultiRobotSolution(record['best_routes']))
                if abs(actual.makespan-record['result']['makespan'])>1e-8:raise ValueError('saved solution mismatch')
                if any(a['best_makespan']<b['best_makespan']-1e-8 for a,b in zip(record['history'],record['history'][1:])):
                    raise ValueError('nonmonotone global best history')
                rows.append(record['result']);records.append(record)
    _write_csv(output/'results.csv',rows)
    summaries=[];pairs=[]
    for dimension in ('overall','tasks','scenario'):
        labels=['all'] if dimension=='overall' else sorted({r[dimension] for r in rows})
        for label in labels:
            group=[r for r in rows if dimension=='overall' or r[dimension]==label]
            for method in METHODS:
                rs=[r for r in group if r['method']==method]
                summaries.append(dict(dimension=dimension,label=label,method=method,runs=len(rs),
                    mean_makespan=mean(r['makespan'] for r in rs),mean_runtime_seconds=mean(r['runtime_seconds'] for r in rs),
                    mean_iterations=mean(r['iterations'] for r in rs),mean_route_dp_calls=mean(r['route_dp_calls'] for r in rs),
                    mean_cache_misses=mean(r['cache_misses'] for r in rs),fallback_count=sum(r['fallback_count'] for r in rs)))
            proposed={(r['instance_id'],r['seed']):r for r in group if r['method']=='Proposed'}
            for method in METHODS[:-1]:
                ref={(r['instance_id'],r['seed']):r for r in group if r['method']==method}
                if proposed.keys()!=ref.keys():raise ValueError('missing paired results')
                gains=[100*(1-proposed[k]['makespan']/ref[k]['makespan']) for k in ref]
                pairs.append(dict(dimension=dimension,label=label,reference=method,
                    paired_improvement_pct=mean(gains),wins=sum(g>1e-8 for g in gains),
                    ties=sum(abs(g)<=1e-8 for g in gains),losses=sum(g< -1e-8 for g in gains)))
    _write_csv(output/'summary.csv',summaries);_write_csv(output/'paired_comparisons.csv',pairs)
    write_json(output/'best_solutions.json',[dict(instance_id=r['result']['instance_id'],seed=r['result']['seed'],
        method=r['result']['method'],makespan=r['result']['makespan'],routes=r['best_routes'],per_robot_costs=r['per_robot_costs']) for r in records])
    plot(output,records)
    lines=['# E12 literature baseline development comparison','',
        'All four literature baselines are adapted implementations, not author-code reproductions. See source comparison_algorithms/ADAPTATIONS.md. Four manifest-qualified development instances × two seeds × six methods; no test/validation solves and no LLM requests.','',
        'The same nominal task_count-second budget includes state/matrix setup, candidate imports, population initialization and search. B1/Proposed core implementations are unchanged; their solve budget is reduced by measured setup time. Atomic moves/ALNS iterations may overrun the deadline. Independent final verification is excluded.','',
        '| Method | Mean makespan | Runtime (s) | Cycles/generations | Proposed paired gain | W/T/L |',
        '|---|---:|---:|---:|---:|---|']
    for s in summaries:
        if s['dimension']!='overall':continue
        p=next((p for p in pairs if p['dimension']=='overall' and p['reference']==s['method']),None)
        tail=f"{p['paired_improvement_pct']:+.3f}% | {p['wins']}/{p['ties']}/{p['losses']}" if p else '— | —'
        lines.append(f"| {s['method']} | {s['mean_makespan']:.3f} | {s['mean_runtime_seconds']:.3f} | {s['mean_iterations']:.1f} | {tail} |")
    lines+=['','Cycles differ in meaning across algorithms; use elapsed-time convergence for comparisons. Small sample confounds scale and scenario; no significance or generalization claims. The Proposed is the unmodified E11 AUX identity; no selection/tuning used E12 outcomes.','',
        f"Final feasible records: {len(rows)}; runtime fallbacks: {sum(r['fallback_count'] for r in rows)}; max budget overrun: {max(r['budget_overrun_seconds'] for r in rows):.3f}s.",'',
        '## Instance means (two seeds)','', '| Instance | '+' | '.join(METHODS)+' |','|---|'+'---:|'*len(METHODS)]
    for entry in config['entries']:
        values=[mean(r['makespan'] for r in rows if r['instance_id']==entry['instance_id'] and r['method']==m) for m in METHODS]
        lines.append('| '+entry['instance_id']+' | '+' | '.join(f'{v:.3f}' for v in values)+' |')
    lines+=['','## Reproduce','', '```powershell',"$env:PYTHONPATH='src'",
        r"& 'G:\Anaconda\envs\mrta_env\python.exe' -m pytest tests/test_comparison_algorithms.py tests/test_e12_comparison.py -q",
        r"& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e12_comparison --stage run",
        r"& 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e12_comparison --stage analyze",'```','',
        'Existing run records resume without replacement. Use --output with a fresh directory for independent measurements. Config JSON includes all parameters, PDF/source hashes and E11 identities. Runs retain complete best routes, histories, generated execution and fallbacks.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_json(output/'verification.json',dict(records=len(rows),feasible=len(rows),independent_dp_recheck=True,
        test_accessed=False,validation_accessed=False,llm_calls=0,frozen_e11_verified=True,
        runner_sha256=byte_hash(Path(__file__)),max_budget_overrun=max(r['budget_overrun_seconds'] for r in rows)))
    print('\n'.join(lines[:18]),flush=True)


def plot(output,records):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'pdf.fonttype':42,'ps.fonttype':42})
    fig,axes=plt.subplots(1,2,figsize=(10.8,3.9))
    for ax,index in zip(axes,(0,3)):
        entry=entries()[index]
        for method in METHODS:
            record=next(r for r in records if r['result']['instance_id']==entry['instance_id'] and r['result']['seed']==0 and r['result']['method']==method)
            history=record['history']
            ax.step([h['elapsed_seconds'] for h in history],[h['best_makespan'] for h in history],where='post',label=method,
                linewidth=2 if method=='Proposed' else 1.2)
        ax.set(title=entry['instance_id'].removeprefix('development/'),xlabel='Total elapsed time (s)',ylabel='Best makespan')
        ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    axes[1].legend(fontsize=8,ncol=2);fig.tight_layout()
    fig.savefig(output/'convergence.png',dpi=300);fig.savefig(output/'convergence.svg');plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('run','analyze'),required=True)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    globals()[args.stage](args.output.resolve())


if __name__=='__main__':main()
