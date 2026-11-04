"""One bounded real LLM population -> pair portfolio -> frozen-stage experiment."""
from __future__ import annotations
import argparse
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import inspect
import json
from pathlib import Path
import random
from statistics import mean, pstdev
from time import perf_counter

from ..core.instance_loader import load_instance
from ..core.models import MultiRobotSolution
from ..heuristics.alns_solver import ALNSConfig, ALNSSolver
from ..heuristics.structural_search import (PairPortfolioSolver,StructuralKernel,
    StructuralExecutor,reference_step,MANUAL_PAIRS)
from ..llm.operator_evolution.candidate_security import validate_candidate_source
from ..llm.operator_evolution.langchain_provider import LangChainOperatorEvolutionProvider
from ..llm.runtime.config import load_from_env
from ..llm.runtime.client_factory import build_langchain_chat_model

ROOT=Path(__file__).resolve().parents[3]
DATA=ROOT/'data/structural_benchmark_v1'

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,data):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    Path(p).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(**kw): print(json.dumps(kw,ensure_ascii=True),flush=True)
def instance(e):
    if e['split']!='development': raise ValueError('development inputs only')
    if 'input_path' in e:
        p=(ROOT/e['input_path']).resolve()
        allowed=(ROOT/'outputs/structural_population/deploy_check_003/inputs').resolve()
        if not p.is_relative_to(allowed): raise ValueError('custom input escaped frozen check inputs')
    else:
        p=DATA/e['path']
    if sha(p)!=e['sha256']: raise ValueError('instance hash mismatch')
    return load_instance(p)


CONTRACT='''Implement one pure Python def search_step(features, rng). Return ONE JSON object
{"name":"...", "description":"falsifiable structural hypothesis", "code":"complete Python source"}.
Allowed import: math only. No IO, reflection, object attribute mutation, solver access or instance-ID memorization.
The same program implements two phases. All input data are copies. You may define helper functions.
DESTROY: features={phase:"destroy",routes:[[int task IDs]],costs:[exact route costs],remove_count:int,
remove_limit:int,tasks:{STRING task ID:{robot,position,released,processing,min_processing,entry:[x,y],exit:[x,y],state,incoming}},
windows:[{robot,tasks:[2 or 3 contiguous IDs],released,costs:[exact after JOINT removal],makespan}]}.
Return a nonempty list of unique known task IDs, at most remove_limit. You choose actual removal size and set,
can remove contiguous chains or scattered cross-robot tasks to allow joint reassignment and visit-order rebuilding.
released is exact optimal-state route-cost saving, not additive across tasks. windows are exact joint removal outcomes.
State IDs and task IDs are identifiers, not numeric features. incoming is actual depot/preceding-state transition cost.
REPAIR: features={phase:"repair",depth:int,width:3,prices_remaining:int,
branches:[{routes:[[IDs]],costs:[exact costs],remaining:[IDs],options:[{task,robot,position,cost,makespan,total,bottleneck}]}]}.
ALL insertions of remaining tasks into every slot/robot are priced exactly on THAT branch's actual routes.
Return 1..width dictionaries with EXACTLY {branch:int,task:int,robot:int,position:int}, each referencing an offered option.
The host applies each chosen insertion to its parent branch, deduplicates resulting routes, then presents new exact
options. You control which task is inserted next, where, and which competing reconstruction branches survive.
You may retain branches for different tasks, assignments, orders or bottleneck transitions; no fixed depth-two rule.
Every remaining task must eventually be inserted. The host returns lowest final makespan/total branch, then applies
the common one-pass priced LS and SA. No local-improvement requirement. Candidate decisions must finish within 150ms;
host price cap 80000, beam width 3. Budget completion uses deterministic greedy, counted and recorded. Avoid wide
branching on every depth: final timed solve matters, including feature, subprocess and pricing overhead.
No mandatory greedy incumbent or forced random fallback masks your algorithm. Invalid candidates are rejected.
Destroy/repair phases can also be deployed separately with manual phases or another generated source.
Return executable structural behavior, not a description or only a few changed coefficients.
Research hypothesis (not established): entry/exit chains, joint removal prices and bottleneck migration can guide
effective structural moves and complementary portfolios. Do not claim novelty for multiple operators or coevolution.
'''


