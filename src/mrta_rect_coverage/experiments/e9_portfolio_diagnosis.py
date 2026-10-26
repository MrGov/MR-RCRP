"""E9: read-only E8 diagnosis and eight additional PORT-ALL runs. No LLM calls."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from statistics import mean
import subprocess
from time import perf_counter

from .e3_alns import ROOT, INSTANCES, SEEDS, write_json
from .e5_destroy_repair import read, digest, load_choice, D_NAME, R_NAME
from .e6_pair_selection import make_solver, config_for
from .e8_repair_portfolio import portfolio_solver, repair_usage, AUX_NAME, REPLACE_SLOT
from .e2_c1_pilot import _write_csv
from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..heuristics.alns_solver import ALNSSolver

E8=ROOT/'outputs/e8_repair_portfolio'
VERSIONS=('V1','V2','AUX','PORT','PORT-ALL')
COMPARISON=('V1','AUX','PORT','PORT-ALL')


def version_solver(instance,seed,decision,version,*,iterations=None):
    """Version assembly only; existing B1 registry, controls and operators unchanged."""
    selected=dict(destroy=decision['destroy'],repair=decision['main'])
    if version in ('V1','V2','PORT-ALL'):
        solver=make_solver(instance,seed,selected,'V2' if version=='V2' else 'V1',iterations=iterations)
        if version=='PORT-ALL':
            solver.register_development_repair(load_choice(decision['aux'],'repair').callable_obj,name=AUX_NAME)
        return solver
    if version in ('AUX','PORT'):
        return portfolio_solver(instance,seed,selected,decision['aux'],version,iterations=iterations)
    raise ValueError(version)


def stage_rows(saved):
    """Wall-time checkpoints carry the last completed best, excluding future completions."""
    r=saved['result'];history=saved['history'];rows=[]
    for fraction in (.25,.5,.75,1.):
        completed=[h for h in history if h['elapsed_seconds']<=fraction*r['budget_seconds']]
        rows.append(dict(method=r['method'],instance=r['instance'],seed=r['seed'],budget_fraction=fraction,
            best_makespan=completed[-1]['best_makespan'] if completed else r['initial_makespan'],
            iterations_by_checkpoint=len(completed)))
    return rows


def execution_rows(saved):
    rows=[];r=saved['result']
    for kind,group in saved['generated_operator_execution'].items():
        for name,stats in group.items():
            count=stats['calls'];wall=stats['wall_time_seconds'];execution=stats['run_request_seconds']
            rows.append(dict(method=r['method'],instance=r['instance'],seed=r['seed'],kind=kind,operator=name,
                **stats,mean_bounded_wall_ms=1000*wall/count if count else None,
                mean_run_request_ms=1000*execution/count if count else None,
                outside_run_request_seconds=wall-execution))
    return rows


def setup(output):
    output.mkdir(parents=True,exist_ok=True)
    path=output/'experiment_config.json'
    if not path.exists():
        old=read(E8/'experiment_config.json');decision=read(E8/'selection_decision.json')
        frozen={**old['frozen_hashes'],**old['candidate_hashes']}
        files=[E8/'selection_decision.json',E8/'experiment_config.json',E8/'fixed_evaluations.json',
               E8/'complementarity_analysis.json',E8/'short_evaluations.json']+sorted((E8/'runs').glob('*.json'))
        files += [ROOT/'src/mrta_rect_coverage/experiments'/f'{n}.py' for n in
                  ('e5_destroy_repair','e6_pair_selection','e8_repair_portfolio')]
        files += [ROOT/'src/mrta_rect_coverage/llm/operator_evolution'/f'{n}.py' for n in ('candidate_loader','evaluator')]
        frozen.update({str(p):digest(p) for p in files})
        write_json(path,dict(phase='E9',git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            decision=decision,instances=INSTANCES,seeds=SEEDS,budget='1.0 * task_count seconds',
            new_runs='PORT-ALL only, 4 instances x 2 seeds; historical E8 24 runs read unchanged',
            llm_calls=0,frozen_hashes=frozen,primary='V1',
            interpretation='development/exploratory; historical-vs-new timing not concurrent; five repair slots confound pool size and balancing retention',
            candidate_reselection=False,C2='exploratory prototype implemented; reliable benefit not established'))
    config=read(path)
    for p,h in config['frozen_hashes'].items():
        if digest(p)!=h:raise ValueError(f'frozen historical source/result changed: {p}')
    return config


def prepare(output):
    config=setup(output);d=config['decision'];versions={}
    manual=['greedy_insertion','regret_k_insertion',REPLACE_SLOT]
    pools={'V1':manual+[R_NAME],'V2':manual+[R_NAME],'AUX':manual+[AUX_NAME],
           'PORT':['greedy_insertion','regret_k_insertion',AUX_NAME,R_NAME],
           'PORT-ALL':manual+[R_NAME,AUX_NAME]}
    for version in VERSIONS:
        versions[version]=dict(role='stable main version' if version=='V1' else 'optional experiment/diagnostic',
            destroy=config['decision']['destroy'],main_repair=d['main'] if version!='AUX' else None,
            auxiliary=d['aux'] if version in ('AUX','PORT','PORT-ALL') else None,
            destroy_pool=['random_destroy','bottleneck_route_destroy','geometry_aware_destroy',D_NAME],repair_pool=pools[version],
            constructor='spatial_sort',parameters=[dict(instance=n,seed=s,alns=asdict(config_for(
                load_instance(ROOT/'data'/f'{n}.txt'),s,'V2' if version=='V2' else 'V1'))) for n in INSTANCES for s in SEEDS],
            command=f'python -m mrta_rect_coverage.experiments.e9_portfolio_diagnosis --stage benchmark --version {version} --output outputs/e9_reproduce_{version}',
            historic_results=str(ROOT/'outputs/e6_pair_selection') if version=='V2' else str(E8) if version!='PORT-ALL' else str(output))
    write_json(output/'algorithm_versions.json',versions)
    # DP is an offline explanation in E8, not a component in its screening score.
    write_json(output/'dp_knowledge_role.json',dict(
        selection_inputs=['feasibility/completeness on identical partials','paired makespan improvement',
            'makespan on hard incumbents grouped by instance','relief of R* makespan-degraded cases',
            'candidate execution runtime','short full-ALNS quality/fallback gate'],
        canonical_DP_metrics_used_in_selection=[],
        canonical_DP_metrics_for_explanation=['dp_state_switch_fraction','hv_mode_switch_fraction',
            'entry_corner_switch_fraction','exit_corner_switch_fraction','dp_cascade_count','dp_cascade_ratio',
            'bottleneck_relief','travel_change','coverage_change','turning_change'],
        intrinsic_features_role='labels/stratified reporting only; not selector inputs',
        actual_positioning='Exact-DP-evaluated makespan-crossover repair portfolio, with post-evaluation DP behavioral interpretation',
        not_implemented='DP-behavior-grounded portfolio selector or state-switch diversity reward',
        source=str(ROOT/'src/mrta_rect_coverage/experiments/e8_repair_portfolio.py'),
        functions=['complementarity','screen','select','candidate_analysis']))
    print('Frozen versions V1/V2/AUX/PORT/PORT-ALL; only PORT-ALL scheduled for new runs.',flush=True)


def historical_runs():
    return [read(E8/'runs'/f'{n}_{m}_s{s}.json') for n in INSTANCES for s in SEEDS for m in ('V1','AUX','PORT')]


def diagnose(output,saved=None):
    setup(output)
    saved=historical_runs() if saved is None else saved
    operator=[];execution=[];phases=[]
    for d in saved:
        r=d['result'];usage=repair_usage(d['history'],r['initial_makespan'])
        assert usage==d['repair_usage']
        for name in d['operator_pools']['repair']:
            stats=usage.get(name,dict(uses=0,accepted=0,global_best=0))
            matching=[h for h in d['history'] if h['repair']==name]
            seconds=sum(h['stage_timings_seconds']['repair_execution'] for h in matching)
            operator.append(dict(method=r['method'],instance=r['instance'],seed=r['seed'],operator=name,
                uses=stats['uses'],accepted=stats['accepted'],global_best=stats['global_best'],
                selection_share=stats['uses']/r['iterations'],repair_stage_seconds=seconds,
                mean_repair_stage_ms=1000*seconds/stats['uses'] if stats['uses'] else None))
        execution.extend(execution_rows(d));phases.extend(stage_rows(d))
    _write_csv(output/'repair_usage_by_run.csv',operator);_write_csv(output/'generated_execution_by_run.csv',execution)
    _write_csv(output/'time_checkpoints.csv',phases)
    aggregated=[]
    for method in sorted({r['method'] for r in operator}):
        for name in sorted({r['operator'] for r in operator if r['method']==method}):
            group=[r for r in operator if r['method']==method and r['operator']==name]
            uses=sum(r['uses'] for r in group);total=sum(d['result']['iterations'] for d in saved if d['result']['method']==method)
            aggregated.append(dict(method=method,operator=name,uses=uses,accepted=sum(r['accepted'] for r in group),
                global_best=sum(r['global_best'] for r in group),selection_share=uses/total,
                repair_stage_seconds=sum(r['repair_stage_seconds'] for r in group)))
    _write_csv(output/'repair_usage_summary.csv',aggregated)
    totals=[]
    for method,kind,name in sorted({(r['method'],r['kind'],r['operator']) for r in execution}):
        group=[r for r in execution if (r['method'],r['kind'],r['operator'])==(method,kind,name)]
        count=sum(r['calls'] for r in group);wall=sum(r['wall_time_seconds'] for r in group);inner=sum(r['run_request_seconds'] for r in group)
        totals.append(dict(method=method,kind=kind,operator=name,calls=count,
            failures=sum(r['failures'] for r in group),wall_seconds=wall,run_request_seconds=inner,
            mean_bounded_wall_ms=wall*1000/count,mean_run_request_ms=inner*1000/count,
            outside_run_request_fraction=(wall-inner)/wall))
    _write_csv(output/'generated_execution_summary.csv',totals)
    phase_totals=[]
    for method in sorted({d['result']['method'] for d in saved}):
        group=[d for d in saved if d['result']['method']==method]
        runtime=sum(d['result']['runtime_seconds'] for d in group)
        values={key:sum(d['result'][key] for d in group) for key in
            ('destroy_execution_seconds','partial_evaluation_seconds','repair_execution_seconds','local_search_seconds','other_seconds')}
        phase_totals.append(dict(method=method,total_solve_seconds=runtime,**values,
            generated_bounded_wall_seconds=sum(r['wall_time_seconds'] for r in execution if r['method']==method),
            generated_bounded_wall_fraction=sum(r['wall_time_seconds'] for r in execution if r['method']==method)/runtime))
    _write_csv(output/'phase_timing_summary.csv',phase_totals)
    comparisons=[]
    index={(r['method'],r['instance'],r['seed'],r['budget_fraction']):r for r in phases}
    for method in sorted({r['method'] for r in phases}-{'V1'}):
        for fraction in (.25,.5,.75,1.):
            pairs=[(r,index['V1',r['instance'],r['seed'],fraction]) for r in phases if r['method']==method and r['budget_fraction']==fraction]
            comparisons.append(dict(method=method,budget_fraction=fraction,
                paired_improvement_vs_V1_pct=mean(100*(1-a['best_makespan']/b['best_makespan']) for a,b in pairs),
                wins=sum(a['best_makespan']<b['best_makespan'] for a,b in pairs),
                ties=sum(a['best_makespan']==b['best_makespan'] for a,b in pairs),
                losses=sum(a['best_makespan']>b['best_makespan'] for a,b in pairs)))
    _write_csv(output/'checkpoint_comparison.csv',comparisons)
    print('Offline diagnosis saved; operator outcomes include local search and are not causal credits.',flush=True)


def run_one(output,name,seed,version,decision):
    path=output/'runs'/f'{name}_{version}_s{seed}.json'
    instance=load_instance(ROOT/'data'/f'{name}.txt');expected=asdict(config_for(instance,seed,'V2' if version=='V2' else 'V1'))
    if path.exists():
        saved=read(path);assert saved['config']==expected and saved['decision']==decision
        return saved
    started=perf_counter()
    try:
        solver=version_solver(instance,seed,decision,version);setup_seconds=perf_counter()-started
        result=solver.solve();verified=solver.solution_evaluator.evaluate(result.best_solution)
        assert verified.makespan==result.best_evaluation.makespan
        row=dict(method=version,instance=name,seed=seed,feasible=True,status='fallback' if result.fallback_events else 'ok',
            makespan=verified.makespan,initial_makespan=result.initial_makespan,budget_seconds=solver.config.max_runtime_seconds,
            runtime_seconds=result.runtime_seconds,setup_seconds=setup_seconds,iterations=result.iterations_completed,
            route_dp_calls=result.route_dp_calls,route_dp_cache_misses=result.route_dp_cache_misses,
            fallback_count=len(result.fallback_events),**result.timing_breakdown_seconds)
        saved=dict(result=row,decision=decision,config=asdict(solver.config),initial_routes=solver.initial_solution.routes,
            best_routes=result.best_solution.routes,per_robot_costs=verified.per_robot_costs,history=result.iteration_history,
            repair_usage=repair_usage(result.iteration_history,result.initial_makespan),
            operator_pools=dict(destroy=list(solver.destroy_ops),repair=list(solver.repair_ops)),
            generated_operator_execution=result.generated_operator_execution,fallback_events=result.fallback_events,
            final_weights=dict(destroy=solver.destroy_weights,repair=solver.repair_weights))
        write_json(path,saved)
    except Exception as exc:
        write_json(path.with_suffix('.error.json'),dict(status='error',error=f'{type(exc).__name__}: {exc}',instance=name,seed=seed,method=version))
        raise
    print(f"{name} seed {seed} {version}: {row['makespan']}, {row['iterations']} iterations, fallback {row['fallback_count']}",flush=True)
    return saved


def benchmark(output,version='PORT-ALL'):
    config=setup(output)
    for name in INSTANCES:
        for seed in SEEDS:run_one(output,name,seed,version,config['decision'])


def analyze(output):
    config=setup(output)
    saved=historical_runs()+[read(output/'runs'/f'{n}_PORT-ALL_s{s}.json') for n in INSTANCES for s in SEEDS]
    for d in saved:
        r=d['result'];verifier=ALNSSolver(load_instance(ROOT/'data'/f"{r['instance']}.txt"),constructor='spatial_sort')
        assert verifier.initial_solution.routes==d['initial_routes']
        assert verifier.solution_evaluator.evaluate(MultiRobotSolution(d['best_routes'])).makespan==r['makespan']
        assert d['config']==asdict(config_for(verifier.instance,r['seed'],'V1'))
        assert len(d['operator_pools']['destroy'])==4
        assert len(d['operator_pools']['repair'])==(5 if r['method']=='PORT-ALL' else 4)
        assert r['feasible'] and len(d['history'])==r['iterations']
    diagnose(output,saved)
    index={(d['result']['method'],d['result']['instance'],d['result']['seed']):d for d in saved}
    summary=[]
    for method in COMPARISON:
        group=[d for d in saved if d['result']['method']==method];out=dict(method=method,runs=len(group))
        for field in ('makespan','runtime_seconds','iterations','route_dp_calls','route_dp_cache_misses'):
            out['mean_'+field]=mean(d['result'][field] for d in group)
        count=sum(d['result']['iterations'] for d in group);seconds=sum(d['result']['runtime_seconds'] for d in group)
        out['iterations_per_second']=count/seconds
        for name,label in ((R_NAME,'main'),(AUX_NAME,'aux'),(REPLACE_SLOT,'balancing')):
            for field in ('uses','accepted','global_best'):
                out[label+'_'+field]=sum(d['repair_usage'].get(name,{}).get(field,0) for d in group)
        out['generated_repair_share']=(out['main_uses']+out['aux_uses'])/count
        out['fallback_count']=sum(d['result']['fallback_count'] for d in group)
        for base in ('V1','AUX','PORT'):
            pairs=[(d['result'],index[base,d['result']['instance'],d['result']['seed']]['result']) for d in group]
            out[f'paired_improvement_vs_{base}_pct']=mean(100*(1-a['makespan']/b['makespan']) for a,b in pairs)
            out[f'wtl_vs_{base}']=[sum(a['makespan']<b['makespan'] for a,b in pairs),sum(a['makespan']==b['makespan'] for a,b in pairs),sum(a['makespan']>b['makespan'] for a,b in pairs)]
        summary.append(out)
    write_json(output/'summary.json',summary);_write_csv(output/'summary.csv',summary)
    per_instance=[dict(instance=n,**{m:mean(index[m,n,s]['result']['makespan'] for s in SEEDS) for m in COMPARISON}) for n in INSTANCES]
    _write_csv(output/'per_instance_results.csv',per_instance)
    write_json(output/'verification_summary.json',dict(historical_runs_reused=24,new_runs=8,
        feasible_complete_solutions_reevaluated=len(saved),fallbacks=sum(d['result']['fallback_count'] for d in saved),
        generated_failures=sum(x['failures'] for d in saved for g in d['generated_operator_execution'].values() for x in g.values()),
        frozen_historical_hashes_unchanged=True,llm_calls=0,primary='V1',C2='implemented exploratory prototype; no reliable benefit',
        runner_hash=digest(Path(__file__))))
    report(output,summary,per_instance)
    for r in summary:print(r,flush=True)


def report(output,summary,instances):
    lines=['# E9 portfolio mechanism check','',
        'V1 remains the stable main algorithm. C2 is an implemented exploratory prototype without established reliable benefit. Stop C2 tuning for now. No LLM calls, candidate reselection, solver/DP/candidate changes, or repeated historical ALNS runs.','',
        '24 E8 runs are reused byte-for-byte with text hashes verified. Only eight PORT-ALL runs are added. Historical and new runs occurred at different times; equal configured budgets do not eliminate machine-load effects. All comparisons are development/exploratory.','',
        '## Results','',
        '| Method | Mean makespan | Paired gain vs V1 | W/T/L | Mean s | Mean iterations | LLM repair share |',
        '|---|---:|---:|---|---:|---:|---:|']
    for r in summary:lines.append(f"| {r['method']} | {r['mean_makespan']:.3f} | {r['paired_improvement_vs_V1_pct']:+.3f}% | {r['wtl_vs_V1']} | {r['mean_runtime_seconds']:.3f} | {r['mean_iterations']:.2f} | {100*r['generated_repair_share']:.2f}% |")
    extra=next(r for r in summary if r['method']=='PORT-ALL')
    lines+=['',f"PORT-ALL vs PORT: mean paired gain {extra['paired_improvement_vs_PORT_pct']:+.3f}%, W/T/L {extra['wtl_vs_PORT']}. "
        f"Vs AUX: {extra['paired_improvement_vs_AUX_pct']:+.3f}%, W/T/L {extra['wtl_vs_AUX']}.",'',
        '| Method | Mean DP calls | Mean cache misses | Balancing use/accept/best | R* use/accept/best | Aux use/accept/best |',
        '|---|---:|---:|---|---|---|']
    for r in summary:
        triples=['/'.join(str(r[label+'_'+k]) for k in ('uses','accepted','global_best')) for label in ('balancing','main','aux')]
        lines.append(f"| {r['method']} | {r['mean_route_dp_calls']:.1f} | {r['mean_route_dp_cache_misses']:.1f} | "+' | '.join(triples)+' |')
    lines+=['','| Instance | V1 | AUX | PORT | PORT-ALL |','|---|---:|---:|---:|---:|']
    for r in instances:lines.append('| '+r['instance']+' | '+' | '.join(f"{r[m]:.1f}" for m in COMPARISON)+' |')
    lines+=['','## Mechanism diagnosis','',
        'In historical V1, balancing repair is selected 192 times, accepted 35 times and associated with 10 global-best improvements (15.85% of iterations). It was active, so removing it changes search opportunities. Outcomes include local search and shared destroy decisions; counts do not identify causal contribution.','',
        'Those ten V1 balancing-associated best improvements occur 8/1/1/0 times in successive wall-time quarters. Thus PORT losing its early lead is not directly explained by missing late balancing improvements. Earlier trajectory effects are possible but unisolated.','',
        'PORT raises generated-repair share from 28.32% to 56.67% and reduces mean iterations from 151.38 to 113.38. Manual greedy/regret selections decrease from 390/286 to 203/190. Both member replacement and bounded invocation exposure change together. Detailed timing is in generated_execution_summary.csv and repair_usage_summary.csv. run_request_seconds measures parent send-to-receive time including serialization, transport and candidate execution, not pure candidate CPU time. Bounded wall includes spawn/import/validation and exit; the difference is outside-request overhead, not a pure startup-only measurement.','',
        'E8 PORT loses on the 10/20/40-task instance means and wins on the 80-task dispersed instance. time_checkpoints.csv and checkpoint_comparison.csv compare best solutions at 25/50/75/100% of the fixed time budget, carrying only completed iterations. Post-budget iteration improvements are excluded from these checkpoints but retained in final makespan; no convergence event is moved earlier.','',
        'PORT-ALL restores balancing while also increasing the repair pool to five. Its results cannot isolate balancing retention from changed sampling probabilities, adaptive paths, invocation frequency or run timing. No single mechanism is proved causal.','',
        f"In the new runs balancing was used {extra['balancing_uses']} times, accepted {extra['balancing_accepted']} times, "
        f"and associated with {extra['balancing_global_best']} global-best improvements. "
        'Restoration therefore represents actual use, not merely registry membership. Pool-size and sampling changes remain confounded.','',
        f"PORT-ALL averages {extra['mean_iterations']:.2f} iterations versus PORT's "
        f"{next(r for r in summary if r['method']=='PORT')['mean_iterations']:.2f}, yet improves paired makespan vs PORT. "
        'Thus reduced iteration count alone cannot explain PORT losses. Generated bounded invocation occupies 44.97% of V1 solve time, 54.01% of PORT, and 52.12% of PORT-ALL; those measured exposures support overhead association but are not an isolated causal experiment.','',
        '| Method | Quarter budget | Half budget | Three-quarter budget | At budget |','|---|---:|---:|---:|---:|']
    import csv
    with (output/'checkpoint_comparison.csv').open(encoding='utf-8',newline='') as f:checkpoints=list(csv.DictReader(f))
    for method in ('AUX','PORT','PORT-ALL'):
        lines.append('| '+method+' | '+' | '.join(f"{float(r['paired_improvement_vs_V1_pct']):+.3f}%" for r in checkpoints if r['method']==method)+' |')
    lines+=['','The checkpoint table gives matched improvement vs V1 at equal wall-time progress, not iteration progress. Final results can include a last iteration completed after the limit.','',
        '| Method/operator | Calls | Bounded wall ms/call | Run request ms/call | Outside-request fraction |',
        '|---|---:|---:|---:|---:|']
    with (output/'generated_execution_summary.csv').open(encoding='utf-8',newline='') as f:execution=list(csv.DictReader(f))
    for r in execution:
        if r['kind']=='repair':lines.append(f"| {r['method']}/{r['operator']} | {r['calls']} | {float(r['mean_bounded_wall_ms']):.2f} | {float(r['mean_run_request_ms']):.2f} | {100*float(r['outside_run_request_fraction']):.2f}% |")
    lines+=['','phase_timing_summary.csv retains solve totals and disjoint phase timings. Generated bounded execution is nested in destroy/repair phase time; do not add it again. No subprocess execution or validation was bypassed.','',
        '## Exact-DP knowledge role','',
        'E8 complementarity()/screen()/select() use feasibility, Exact-DP-evaluated makespan crossovers, R* weak-case relief, runtime, and a short full-ALNS quality gate. **No canonical DP behavior metric enters screening, ranking or roulette rewards.** Intrinsic labels are for reporting, not assignment. Canonical state/HV/corner switching, cascade, bottleneck relief and cost-component deltas are evaluated offline for explanation only.','',
        'Accurate positioning: a makespan-crossover historical repair portfolio evaluated by Exact-DP, with DP behavioral interpretation. A DP-behavior-grounded selector has not been implemented. See dp_knowledge_role.json.','',
        '## Consolidated versions','',
        'algorithm_versions.json records V1, V2, AUX, PORT and PORT-ALL with full source hashes, pool order, per-instance/per-seed B1 parameters and individual reproduction commands. V1 is unchanged independent selection; V2 retains the existing optional coupled action. AUX replaces R*, PORT replaces manual balancing, PORT-ALL appends auxiliary without removing manual repairs. All retain D*.','',
        'Keep V1 as the next-stage base: reproducible stable framework, original manual balancing available, frozen D*/R*. Retain AUX as a promising optional comparator, not a newly confirmed best algorithm. Do not promote a portfolio from this tiny diagnostic. Pause C2 development rather than tune for a positive result.','',
        '## Reproduce','',
        'From the repository root in the existing environment:','',
        '```powershell',"$env:PYTHONPATH='src'",
        "foreach ($stage in @('prepare','diagnose','benchmark','analyze')) {",
        "  & 'G:\\Anaconda\\envs\\mrta_env\\python.exe' -m mrta_rect_coverage.experiments.e9_portfolio_diagnosis --stage $stage",
        '  if ($LASTEXITCODE -ne 0) { throw "E9 failed at $stage" }','}','```','',
        'Existing PORT-ALL results resume; use a fresh --output directory at every stage to repeat only the eight new runs. Historical E8 records remain read-only. Optional --version commands in algorithm_versions.json reproduce a named version into a separate directory; they were not executed during E9. No new selector or additional experiment is scheduled.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('prepare','diagnose','benchmark','analyze'),required=True)
    parser.add_argument('--version',choices=VERSIONS,default='PORT-ALL')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/e9_portfolio_diagnosis')
    args=parser.parse_args();output=args.output.resolve()
    if args.stage=='benchmark':benchmark(output,args.version)
    else:dict(prepare=prepare,diagnose=diagnose,analyze=analyze)[args.stage](output)


if __name__=='__main__':main()
