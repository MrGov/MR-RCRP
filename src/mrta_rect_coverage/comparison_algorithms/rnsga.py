"""Single-objective RNSGA adaptation: Chen et al., T-ITS 26(8), 2025.

Algorithm 1 / Section IV: clustered nearest-task construction, ISA adaptive
discrete genetic sequencing, RBM endpoint load balance, proximity-based N1/N2/N3
search and genetic route allocation with a diverse elite archive. Supplementary
Algorithms 2--7 were not supplied; their implementations follow the main text.
"""
from .common import (SearchConfig, SearchEnvironment, clone, rank,
                     ordered_crossover, environmental_select)
from ..core.models import MultiRobotSolution


def clustered_seed(env):
    """Small L1 Lloyd clustering, then depot-rooted nearest-task sequences."""
    ids=env.ids;centers=[env.centers[t] for t in env.rng.sample(ids,min(len(ids),env.instance.robot_count))]
    groups=[]
    for _ in range(5):
        groups=[[] for _ in centers]
        for t in ids:
            k=min(range(len(centers)),key=lambda k:env.distance(env.centers[t],centers[k]))
            groups[k].append(t)
        for k,g in enumerate(groups):
            if g:centers[k]=tuple(sum(env.centers[t][d] for t in g)/len(g) for d in (0,1))
    routes=[]
    for g in groups:
        route=[];point=env.instance.depot;remaining=set(g)
        while remaining:
            task=min(remaining,key=lambda t:(env.distance(point,env.centers[t]),t))
            remaining.remove(task);route.append(task);point=env.centers[task]
        routes.append(route)
    routes.extend([] for _ in range(env.instance.robot_count-len(routes)))
    return MultiRobotSolution(routes)


