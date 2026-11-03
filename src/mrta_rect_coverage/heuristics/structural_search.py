"""Bounded structural actions on exact host-priced destroy/rebuild branches.

Generated code sees plain data only. Its fresh namespace, hash/AST checks,
timeout process and cleanup are those of the existing persistent executor.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
from time import perf_counter

from .alns_solver import ALNSSolver, OperatorRecord
from ..core.models import MultiRobotSolution
from ..llm.operator_evolution.candidate_execution import CandidateProxy
from ..llm.operator_evolution.persistent_candidate_execution import PersistentCandidateProxy
from ..llm.operator_evolution.candidate_security import code_sha256, validate_candidate_source

MANUAL_PAIRS = [('random_destroy','greedy_insertion'),
                ('bottleneck_route_destroy','regret_k_insertion'),
                ('geometry_aware_destroy','bottleneck_balancing_insertion')]


def validate_actions(value, f):
    if not isinstance(value,list) or not value:
        raise ValueError('nonempty action list required')
    if f['phase']=='destroy':
        ids={t for r in f['routes'] for t in r}
        if (len(value)>f['remove_limit'] or any(type(t) is not int or t not in ids for t in value)
                or len(set(value))!=len(value)):
            raise ValueError('invalid/duplicate/overbudget removal')
    else:
        if len(value)>f['width']:
            raise ValueError('branch width exceeded')
        if len({(a.get('branch'),a.get('task'),a.get('robot'),a.get('position'))
                for a in value if isinstance(a,dict)})!=len(value):
            raise ValueError('duplicate reconstruction action')
        for a in value:
            if (not isinstance(a,dict) or set(a)!={'branch','task','robot','position'}
                    or any(type(v) is not int for v in a.values())
                    or not 0<=a['branch']<len(f['branches'])):
                raise ValueError('invalid branch action')
            if not any(all(a[k]==o[k] for k in ('task','robot','position'))
                       for o in f['branches'][a['branch']]['options']):
                raise ValueError('action must reference an exact offered insertion')
    return value


class StructuralExecutor:
    def __init__(self,path,*,expected_hash=None,timeout_ms=150):
        self.path=Path(path)
        source=self.path.read_text(encoding='utf-8')
        self.code_hash=code_sha256(source)
        # Archive identity is exact file bytes; existing worker hashes normalized text.
        # Verify BOTH at their respective boundary, including Windows CRLF artifacts.
        self.artifact_hash=hashlib.sha256(self.path.read_bytes()).hexdigest()
        if expected_hash and self.artifact_hash!=expected_hash:
            raise ValueError('source hash mismatch')
        validate_candidate_source(source,'structural')
        self.backend=PersistentCandidateProxy.from_validated(
            CandidateProxy(self.path,'structural',self.code_hash,timeout_ms))
        self.samples=[]

    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def close(self): self.backend.close()

    def __call__(self,features,rng):
        # Advance the solver RNG once per decision; copies prevent shared mutation.
        import random
        outcome=self.backend.execute((deepcopy(features),random.Random(rng.getrandbits(64))),
                                     timeout_ms=self.backend.timeout_ms)
        self.samples.append({k:getattr(outcome,k) for k in
                             ('status','wall_time_ms','runtime_ms','startup_ms','validation_import_ms')})
        if outcome.status!='success':
            self.close()
            raise RuntimeError(f'{outcome.status}: {outcome.error_message}')
        return validate_actions(outcome.result,features)


def reference_step(features,rng):
    """Hand-written state-chain window ruin and exact regret branching reference."""
    f=features
    if f['phase']=='destroy':
        b=max(range(len(f['costs'])),key=lambda r:f['costs'][r])
        windows=[w for w in f['windows'] if w['robot']==b]
        if windows:
            w=max(windows,key=lambda w:w['released']-sum(f['tasks'][str(t)]['processing'] for t in w['tasks']))
            chosen=list(w['tasks'])
        else:
            chosen=list(f['routes'][b][:1])
        others=[t for r in f['routes'] for t in r if t not in chosen]
        rng.shuffle(others)
        return (chosen+others[:max(0,f['remove_count']-len(chosen))])[:f['remove_limit']]
    proposals=[]
    for bi,b in enumerate(f['branches']):
        grouped={t:[] for t in b['remaining']}
        for o in b['options']: grouped[o['task']].append(o)
        for opts in grouped.values():
            opts.sort(key=lambda o:(o['makespan'],o['total'],o['robot'],o['position']))
        task=max(grouped,key=lambda t:(grouped[t][min(1,len(grouped[t])-1)]['makespan']-grouped[t][0]['makespan'],
                                      -grouped[t][0]['total']))
        for o in grouped[task][:2 if f['depth']<2 else 1]:
            proposals.append((o['makespan'],o['total'],bi,o))
    proposals.sort(key=lambda x:x[:3])
    return [dict(branch=bi,task=o['task'],robot=o['robot'],position=o['position'])
            for _,_,bi,o in proposals[:f['width']]]


class StructuralKernel:
    def __init__(self,solver,policy,*,width=3,price_cap=80000,record_features=False):
        self.solver,self.policy=solver,policy
        self.width,self.price_cap=width,price_cap
        self.record_features=record_features
        self.records=[]
        self.events=[]

    def destroy_features(self,solution,evaluation,remove_count):
        s=self.solver
        routes=deepcopy(solution.routes)
        limit=min(s.instance.task_count,max(2,min(24,2*remove_count)))
        tasks,windows={},[]
        for robot,route in enumerate(routes):
            chain=evaluation.route_evaluations[robot]
            for pos,t in enumerate(route):
                state=s.cost_matrix.state(chain.chosen_state_ids[pos])
                cost=s.insertion_pricer.route_cost_without(route,pos)
                tasks[str(t)]={'robot':robot,'position':pos,'released':evaluation.per_robot_costs[robot]-cost,
                    'processing':state.processing_time,'entry':state.entry_point,'exit':state.exit_point,
                    'state':state.state_id,'incoming':chain.transition_costs[pos] if pos<len(chain.transition_costs) else 0.,
                    'min_processing':min(x.processing_time for x in s.states_by_task[t])}
            # All contiguous windows of up to three tasks: exact joint costs, not singleton sums.
            for size in (2,3):
                if size>limit: continue
                for pos in range(len(route)-size+1):
                    cost=s.insertion_pricer.route_cost(route[:pos]+route[pos+size:])
                    cc=list(evaluation.per_robot_costs); cc[robot]=cost
                    windows.append({'robot':robot,'tasks':route[pos:pos+size],
                        'released':evaluation.per_robot_costs[robot]-cost,'costs':cc,'makespan':max(cc)})
        return {'phase':'destroy','routes':routes,'costs':list(evaluation.per_robot_costs),
                'remove_count':remove_count,'remove_limit':limit,'tasks':tasks,'windows':windows}

    def destroy(self,solution,evaluation,remove_count):
        f=self.destroy_features(solution,evaluation,remove_count)
        chosen=validate_actions(self.policy(f,self.solver.rng),f)
        self.events.append({'phase':'destroy','remove':chosen,**({'features':f} if self.record_features else {})})
        return self.solver._remove_tasks(solution,chosen)

    def repair(self,partial,removed,partial_eval):
        s=self.solver
        start=perf_counter()
        if not removed: return deepcopy(partial)
        if (len(partial.routes)!=s.instance.robot_count or
                sorted([t for r in partial.routes for t in r]+list(removed))!=sorted(s.states_by_task)):
            raise ValueError('invalid initial partition')
        branches=[{'routes':deepcopy(partial.routes),'costs':list(partial_eval.per_robot_costs),'remaining':list(removed)}]
        prices=0
        budget_stop=False
        for depth in range(len(removed)):
            # Reserve exact cheapest sequential tail for every live branch.
            needed=sum(len(b['remaining'])*(sum(map(len,b['routes']))+len(b['routes'])) for b in branches)
            tails=sum(len(b['remaining'])*(sum(map(len,b['routes']))+len(b['routes']))+
                      len(b['remaining'])*(len(b['remaining'])-1)//2 for b in branches)
            if prices+needed+tails>self.price_cap:
                budget_stop=True
                break
            offered=[]
            for b in branches:
                opts=[]
                for t in b['remaining']:
                    for robot,route in enumerate(b['routes']):
                        costs=s.insertion_pricer.insertion_costs(route,t)
                        prices+=len(costs)
                        # Retain all slots. This permits order reconstruction beyond greedy minima.
                        for pos,cost in enumerate(costs):
                            cc=list(b['costs']); cc[robot]=cost
                            opts.append({'task':t,'robot':robot,'position':pos,'cost':cost,
                                         'makespan':max(cc),'total':sum(cc),
                                         'bottleneck':max(range(len(cc)),key=lambda r:cc[r])})
                offered.append({**deepcopy(b),'options':opts})
            f={'phase':'repair','branches':offered,'depth':depth,'width':self.width,
               'prices_remaining':self.price_cap-prices}
            actions=validate_actions(self.policy(f,s.rng),f)
            new={}
            for a in actions:
                b=deepcopy(branches[a['branch']])
                opt=next(o for o in offered[a['branch']]['options'] if all(o[k]==a[k] for k in ('task','robot','position')))
                b['routes'][a['robot']].insert(a['position'],a['task'])
                b['costs'][a['robot']]=opt['cost']; b['remaining'].remove(a['task'])
                new.setdefault(tuple(map(tuple,b['routes'])),b)
            # The action width is a global offspring cap; without truncation a
            # width-k policy can still grow into a k^depth beam in the host.
            branches=sorted(new.values(),key=lambda b:(max(b['costs']),sum(b['costs']),tuple(map(tuple,b['routes']))))[:self.width]
            self.events.append({'phase':'repair','depth':depth,'actions':actions,
                                'outcomes':[{'costs':b['costs'],'remaining':b['remaining']} for b in branches],
                                **({'features':f} if self.record_features else {})})
        # A deterministic budget completion is explicit and counted; it is not an error fallback.
        for b in branches:
            for t in list(b['remaining']):
                opts=[]
                for robot,route in enumerate(b['routes']):
                    if prices+len(route)+1>self.price_cap:
                        raise RuntimeError('price budget cannot complete branch')
                    vals=s.insertion_pricer.insertion_costs(route,t); prices+=len(vals)
                    for pos,c in enumerate(vals):
                        cc=list(b['costs']); cc[robot]=c
                        opts.append((max(cc),sum(cc),robot,pos,c))
                _,_,robot,pos,c=min(opts)
                b['routes'][robot].insert(pos,t); b['costs'][robot]=c
                b['remaining'].remove(t)
        best=min(branches,key=lambda b:(max(b['costs']),sum(b['costs'])))
        result=MultiRobotSolution(best['routes'])
        if not s._is_valid_full_solution(result): raise ValueError('invalid repaired solution')
        self.records.append({'prices':prices,'costs':best['costs'],'budget_stop':budget_stop,
                             'max_live_branches':max((len(x.get('outcomes',[])) for x in self.events if x['phase']=='repair'),default=1),
                             'seconds':perf_counter()-start,'routes':deepcopy(result.routes)})
        return result


class PairPortfolioSolver(ALNSSolver):
    """Reuse the production ALNS loop with credit ONLY for deployed pair actions."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.pairs=[]
        self.deployment_stats={}
        self.pair_weights={}
        self._pair_segment={}

    def add_kernel(self,name,kernel):
        for group,fn in [('destroy',kernel.destroy),('repair',kernel.repair)]:
            key=f'{name}:{group}'
            getattr(self,f'{group}_ops')[key]=fn
            getattr(self,f'{group}_weights')[key]=1.
            self.operator_stats[group][key]=OperatorRecord()
            self.segment_stats[group][key]=OperatorRecord()
            self.operator_time_stats[group][key]=[0.,0.]
            self.segment_time_stats[group][key]=[0.,0.]

    def set_pairs(self,pairs):
        self.pairs=list(dict.fromkeys(tuple(p) for p in pairs))
        if not self.pairs or any(d not in self.destroy_ops or r not in self.repair_ops for d,r in self.pairs):
            raise ValueError('deployment contains unknown/empty pairs')
        self.deployment_stats={self.key(p):dict(calls=0,reward=0.,accepted=0,best=0) for p in self.pairs}
        self.pair_weights={k:1. for k in self.deployment_stats}
        self._pair_segment={k:[0.,0] for k in self.deployment_stats}

    @staticmethod
    def key(pair): return '|'.join(pair)

    def _select_operators(self,context):
        untried=[p for p in self.pairs if not self.deployment_stats[self.key(p)]['calls']]
        if untried: pair=self.rng.choice(untried)
        elif self.rng.random()<.1: pair=self.rng.choice(self.pairs)
        else: pair=self.rng.choices(self.pairs,weights=[self.pair_weights[self.key(p)] for p in self.pairs])[0]
        self._selected_pair=self.key(pair)
        self._last_selection_action=self._selected_pair
        return *pair,'portfolio'

    def _update_operator_stats(self,group,name,reward):
        self.operator_stats[group][name].uses+=1
        if group=='repair':
            rec=self.deployment_stats[self._selected_pair]
            rec['calls']+=1; rec['reward']+=reward
            rec['accepted']+=int(reward>0); rec['best']+=int(reward>=8)
            seg=self._pair_segment[self._selected_pair]; seg[0]+=reward; seg[1]+=1

    def _update_weights(self):
        alpha=self.config.reaction_factor
        for key,(score,uses) in self._pair_segment.items():
            if uses: self.pair_weights[key]=max(.1,(1-alpha)*self.pair_weights[key]+alpha*score/uses)
            self._pair_segment[key]=[0.,0]

    def solve(self):
        if not self.pairs: raise ValueError('set deployment before solve')
        result=super().solve()
        for h in result.iteration_history:
            h['pair_reward']=h['score_effective']
            h['destroy_reward']=h['repair_reward']=0.
            h['reward_attribution']={'pair':h['selection_action'],'members':'not_attributed'}
        return result