class Study:
    def __init__(self,config_path,*,resume=False):
        self.cfg=read(config_path)
        c=self.cfg
        if not (1<=c['rounds']<=4 and 1<=c['children_per_round']<=4 and c['max_requests']<=32):
            raise ValueError('outside authorized limits')
        self.out=ROOT/c['output_dir']
        if resume:
            if read(self.out/'config.json')!=c: raise ValueError('resume config mismatch')
        else:
            self.out.mkdir(parents=True,exist_ok=False)
            save(self.out/'config.json',c)
            entries=read(DATA/'manifest.json')['entries']
            lookup={e['instance_id']:e for e in entries}
            chosen={role:[lookup[i] for i in c[role]] for role in ('development','reserved')}
            if any(e['split']!='development' for es in chosen.values() for e in es): raise ValueError('invalid split')
            if set(c['development'])&set(c['reserved']): raise ValueError('overlapping holdout')
            save(self.out/'entries.json',chosen)  # reserved CONTENT is not read until freeze
            files=[Path(__file__),ROOT/'src/mrta_rect_coverage/heuristics/structural_search.py',
                   ROOT/'src/mrta_rect_coverage/heuristics/alns_solver.py',
                   ROOT/'src/mrta_rect_coverage/llm/operator_evolution/candidate_security.py',
                   ROOT/'src/mrta_rect_coverage/llm/operator_evolution/persistent_candidate_execution.py']
            save(self.out/'source_hashes.json',{str(p.relative_to(ROOT)):sha(p) for p in files})
        self.entries=read(self.out/'entries.json')
        self.archive=read(self.out/'archive.json') if (self.out/'archive.json').exists() else {}
        self.ledger=read(self.out/'requests.json') if (self.out/'requests.json').exists() else []
        self.groups=read(self.out/'groups.json') if (self.out/'groups.json').exists() else {}
        self.rng=random.Random(1102)

    def persist(self):
        save(self.out/'archive.json',self.archive); save(self.out/'groups.json',self.groups)

    def config(self,seed,seconds=None,iterations=None):
        return ALNSConfig.enhanced(iterations=iterations,max_runtime_seconds=seconds,
            random_seed=seed,priced_local_search=True,segment_length=10,
            destroy_fraction=.2,capture_operator_states=False)

    def seed(self):
        if self.archive: return
        folder=self.out/'sources'; folder.mkdir()
        for i,pair in enumerate(MANUAL_PAIRS):
            name=f'manual_{i}'
            source='\n'.join(inspect.getsource(getattr(ALNSSolver,'_'+x)) for x in pair)
            p=folder/f'{name}.py'; p.write_text(source,encoding='utf-8')
            self.archive[name]={'id':name,'origin':'manual','parents':[],'source':str(p.relative_to(ROOT)),
                                'hash':sha(p),'pair':list(pair),'valid':True,'operation':'seed'}
        p=folder/'reference.py'
        p.write_text(inspect.getsource(reference_step).replace('def reference_step(', 'def search_step('),encoding='utf-8')
        self.archive['reference']={'id':'reference','origin':'deterministic','parents':[],
            'source':str(p.relative_to(ROOT)),'hash':sha(p),'pair':['reference:destroy','reference:repair'],
            'valid':True,'operation':'seed'}
        self.persist()

    def attach(self,s,pairs,stack,record=False,reference_executor=False):
        kernels={}; executors={}
        ids=sorted({name.split(':')[0] for pair in pairs for name in pair if ':' in name})
        for name in ids:
            a=self.archive[name]
            if sha(ROOT/a['source'])!=a['hash']: raise ValueError('source drift')
            if name=='reference' and not reference_executor: policy=reference_step
            else:
                policy=stack.enter_context(StructuralExecutor(ROOT/a['source'],expected_hash=a['hash']))
                executors[name]=policy
            k=StructuralKernel(s,policy,width=self.cfg['beam_width'],price_cap=self.cfg['price_cap'],record_features=record)
            s.add_kernel(name,k); kernels[name]=k
        s.set_pairs(pairs)
        return kernels,executors

    def run_one(self,e,seed,pairs,*,reference_executor=False):
        start=perf_counter()
        allowance=self.cfg['seconds_by_tasks'][str(e['n_tasks'])]
        # Loading, cost matrix and constructor are inside the allowance.
        cls=ALNSSolver if pairs is None else PairPortfolioSolver
        s=cls(instance(e),constructor=self.cfg['constructor'],config=self.config(seed,seconds=allowance))
        error=None; result=None; kernels={}; executors={}
        try:
            with ExitStack() as stack:
                if pairs is not None: kernels,executors=self.attach(s,pairs,stack,
                    reference_executor=reference_executor)
                setup=perf_counter()-start
                s.config.max_runtime_seconds=max(.001,allowance-setup)
                result=s.solve()
        except Exception as exc:
            error=f'{type(exc).__name__}: {exc}'
        elapsed=perf_counter()-start
        row={'instance_id':e['instance_id'],'seed':seed,'budget_seconds':allowance,
             'end_to_end_seconds':elapsed,'overshoot_seconds':max(0,elapsed-allowance),
             'setup_seconds':locals().get('setup',elapsed),'error':error,'valid':result is not None,
             'pairs':pairs,'config':asdict(s.config),'executors':{n:x.samples for n,x in executors.items()},
             'kernel_summary':{n:{'calls':len(k.records),'prices':sum(r.get('price_requests',r.get('prices',0)) for r in k.records),
                                 'budget_completions':sum(r.get('status')=='budget_exhausted' or r.get('budget_stop',False)
                                                          for r in k.records)} for n,k in kernels.items()}}
        if result:
            best_rows=[h for h in result.iteration_history
                       if abs(h['best_makespan']-result.best_evaluation.makespan)<1e-9]
            first_best=(setup+best_rows[0]['elapsed_seconds']) if best_rows else None
            kernel_rows=[r for k in kernels.values() for r in k.records]
            phases=('feature_construction','exact_pricing','strategy_execution','reconstruction','completion')
            kernel_costs={phase:sum(r['phase_costs'][phase] for r in kernel_rows) for phase in phases}
            kernel_calls={phase:sum(r['phase_calls'][phase] for r in kernel_rows) for phase in phases}
            row.update(makespan=result.best_evaluation.makespan,routes=result.best_solution.routes,
                initial=result.initial_makespan,iterations=result.iterations_completed,
                iterations_attempted=result.iterations_completed+result.incomplete_iterations,
                incomplete_iterations=result.incomplete_iterations,
                incomplete_iteration_records=result.incomplete_iteration_records,
                first_legal_complete_seconds=setup,
                first_final_best_seconds=first_best,
                solve_seconds=result.runtime_seconds,valid=s._is_valid_full_solution(result.best_solution),
                dp=s.route_dp.statistics(),pricing=s.insertion_pricer.statistics(),
                pair_stats=getattr(s,'deployment_stats',{}),fallbacks=result.fallback_events,
                structural_work={'completed_search_steps':sum(r['status']=='complete' for r in kernel_rows),
                    'budget_exhausted_steps':sum(r['status']=='budget_exhausted' for r in kernel_rows),
                    'errors':sum(r['status']=='error' for r in kernel_rows),
                    'phase_seconds':kernel_costs,'phase_calls':kernel_calls,
                    'price_requests':sum(r['price_requests'] for r in kernel_rows),
                    'policy_calls':sum(r['policy_calls'] for r in kernel_rows),
                    'max_live_branches':max((r['max_live_branches'] for r in kernel_rows),default=0)},
                structural_events={name:k.events for name,k in kernels.items()},
                history=result.iteration_history)
        return row

    def evaluate(self,label,pairs,role='development'):
        pairs=None if pairs is None else [list(pair) for pair in pairs]
        p=self.out/role/f'{label}.json'
        if p.exists():
            previous=read(p)
            if previous.get('pairs')==pairs and previous.get('valid'): return previous
            suffix='invalid_pair_shape' if previous.get('pairs')!=pairs else 'failed_budget_semantics'
            backup=p.with_name(f'{p.stem}.{suffix}.json')
            if backup.exists(): raise FileExistsError(f'refusing to overwrite {backup}')
            save(backup,previous)
        rows=[]; start=perf_counter()
        # Alternate seed blocks, same predeclared ordering; avoid parallel CPU contention.
        for e in self.entries[role]:
            for seed in self.cfg['seeds']:
                row=self.run_one(e,seed,pairs); rows.append(row)
                emit(stage=role,group=label,instance=e['instance_id'],seed=seed,
                     makespan=row.get('makespan'),seconds=round(row['end_to_end_seconds'],3),error=row['error'])
                save(p.with_suffix('.partial.json'),rows)
        data={'label':label,'pairs':pairs,'rows':rows,'wall_seconds':perf_counter()-start,
              'valid':all(r['valid'] and not r['error'] for r in rows)}
        if role=='development':
            if label=='manual':
                data.update(score=0.,mean_relative=0.,relative_by_instance=[0.]*len(self.entries[role]))
            elif data['valid']:
                base=read(self.out/'development/manual.json')['rows']
                by=[]
                for e in self.entries[role]:
                    ds=[(r['makespan']-b['makespan'])/b['makespan'] for r,b in zip(rows,base) if r['instance_id']==e['instance_id']]
                    by.append(mean(ds))
                data.update(mean_relative=mean(by),relative_by_instance=by,score=mean(by)+.1*max(0,max(by)))
            else: data.update(score=1e6,mean_relative=1e6,relative_by_instance=[])
            self.groups[label]={k:data[k] for k in ('label','pairs','valid','score','mean_relative','relative_by_instance')}
        save(p,data); self.persist()
        return data

    def behavior(self,name):
        a=self.archive[name]
        p=self.out/'behavior'/f'{name}.json'
        if p.exists(): return read(p)
        rows=[]
        try:
            with ExitStack() as stack:
                policy=(reference_step if name=='reference' else stack.enter_context(
                    StructuralExecutor(ROOT/a['source'],expected_hash=a['hash'])))
                for idx,e in enumerate(self.entries['development'][:3]):
                    s=PairPortfolioSolver(instance(e),config=self.config(71+idx,iterations=1))
                    # Fixed initial and mid-search manual states; not optimized per candidate.
                    base=read(self.out/'development/manual.json')['rows'][idx*2]
                    solution=MultiRobotSolution(base['routes'])
                    if idx==0: solution=s.initial_solution
                    ev=s.solution_evaluator.evaluate(solution)
                    k=StructuralKernel(s,policy,width=self.cfg['beam_width'],price_cap=self.cfg['price_cap'],record_features=idx==0)
                    partial,removed=k.destroy(solution,ev,max(2,int(.2*e['n_tasks'])))
                    full=k.repair(partial,removed,s.solution_evaluator.evaluate_partial(partial))
                    evaluation=s.solution_evaluator.evaluate(full)
                    rows.append({'instance_id':e['instance_id'],'remove':removed,'routes':full.routes,
                        'before':ev.makespan,'after':evaluation.makespan,'costs':evaluation.per_robot_costs,
                        'events':k.events,'record':k.records[-1]})
            fingerprint=hashlib.sha256(json.dumps([(r['remove'],r['routes']) for r in rows]).encode()).hexdigest()
            data={'valid':True,'rows':rows,'fingerprint':fingerprint}
        except Exception as exc:
            data={'valid':False,'rows':rows,'error':f'{type(exc).__name__}: {exc}'}
        save(p,data)
        return data

    def feedback(self):
        # Bounded summaries include failures and complete-solve performance, not just the champion.
        return {'groups':list(self.groups.values()),'archive':[{k:a.get(k) for k in
            ('id','parents','operation','description','valid','duplicate_of','group','error')} for a in self.archive.values()],
            'limits':'development feedback; no reserved outcomes; no causal superiority claim'}

    def request(self,name,round_id,operation,parents,repair_error=None):
        if len(self.ledger)>=self.cfg['max_requests']: return None
        folder=self.out/'requests'/f'{len(self.ledger)+1:02d}_{name}'
        folder.mkdir(parents=True,exist_ok=False)
        prompt=CONTRACT+'\nOperation: '+operation+'\n'
        if operation=='recombine': prompt+='Combine concrete structural logic from BOTH parents; explain retained and changed behavior.\n'
        elif operation=='gap': prompt+='Target the portfolio weaknesses and bottleneck transitions in complete-solve feedback; design complementary actions.\n'
        elif operation=='de_novo': prompt+='Invent a small new search behavior without inheriting a specific source.\n'
        else: prompt+='Structurally revise parent actions, use full-solve feedback; do not just retune scalar weights.\n'
        for parent in parents:
            a=self.archive[parent]
            prompt+=f'\nPARENT {parent} ({a["origin"]})\n'+(ROOT/a['source']).read_text(encoding='utf-8')
        prompt+='\nFEEDBACK:\n'+json.dumps(self.feedback(),ensure_ascii=False,separators=(',',':'))
        for parent in parents:
            bp=self.out/'behavior'/f'{parent}.json'
            if bp.exists():
                behavior=read(bp)
                if behavior['valid']:
                    measured=[{k:r[k] for k in ('instance_id','remove','routes','before','after','costs')} for r in behavior['rows']]
                    prompt+='\nACTUAL PARENT ACTIONS AND OUTCOMES '+parent+':\n'+json.dumps(measured,separators=(',',':'))
        # One exact trace, with bounded action alternatives and truthful measured outcomes.
        trace=read(self.out/'behavior/reference.json') if (self.out/'behavior/reference.json').exists() else None
        if trace and trace['valid']:
            rr=trace['rows'][0]
            detail=deepcopy(rr)
            for ev in detail['events']:
                if 'features' in ev and ev['phase']=='repair':
                    for b in ev['features']['branches']: b['options']=sorted(b['options'],key=lambda o:(o['makespan'],o['total']))[:12]
            detail['events']=detail['events'][:3]
            prompt+='\nMeasured reference trace; repair option list truncated FOR PROMPT ONLY:\n'+json.dumps(detail,separators=(',',':'))
        if repair_error:
            prompt+='\nONE ENGINEERING REPAIR: preserve algorithm intent; fix this actual failure: '+repair_error
            prior=self.archive[name]; prompt+='\nFailed code:\n'+(ROOT/prior['source']).read_text(encoding='utf-8')
        (folder/'prompt.txt').write_text(prompt,encoding='utf-8')
        runtime=replace(load_from_env(),max_retries=0,temperature=None,max_output_tokens=self.cfg['max_output_tokens'])
        if runtime.provider not in ('langchain_openai_compatible','langchain'): raise ValueError('real provider required')
        provider=LangChainOperatorEvolutionProvider(build_langchain_chat_model(runtime),raw_response_dir=folder,requested_temperature=None)
        row={'request':len(self.ledger)+1,'candidate':name,'round':round_id,'operation':operation,
             'parents':parents,'repair':bool(repair_error),'model':runtime.model,'provider':runtime.provider,
             'prompt_hash':sha(folder/'prompt.txt'),'max_output_tokens':runtime.max_output_tokens,
             'status':'started','max_retries':0}
        self.ledger.append(row); save(self.out/'requests.json',self.ledger)
        emit(stage='request',candidate=name,operation=operation,number=row['request'])
        started=perf_counter()
        try:
            drafts=provider.revise_operator_candidates(prompt,{},n=1,operator_type='structural',round_id=round_id)
            row.update(status='success' if drafts else 'parse_failure',metadata=provider.last_call_metadata)
        except Exception as exc:
            drafts=[]; row.update(status='provider_failure',error_type=type(exc).__name__,status_code=getattr(exc,'status_code',None))
        row['seconds']=perf_counter()-started
        save(self.out/'requests.json',self.ledger)
        if not drafts: return None
        draft=drafts[0]
        p=folder/'candidate.py'; p.write_text(draft.code,encoding='utf-8')
        prior=self.archive.get(name)
        record={'id':name,'origin':'llm','parents':parents,'parent_hashes':[self.archive[x]['hash'] for x in parents],
                'round':round_id,'operation':operation,'description':draft.description,'source':str(p.relative_to(ROOT)),
                'hash':sha(p),'pair':[name+':destroy',name+':repair'],'request':row['request'],'valid':False,
                'prior_source':prior['source'] if repair_error else None}
        save(folder/'lineage.json',record)
        self.archive[name]=record; self.persist()
        return record

    def candidate(self,name,round_id,operation,parents):
        # Requests are never replayed automatically after an uncertain started call.
        a=self.archive.get(name)
        if a and 'group' in a: return a
        if a is None:
            if any(r['candidate']==name for r in self.ledger): return None
            a=self.request(name,round_id,operation,parents)
        if not a: return None
        for attempt in range(2):
            try:
                validate_candidate_source((ROOT/a['source']).read_text(encoding='utf-8'),'structural')
                b=self.behavior(name)
                if not b['valid']: raise ValueError(b['error'])
                a.update(valid=True,fingerprint=b['fingerprint'])
                duplicate=next((x['id'] for x in self.archive.values() if x['id']!=name and x.get('fingerprint')==b['fingerprint']),None)
                if duplicate:
                    a['duplicate_of']=duplicate; a['valid']=False
                    self.persist(); return a
                data=self.evaluate(name,list(MANUAL_PAIRS)+[a['pair']])
                a.update(valid=data['valid'],group=name)
                if not data['valid']: a['error']='; '.join(r['error'] or '' for r in data['rows'] if r['error'])
                self.persist(); return a
            except Exception as exc:
                a['error']=str(exc); self.persist()
                if attempt or any(r['candidate']==name and r['repair'] for r in self.ledger): return a
                # Preserve failed behavior artifact before exactly one engineering repair.
                bp=self.out/'behavior'/f'{name}.json'
                if bp.exists(): bp.rename(bp.with_name(name+'_failed.json'))
                a=self.request(name,round_id,operation,parents,repair_error=str(exc))
                if not a: return None

    def survivors(self):
        seeds=['manual_0','manual_1','manual_2','reference']
        eligible=[a for a in self.archive.values() if a['origin']=='llm' and a.get('valid') and a.get('group')
                  and self.groups[a['group']]['mean_relative']<=self.cfg['population_quality_floor']]
        eligible.sort(key=lambda a:self.groups[a['group']]['score'])
        selected=seeds[:]
        if eligible: selected.append(eligible[0]['id'])  # elite
        for j in range(len(self.entries['development'])):
            if eligible:
                best=min(eligible,key=lambda a:self.groups[a['group']]['relative_by_instance'][j])
                if best['id'] not in selected: selected.append(best['id'])
        for a in eligible:
            if a['id'] not in selected: selected.append(a['id'])
        return selected[:self.cfg['population_capacity']]

    def choose_parents(self,population,round_id,index):
        # Rank-biased tournaments, distinct second parent, round rotation; never latest-child chaining.
        r=random.Random(1102+round_id*31+index)
        ranked=sorted(population,key=lambda n:self.groups.get(self.archive[n].get('group'),{}).get('score',0.))
        weights=[1/(i+1) for i in range(len(ranked))]
        first=r.choices(ranked,weights=weights)[0]
        others=[n for n in ranked if n!=first]
        second=r.choice(others)
        return [first,second]

    def best_group(self,labels=None):
        values=[g for k,g in self.groups.items() if g['valid'] and (labels is None or k in labels)]
        best=min(g['score'] for g in values)
        close=[g for g in values if g['score']<=best+.0005]
        return min(close,key=lambda g:(len({n.split(':')[0] for p in (g['pairs'] or []) for n in p if ':' in n}),
                                       len(g['pairs'] or MANUAL_PAIRS),g['score'],g['label']))

    def compositions(self,round_id,population):
        candidates=[a for a in self.archive.values() if a['origin']=='llm' and a.get('valid') and a.get('group')]
        if len(candidates)<2: return []
        first=min(candidates,key=lambda a:self.groups[a['group']]['score'])
        # Complementary partner chosen by instance-vector envelope, then measured whole combination.
        vec=self.groups[first['group']]['relative_by_instance']
        second=min((a for a in candidates if a['id']!=first['id']),key=lambda a:(
            mean(min(x,y) for x,y in zip(vec,self.groups[a['group']]['relative_by_instance'])),
            self.groups[a['group']]['score']))
        a,b=first['id'],second['id']
        # Also expose retained alternatives if the same two recur; use a different lineage each round.
        if round_id>1 and len(candidates)>2:
            used={tuple(g.get('members',[])) for g in self.groups.values()}
            if (a,b) in used:
                pool=[x for x in candidates if x['id']!=a]
                second=pool[(round_id-1)%len(pool)]; b=second['id']
        pa,pb=self.archive[a]['pair'],self.archive[b]['pair']
        specs=[(f'r{round_id}_join',list(MANUAL_PAIRS)+[pa,pb]),
               (f'r{round_id}_replace',list(MANUAL_PAIRS[:2])+[pa,pb]),
               (f'r{round_id}_cross',list(MANUAL_PAIRS[:2])+[[pa[0],pb[1]],[pb[0],pa[1]]])]
        for label,pairs in specs:
            self.evaluate(label,pairs); self.groups[label]['members']=[a,b]
        self.persist()
        return [l for l,_ in specs]

    def run(self):
        start=perf_counter(); self.seed()
        self.evaluate('manual',None)
        self.evaluate('manual_pairs',MANUAL_PAIRS)
        ref=self.behavior('reference'); self.archive['reference'].update(fingerprint=ref.get('fingerprint'),valid=ref['valid'])
        self.evaluate('reference',list(MANUAL_PAIRS)+[self.archive['reference']['pair']])
        self.archive['reference']['group']='reference'; self.persist()
        population=self.survivors(); stalled=0; best=self.best_group()['score']; previous=set(population)
        rounds=[]
        for r in range(1,self.cfg['rounds']+1):
            round_path=self.out/f'round_{r}.json'
            if round_path.exists():
                info=read(round_path); rounds.append(info); population=info['population'];
                stalled=info['stalled']; best=info['best_score']; previous=set(population)
                if info['stop']: break
                continue
            generated=[]
            for j in range(self.cfg['children_per_round']):
                if len(self.ledger)>=self.cfg['max_requests']: break
                op=['mutate','recombine','gap','de_novo' if r==1 else 'mutate'][j]
                parents=self.choose_parents(population,r,j)
                if op=='mutate': parents=parents[:1]
                if op=='de_novo': parents=[]
                a=self.candidate(f'r{r}_c{j+1}',r,op,parents)
                if a: generated.append(a['id'])
            population=self.survivors()
            labels=self.compositions(r,population)
            now=self.best_group()['score']
            effective=[n for n in generated if self.archive[n].get('valid') and self.archive[n].get('group')
                and self.groups[self.archive[n]['group']]['mean_relative']<=self.cfg['population_quality_floor']
                and min(self.groups[self.archive[n]['group']]['relative_by_instance'])<-.0005]
            progress=now<best-.0005 or bool(effective)
            stalled=0 if progress else stalled+1
            stop=(r==self.cfg['rounds'] or len(self.ledger)>=self.cfg['max_requests'] or stalled>=self.cfg['stagnant_rounds'])
            info={'round':r,'generated':generated,'population':population,'eliminated':sorted(previous-set(population)),
                  'admitted':sorted(set(population)-previous),'compositions':labels,'effective_new':effective,
                  'best_score':min(best,now),'stalled':stalled,'stop':stop,
                  'stop_reason':('round_budget' if r==self.cfg['rounds'] else 'request_budget' if len(self.ledger)>=self.cfg['max_requests']
                                 else 'population_and_composition_stagnation' if stop else None)}
            save(round_path,info); emit(stage='round_complete',**info)
            rounds.append(info); best=min(best,now); previous=set(population)
            if stop: break
        self.freeze_and_check(rounds)
        save(self.out/'invocation_cost.json',{'wall_seconds':perf_counter()-start,'requests':len(self.ledger),
            'request_seconds':sum(r.get('seconds',0) for r in self.ledger),
            'development_solve_seconds':sum(read(p)['wall_seconds'] for p in (self.out/'development').glob('*.json') if not p.name.endswith('.partial.json')),
            'money_usd':None,'money_note':'provider did not supply billed dollar cost; token usage retained per request'})

    def freeze_and_check(self,rounds):
        p=self.out/'freeze.json'
        if p.exists(): frozen=read(p)
        else:
            multi=[k for k,g in self.groups.items() if len({n.split(':')[0] for pair in (g['pairs'] or []) for n in pair
                    if ':' in n and not n.startswith('reference:')})>=2]
            if multi:
                proposed=self.best_group(multi)
                names=sorted({n.split(':')[0] for pair in proposed['pairs'] for n in pair if ':' in n})
                for name in names[:2]:
                    pairs=[pair for pair in proposed['pairs'] if not any(n.startswith(name+':') for n in pair)]
                    if pairs: self.evaluate('remove_'+name,pairs)
            single=[a['group'] for a in self.archive.values() if a['origin']=='llm' and a.get('valid') and a.get('group')]
            single_group=self.best_group(single) if single else self.groups['manual']
            multi_group=self.best_group(multi) if multi else self.groups['manual']
            selected=self.best_group()
            frozen={'selected':selected,'single':single_group,'multi_proposal':multi_group,
                    'rounds':rounds,'requests':len(self.ledger),
                    'sources':{n:{'source':a['source'],'hash':a['hash']} for n,a in self.archive.items()},
                    'reserved_scope':self.cfg['reserved_history']}
            save(p,frozen)  # freeze BEFORE any reserved input content is read
        for label,g in [('manual',self.groups['manual']),('single',frozen['single']),
                        ('multi_proposal',frozen['multi_proposal']),('selected',frozen['selected']),
                        ('reference',self.groups['reference'])]:
            # Exactly one solve per distinct configuration/instance/seed; reuse identity for equal groups.
            existing=next((x for x in (self.out/'reserved').glob('*.json') if not x.name.endswith('.partial.json')
                           and read(x)['pairs']==g['pairs']),None) if (self.out/'reserved').exists() else None
            if existing:
                d=read(existing); d['alias_of']=d['label']; d['label']=label; save(self.out/'reserved'/f'{label}.json',d)
            else: self.evaluate(label,g['pairs'],'reserved')
        self.report(frozen)

    def report(self,frozen):
        summary={'freeze':frozen,'development':{},'reserved':{},'request_count':len(self.ledger)}
        for role in ('development','reserved'):
            manual=read(self.out/role/'manual.json')['rows']
            for p in (self.out/role).glob('*.json'):
                if p.name.endswith('.partial.json') or 'invalid_unbounded' in p.name: continue
                d=read(p)
                if not d['valid']: summary[role][d['label']]={'valid':False}; continue
                rel=[100*(b['makespan']-a['makespan'])/b['makespan'] for a,b in zip(d['rows'],manual)]
                summary[role][d['label']]={'mean_improvement_percent':mean(rel),'wins':sum(x>1e-8 for x in rel),
                    'ties':sum(abs(x)<=1e-8 for x in rel),'losses':sum(x< -1e-8 for x in rel),
                    'mean_end_to_end_seconds':mean(r['end_to_end_seconds'] for r in d['rows']),
                    'max_overshoot_seconds':max(r['overshoot_seconds'] for r in d['rows']),
                    'by_instance':[{'id':e['instance_id'],
                        'values':[r['makespan'] for r in d['rows'] if r['instance_id']==e['instance_id']],
                        'seed_std':pstdev([r['makespan'] for r in d['rows'] if r['instance_id']==e['instance_id']]),
                        'improvement_percent':mean(x for x,r in zip(rel,d['rows']) if r['instance_id']==e['instance_id'])}
                        for e in self.entries[role]]}
        summary['integrity']={
            'pre_fix_unbounded_candidate':'r1_c3',
            'original_end_to_end_seconds':63478.0787396,
            'status':'excluded from all selection summaries; original raw output preserved as r1_c3_invalid_unbounded.json',
            'post_fix_capped_recheck':'r1_c3_capped_recheck',
            'post_fix_end_to_end_seconds_max':max(r['end_to_end_seconds'] for r in
                read(self.out/'development/r1_c3_capped_recheck.json')['rows']),
            'post_fix_mean_improvement_percent':mean(100*(1+r['mean_relative'])-100 for r in
                [read(self.out/'development/r1_c3_capped_recheck.json')]),
            'beam_width':self.cfg['beam_width'],
            'reserved_scope':'Two instances with E14 historical descriptive-use; batch-held only, not independent validation.'}
        save(self.out/'summary.json',summary)
        emit(stage='complete',selected=frozen['selected']['label'],requests=len(self.ledger),
             development=summary['development'][frozen['selected']['label']],reserved=summary['reserved']['selected'])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config',default='configs/structural_population.json')
    p.add_argument('--resume',action='store_true')
    p.add_argument('--prepare',action='store_true')
    p.add_argument('--report',action='store_true')
    args=p.parse_args()
    study=Study(ROOT/args.config,resume=args.resume)
    if args.report: study.report(read(study.out/'freeze.json'))
    elif args.prepare: study.seed(); emit(stage='prepared',output=str(study.out))
    else: study.run()

if __name__=='__main__': main()