def sequence_cross(x,y,rng,mode):
    n=len(x)
    if n<2:return x[:]
    a,b=sorted(rng.sample(range(n+1),2))
    if mode==0:  # PMX: preserve a segment, map conflicting genes through its partner.
        child=[None]*n;child[a:b]=x[a:b]
        for i in range(n):
            if a<=i<b:continue
            value=y[i]
            while value in x[a:b]:value=y[x.index(value)]
            child[i]=value
        return child
    if mode==1:  # order-based crossover
        positions=sorted(rng.sample(range(n),max(1,n//2)))
        selected={x[i] for i in positions};ordered=iter(t for t in y if t in selected)
        child=x[:]
        for i in positions:child[i]=next(ordered)
        return child
    # Subtour inheritance, retain one parent block and preserve the other's order.
    block=x[a:b];rest=[t for t in y if t not in block]
    return rest[:a]+block+rest[a:]


def isa(env, ind, success):
    """Local route sequence GA; success-adaptive crossover types (Eq. 8)."""
    current=ind
    for k,route in enumerate(ind.solution.routes):
        if len(route)<3 or not env.active():continue
        original=current.solution.routes[k][:]
        mutant=original[:];env.rng.shuffle(mutant)
        local=[original,mutant]
        for _ in range(env.config.local_depth):
            if not env.active():break
            best=min(local,key=lambda r:env.dp.evaluate_route(r).total_cost)
            partner=env.rng.choice(local)
            mode=env.rng.choices(range(3),weights=success)[0]
            child=sequence_cross(best,partner,env.rng,mode)
            if env.rng.random()<.2:
                a,b=sorted(env.rng.sample(range(len(child)),2));child[a:b+1]=reversed(child[a:b+1])
            old_cost=env.dp.evaluate_route(best).total_cost
            new_cost=env.dp.evaluate_route(child).total_cost
            if new_cost<old_cost:success[mode]+=1
            local=sorted(local+[child],key=lambda r:env.dp.evaluate_route(r).total_cost)[:4]
        best=min(local,key=lambda r:env.dp.evaluate_route(r).total_cost)
        if best!=current.solution.routes[k]:
            out=clone(current.solution);out.routes[k]=best[:]
            current=env.evaluate(out,'ISA')
    return current


def balance(env,ind):
    """RBM: transfer progressively longer head/tail blocks MTC -> LTC."""
    costs=ind.evaluation.per_robot_costs
    a=max(range(len(costs)),key=lambda k:costs[k]);b=min(range(len(costs)),key=lambda k:costs[k])
    if a==b or not ind.solution.routes[a]:return ind
    route=ind.solution.routes[a]
    if costs[a]-costs[b]<min(env.work[t] for t in route):return ind
    best=ind
    for tail in (False,True):
        for count in range(1,len(route)+1):
            if not env.active():break
            block=route[-count:] if tail else route[:count]
            remaining=route[:-count] if tail else route[count:]
            branch=ind
            for pos in (0,len(ind.solution.routes[b])):
                out=clone(ind.solution);out.routes[a]=remaining
                out.routes[b]=out.routes[b][:pos]+block+out.routes[b][pos:]
                candidate=env.evaluate(out,'RBM_endpoint_block')
                if rank(candidate)<rank(branch):branch=candidate
            if rank(branch)<rank(best):best=branch
            else:break
    return best


def proximity(env,ind):
    costs=ind.evaluation.per_robot_costs
    nonempty=[k for k,r in enumerate(ind.solution.routes) if r]
    if len(nonempty)<2:return ind
    mode=env.rng.randrange(3)
    a=(max(nonempty,key=lambda k:costs[k]) if mode==0 else
       min(nonempty,key=lambda k:costs[k]) if mode==1 else env.rng.choice(nonempty))
    centers={k:tuple(sum(env.centers[t][d] for t in ind.solution.routes[k])/len(ind.solution.routes[k]) for d in (0,1)) for k in nonempty}
    others=[k for k in nonempty if k!=a]
    by_distance=sorted(others,key=lambda k:env.distance(centers[a],centers[k]))
    # Energy is absent in MR-RCRP; use route-duration rank, explicitly an adaptation.
    by_load=sorted(others,key=lambda k:costs[k],reverse=True)
    b=min(others,key=lambda k:(by_distance.index(k)+by_load.index(k),k))
    current=ind
    for _ in range(env.config.local_depth):
        if not env.active():break
        out=clone(current.solution)
        if not out.routes[a] or not out.routes[b]:break
        if env.rng.random()<.5:
            i=env.rng.randrange(len(out.routes[a]));t=out.routes[a].pop(i)
            out=env.insert(out,t,[b])
        else:
            i=env.rng.randrange(len(out.routes[a]));j=env.rng.randrange(len(out.routes[b]))
            out.routes[a][i],out.routes[b][j]=out.routes[b][j],out.routes[a][i]
        candidate=env.evaluate(out,f'PBOM_N{mode+1}')
        if rank(candidate)<rank(current):current=candidate
    return current


def route_allocation(env,a,b):
    """PRAM surrogate without multi-trip constraints: genetic order and breakpoints."""
    out=ordered_crossover(a.solution,b.solution,env.rng)
    if env.rng.random()<.5:
        # Change route counts while preserving the complete permutation.
        flat=[t for r in out.routes for t in r]
        cuts=sorted(env.rng.choices(range(len(flat)+1),k=env.instance.robot_count-1))
        bounds=[0]+cuts+[len(flat)]
        out=MultiRobotSolution([flat[x:y] for x,y in zip(bounds,bounds[1:])])
    return env.evaluate(out,'PRAM_genetic_allocation')


def solve(instance,config=None):
    env=SearchEnvironment(instance,config or SearchConfig(max_time=instance.task_count))
    cfg=env.config;success=[1.,1.,1.];archive=[]
    while len(archive)<cfg.population_size and env.active():
        seed=env.evaluate(clustered_seed(env),'clustered_initialization')
        archive.append(isa(env,seed,success))
    if not archive:archive=[env.initial]
    archive=environmental_select(archive,cfg.population_size)
    env.initialization_seconds=env.elapsed();generation=0
    while env.active(generation):
        balanced=[]
        for ind in archive:
            if not env.active():break
            balanced.append(isa(env,balance(env,ind),success))
        first=environmental_select(archive+balanced,cfg.population_size)
        offspring=[]
        for ind in first:
            if not env.active():break
            candidate=isa(env,proximity(env,ind),success)
            if candidate.solution.routes==ind.solution.routes:
                candidate=env.evaluate(env.neighbor(ind,'MR-Cross'),'stagnation_perturbation')
            offspring.append(candidate)
            if env.active():
                other=env.tournament(first) if len(first)>1 else first[0]
                offspring.append(isa(env,route_allocation(env,candidate,other),success))
        archive=environmental_select(first+offspring,cfg.population_size)
        generation+=1;env.record('archive_update',generation)
    env.phases.update({f'ISA_success_crossover_{i}':int(v-1) for i,v in enumerate(success)})
    return env.finish(generation)
