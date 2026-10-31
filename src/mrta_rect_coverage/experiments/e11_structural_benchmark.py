"""Manifest-driven E11 screening; frozen solvers, no provider or test execution."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import math
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter

from .e3_alns import ROOT, write_json
from .e5_destroy_repair import read, digest, D_NAME, R_NAME
from .e6_pair_selection import config_for
from .e8_repair_portfolio import portfolio_solver, repair_usage, AUX_NAME
from .e10b_structural_dp_analysis import evaluator_for
from .e2_c1_pilot import _write_csv
from ..core.instance_loader import load_instance
from ..core.state_generator import generate_all_states
from ..core.models import MultiRobotSolution
from ..heuristics.alns_solver import ALNSSolver

DATA=ROOT/'data/structural_benchmark_v1'
METHODS=('B1','V1','AUX')
SEEDS=(0,1)
# Fixed by coverage before observing new results. A small screening, not a factorial study.
SAMPLES={
    'development':('BASE/R2_T10_0','HV-GEOM/R2_T20_0','SPATIAL/R4_T40_0',
                   'BOTTLENECK/R4_T60_0','TURN-HIGH/R8_T80_0','TRAVEL-HIGH/R8_T100_0',
                   'SWEEP-NARROW/R4_T40_0'),
    'validation':('BASE/R2_T10_0','BOTTLENECK/R4_T40_0','HV-GEOM/R8_T100_0'),
}


def byte_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def catalog():
    d=read(DATA/'manifest.json');rows=d['entries']
    if len(rows)!=336 or len({r['instance_id'] for r in rows})!=336 or len({r['path'] for r in rows})!=336:
        raise ValueError('manifest identity/count mismatch')
    if Counter(r['split'] for r in rows)!=dict(development=84,validation=84,test=168):
        raise ValueError('manifest split mismatch')
    for r in rows:
        p=(DATA/r['path']).resolve()
        if not p.is_relative_to(DATA.resolve()) or not r['instance_id'].startswith(r['split']+'/'):
            raise ValueError('invalid manifest identity/path')
    return d


def load_entry(entry):
    if entry['split'] not in SAMPLES:raise ValueError('test instances are not opened in E11')
    p=DATA/entry['path']
    if byte_hash(p)!=entry['sha256']:raise ValueError('instance hash mismatch')
    inst=load_instance(p)
    if (inst.robot_count,inst.task_count)!=(entry['n_robots'],entry['n_tasks']):raise ValueError('size mismatch')
    if any(getattr(inst,k)!=v for k,v in entry['params'].items()):raise ValueError('parameter mismatch')
    inst.name=entry['instance_id']
    return inst


def sample(split):
    if split not in SAMPLES:raise ValueError('only development and validation supported')
    index={e['instance_id']:e for e in catalog()['entries']}
    return [index[split+'/'+suffix] for suffix in SAMPLES[split]]


def identities():
    d=read(ROOT/'outputs/e8_repair_portfolio/selection_decision.json')
    for k in ('destroy','main','aux'):
        if digest(d[k]['source_path'])!=d[k]['source_hash']:raise ValueError('frozen operator changed')
    return {k:{f:d[k][f] for f in ('source_path','source_hash','operator_id','generation')} for k in ('destroy','main','aux')}


def make_solver(instance,seed,method,*,executor='original',config_overrides=None):
    if method not in METHODS:raise ValueError(method)
    if method=='B1':
        config=config_for(instance,seed,'B1+R',overrides=config_overrides)
        return ALNSSolver(instance,constructor='spatial_sort',config=config)
    d=identities()
    return portfolio_solver(instance,seed,dict(destroy=d['destroy'],repair=d['main']),d['aux'],method,executor=executor,config_overrides=config_overrides)


def setup(output):
    output.mkdir(parents=True,exist_ok=True);p=output/'experiment_config.json'
    if not p.exists():
        frozen=[DATA/'manifest.json',DATA/'intrinsic_features.csv',ROOT/'configs/e3_b1.yaml']
        frozen += [ROOT/'src/mrta_rect_coverage'/f for f in ('heuristics/alns_solver.py','core/dp_evaluator.py',
            'core/state_generator.py','core/instance_loader.py','core/models.py','llm/operator_evolution/candidate_execution.py',
            'experiments/e6_pair_selection.py','experiments/e8_repair_portfolio.py')]
        write_json(p,dict(stage='E11 development screening',git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            dataset_version=catalog()['dataset_version'],manifest_sha256=byte_hash(DATA/'manifest.json'),
            archive_sha256=byte_hash(ROOT/'data/MR_RCRP_Structural_Benchmark_v1.zip'),
            samples={s:sample(s) for s in SAMPLES},seeds=SEEDS,methods=METHODS,operators=identities(),
            base_config=asdict(config_for(load_entry(sample('development')[0]),0,'B1+R')),
            alpha_seconds_per_task=1.0,constructor='spatial_sort',pools=dict(B1=[3,3],V1=[4,4],AUX=[4,4]),
            timing='solve timer, boundaries between iterations; setup excluded and separately recorded; serial runs',
            order='instance/seed; cyclic method order per instance, reversed for seed 1',
            selection_rule='AUX is preferred if its paired mean gain vs V1 is nonnegative on development and validation, all final solutions feasible, and generated-call failure rate <=1% on each split. Otherwise retain V1. No parameter tuning or repeat selection. B1 is a comparator, not a candidate LLM version.',
            test_policy='metadata inventory only: no test TXT opened, compatibility evaluated or ALNS run',
            compatibility='all 168 development+validation inputs through real loader, state generator and complete fixed-route DP',
            frozen_hashes={str(f):byte_hash(f) for f in frozen},llm_calls=0))
    cfg=read(p)
    if cfg['operators']!=identities():raise ValueError('operator identity mismatch')
    for f,h in cfg['frozen_hashes'].items():
        if byte_hash(f)!=h:raise ValueError(f'frozen input changed: {f}')
    return cfg


def compatibility(output):
    cfg=setup(output);rows=[]
    for entry in catalog()['entries']:
        if entry['split']=='test':continue
        started=perf_counter();inst=load_entry(entry)
        assert all(math.isfinite(v) for t in inst.tasks for v in (t.x_left,t.x_right,t.y_bottom,t.y_top))
        assert all(t.x_left>=0 and t.y_bottom>=0 for t in inst.tasks)
        for i,a in enumerate(inst.tasks):
            for b in inst.tasks[i+1:]:
                assert min(a.x_right,b.x_right)-max(a.x_left,b.x_left)<=1e-8 or min(a.y_top,b.y_top)-max(a.y_bottom,b.y_bottom)<=1e-8
        states=generate_all_states(inst)
        assert all(len(ss)==8 for ss in states.values())
        assert all(math.isfinite(s.processing_time) and s.processing_time>0 for ss in states.values() for s in ss)
        routes=[[] for _ in range(inst.robot_count)]
        for i,t in enumerate(inst.tasks):routes[i%inst.robot_count].append(t.task_id)
        ev=evaluator_for(inst);cost=ev.evaluate(MultiRobotSolution(routes))
        assert math.isfinite(cost.makespan) and sum(len(r.chosen_states) for r in cost.route_evaluations)==inst.task_count
        rows.append(dict(instance_id=entry['instance_id'],split=entry['split'],scenario=entry['scenario'],
            tasks=inst.task_count,robots=inst.robot_count,state_count=8*inst.task_count,feasible=True,
            fixed_route_makespan=cost.makespan,seconds=perf_counter()-started))
        if len(rows)%14==0:print(f'Compatibility {len(rows)}/168',flush=True)
    _write_csv(output/'compatibility.csv',rows)
    write_json(output/'compatibility_summary.json',dict(dataset_version=cfg['dataset_version'],verified=len(rows),
        splits=dict(Counter(r['split'] for r in rows)),test_instances_opened=0,all_compatible=True,
        route_evaluation='fixed round-robin routes, compatibility only; not optimized results'))


def run(output,split):
    cfg=setup(output)
    if not (output/'compatibility_summary.json').exists():raise ValueError('run compatibility first')
    for i,e in enumerate(cfg['samples'][split]):
        for seed in SEEDS:
            order=METHODS[i%3:]+METHODS[:i%3]
            if seed:order=tuple(reversed(order))
            initial=None
            for method in order:
                path=output/'runs'/e['instance_id']/f'{method}_s{seed}.json'
                if path.exists():
                    d=read(path);assert d['entry']==e and d['operators']==cfg['operators']
                else:
                    started=perf_counter();inst=load_entry(e);solver=make_solver(inst,seed,method)
                    setup_seconds=perf_counter()-started
                    result=solver.solve();verified=solver.solution_evaluator.evaluate(result.best_solution)
                    assert verified.makespan==result.best_evaluation.makespan
                    executions=[x for g in result.generated_operator_execution.values() for x in g.values()]
                    r=dict(instance_id=e['instance_id'],split=split,scenario=e['scenario'],tasks=e['n_tasks'],robots=e['n_robots'],
                        size=f"R{e['n_robots']}_T{e['n_tasks']}",seed=seed,method=method,makespan=verified.makespan,
                        initial_makespan=result.initial_makespan,runtime_seconds=result.runtime_seconds,setup_seconds=setup_seconds,
                        iterations=result.iterations_completed,route_dp_calls=result.route_dp_calls,cache_misses=result.route_dp_cache_misses,
                        feasible=True,fallback_count=len(result.fallback_events),status='fallback' if result.fallback_events else 'ok',
                        generated_calls=sum(x['calls'] for x in executions),generated_failures=sum(x['failures'] for x in executions),
                        llm_destroy_uses=sum(h['destroy']==D_NAME for h in result.iteration_history),
                        llm_repair_uses=sum(h['repair'] in (R_NAME,AUX_NAME) for h in result.iteration_history))
                    d=dict(result=r,entry=e,operators=cfg['operators'],config=asdict(solver.config),
                        initial_routes=solver.initial_solution.routes,best_routes=result.best_solution.routes,
                        per_robot_costs=verified.per_robot_costs,history=result.iteration_history,
                        repair_usage=repair_usage(result.iteration_history,result.initial_makespan),
                        pools=dict(destroy=list(solver.destroy_ops),repair=list(solver.repair_ops)),
                        generated_execution=result.generated_operator_execution,fallback_events=result.fallback_events,
                        timing=result.timing_breakdown_seconds)
                    write_json(path,d)
                    print(f"{e['instance_id']} s{seed} {method}: {r['makespan']:.3f}, iterations={r['iterations']}, fallback={r['fallback_count']}",flush=True)
                assert d['config']==asdict(config_for(load_entry(e),seed,'B1+R' if method=='B1' else 'V1'))
                if initial is None:initial=d['initial_routes']
                assert initial==d['initial_routes']


def comparison(rows,method,base):
    a={(r['instance_id'],r['seed']):r for r in rows if r['method']==method}
    b={(r['instance_id'],r['seed']):r for r in rows if r['method']==base}
    if a.keys()!=b.keys() or not a:raise ValueError('missing paired measurements')
    deltas=[100*(1-a[k]['makespan']/b[k]['makespan']) for k in sorted(a)]
    return dict(method=method,reference=base,pairs=len(a),paired_improvement_pct=mean(deltas),
        wins=sum(x>1e-8 for x in deltas),ties=sum(abs(x)<=1e-8 for x in deltas),losses=sum(x< -1e-8 for x in deltas))


def analyze(output):
    cfg=setup(output);rows=[]
    for split,es in cfg['samples'].items():
        for e in es:
            ev=evaluator_for(load_entry(e))
            for seed in SEEDS:
                initial=None
                for method in METHODS:
                    d=read(output/'runs'/e['instance_id']/f'{method}_s{seed}.json');r=d['result']
                    assert d['entry']==e and d['operators']==cfg['operators']
                    assert d['config']==asdict(config_for(load_entry(e),seed,'B1+R' if method=='B1' else 'V1'))
                    v=ev.evaluate(MultiRobotSolution(d['best_routes']));assert abs(v.makespan-r['makespan'])<1e-8
                    assert r['feasible'] and r['iterations']==len(d['history'])
                    assert (len(d['pools']['destroy']),len(d['pools']['repair']))==tuple(cfg['pools'][method])
                    if initial is None:initial=d['initial_routes']
                    assert initial==d['initial_routes'];rows.append(r)
    _write_csv(output/'results.csv',rows)
    aggregates=[];pairs=[]
    for split in SAMPLES:
        group=[r for r in rows if r['split']==split]
        for dimension in ('overall','size','scenario'):
            for label in (['all'] if dimension=='overall' else sorted({r[dimension] for r in group})):
                subset=[r for r in group if dimension=='overall' or r[dimension]==label]
                for m in METHODS:
                    rs=[r for r in subset if r['method']==m]
                    aggregates.append(dict(split=split,dimension=dimension,label=label,method=m,runs=len(rs),
                        **{f'mean_{k}':mean(r[k] for r in rs) for k in ('makespan','runtime_seconds','iterations','route_dp_calls','cache_misses','llm_destroy_uses','llm_repair_uses')},
                        fallback_count=sum(r['fallback_count'] for r in rs)))
                for m,b in (('V1','B1'),('AUX','B1'),('AUX','V1')):
                    pairs.append(dict(split=split,dimension=dimension,label=label,**comparison(subset,m,b)))
    _write_csv(output/'summary.csv',aggregates);_write_csv(output/'paired_comparisons.csv',pairs)
    eligibility={}
    for split in SAMPLES:
        aux=[r for r in rows if r['split']==split and r['method']=='AUX']
        gain=comparison([r for r in rows if r['split']==split],'AUX','V1')['paired_improvement_pct']
        failure_rate=sum(r['generated_failures'] for r in aux)/max(1,sum(r['generated_calls'] for r in aux))
        eligibility[split]=dict(gain_vs_V1_pct=gain,generated_failure_rate=failure_rate,eligible=gain>=0 and failure_rate<=.01)
    chosen='AUX' if all(r['eligible'] for r in eligibility.values()) else 'V1'
    write_json(output/'algorithm_freeze.json',dict(recommended_proposed=chosen,eligibility=eligibility,
        selection_rule=cfg['selection_rule'],operators=cfg['operators'],deployed_destroy=cfg['operators']['destroy'],
        deployed_repair=cfg['operators']['aux' if chosen=='AUX' else 'main'],dataset_version=cfg['dataset_version'],
        manifest_sha256=cfg['manifest_sha256'],parameters=asdict(config_for(load_entry(sample('development')[0]),0,'V1')),
        parameter_substitution='max_runtime_seconds = task_count; random_seed = each frozen seed',alpha_seconds_per_task=1.0,
        initial_constructor='spatial_sort',seeds=SEEDS,pools=cfg['pools'][chosen],selector='independent',
        no_test_execution=True,scope='configuration frozen for next comparison; pilot selection is not confirmation',
        experiment_config_sha256=byte_hash(output/'experiment_config.json')))
    write_json(output/'verification.json',dict(complete_feasible_runs=len(rows),test_runs=0,llm_calls=0,
        independently_reevaluated=True,same_initial_routes_within_pair=True,frozen_hashes_verified=True,
        fallbacks=sum(r['fallback_count'] for r in rows),runner_hash=byte_hash(Path(__file__)),
        setup_failure_records=[read(p) for p in sorted(output.glob('setup_failure_*.json'))]))
    lines=['# E11 structural benchmark screening','',f'Data: {cfg["dataset_version"]}; 7 development and 3 validation instances, seeds 0/1; 60 serial full solves. No test TXT opened or test optimization. See compatibility_summary.json for the 168 non-test compatibility checks.','',
        'The sample was fixed by coverage before results. Seven development instances cover six scales and seven scenarios, but scale and scenario are confounded. Per-size and per-scenario tables are descriptive screening, not isolated structural effects; seeds are repeated measures. B1 has 3x3 operator pools; V1/AUX have 4x4. All frozen operator identifiers, full hashes and actual configurations are retained.','',
        '| Split | Method | Mean makespan | Runtime (s) | Iterations |','|---|---|---:|---:|---:|']
    for r in aggregates:
        if r['dimension']=='overall':lines.append(f"| {r['split']} | {r['method']} | {r['mean_makespan']:.3f} | {r['mean_runtime_seconds']:.3f} | {r['mean_iterations']:.2f} |")
    lines+=['','## Paired comparisons','', '| Split | Method vs reference | Mean paired gain | W/T/L |','|---|---|---:|---|']
    for r in pairs:
        if r['dimension']=='overall':lines.append(f"| {r['split']} | {r['method']} vs {r['reference']} | {r['paired_improvement_pct']:+.3f}% | {r['wins']}/{r['ties']}/{r['losses']} |")
    for dimension in ('size','scenario'):
        lines+=['',f'## Development by {dimension}','',
            '| Group | B1 makespan | V1 makespan | AUX makespan | AUX vs V1 | AUX vs B1 |',
            '|---|---:|---:|---:|---:|---:|']
        for label in sorted({r['label'] for r in aggregates if r['split']=='development' and r['dimension']==dimension}):
            rs={r['method']:r for r in aggregates if r['split']=='development' and r['dimension']==dimension and r['label']==label}
            ps={r['reference']:r for r in pairs if r['split']=='development' and r['dimension']==dimension and r['label']==label and r['method']=='AUX'}
            lines.append(f"| {label} | {rs['B1']['mean_makespan']:.3f} | {rs['V1']['mean_makespan']:.3f} | {rs['AUX']['mean_makespan']:.3f} | {ps['V1']['paired_improvement_pct']:+.3f}% | {ps['B1']['paired_improvement_pct']:+.3f}% |")
    lines+=['',f'Frozen Proposed recommendation: **{chosen}**. Selection checks: {eligibility}. No parameter optimization. Freeze alpha=1 second/task; fixed B1 segment/SA/local-search controls. Fallbacks remain in primary data; no outcome-based reruns. Exact sources and hashes, parameters and seeds are in algorithm_freeze.json.',
        '',f"Initialization failures before solve: {len(list(output.glob('setup_failure_*.json')))}; recorded separately and resumed at unfinished records with the same configuration. These are not successful solver executions and are additional to the generated runtime failure-rate selection check. Existing completed solves were not repeated. This pilot does not establish deployment reliability under other machine loads.",
        '', '## Reproduce','', 'From repository root (existing records resume without replacing runs; use a fresh --output for an independent new measurement):','', '```powershell',"$env:PYTHONPATH='src'",
        "foreach ($stage in @('compatibility','development','validation','analyze')) {",
        r"  & 'G:\Anaconda\envs\mrta_env\python.exe' -m mrta_rect_coverage.experiments.e11_structural_benchmark --stage $stage",
        '  if ($LASTEXITCODE -ne 0) { throw "E11 failed at $stage" }','}','```','',
        'results.csv retains individual outcomes, summary.csv groups by size/scenario, paired_comparisons.csv averages matched ratios rather than ratios of means. Full routes, convergence, generated executions and fallback details are retained in runs/. This stage stops before test.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Recommendation',chosen,'checks',eligibility,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=('compatibility','development','validation','analyze'),required=True)
    p.add_argument('--output',type=Path,default=ROOT/'outputs/e11_structural_benchmark')
    a=p.parse_args();o=a.output.resolve()
    if a.stage in SAMPLES:run(o,a.stage)
    else:globals()[a.stage](o)


if __name__=='__main__':main()
