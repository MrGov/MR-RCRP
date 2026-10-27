"""SGA-TS adaptation of Seo & Lee, RAS 205 (2026) 105664, Section 4.

Permutation/count chromosomes, half crossover with duplicate repair, roulette,
5% swap/reverse/count/TaskShift mutation and elite preservation. JPS encounters
are approximated by proximity to a shortest Manhattan corridor between actual
DP exit/entry points. Transfers additionally pass a real DP nonworsening guard
because MR-RCRP tasks have nonzero and strongly variable service time.
"""
import math
from .common import SearchConfig, SearchEnvironment, clone, rank
from ..core.models import MultiRobotSolution


def split(flat,counts):
    routes=[];start=0
    for count in counts:routes.append(flat[start:start+count]);start+=count
    return MultiRobotSolution(routes)


def half_crossover(a,b):
    """Section 4.1.4: better-parent first half, weaker-parent second half."""
    if rank(b)<rank(a):a,b=b,a
    x=[t for r in a.solution.routes for t in r];y=[t for r in b.solution.routes for t in r]
    cut=len(x)//2;raw=x[:cut]+y[cut:]
    missing=iter(t for t in x if t not in raw);seen=set();child=[]
    for task in raw:
        if task in seen:task=next(missing)
        child.append(task);seen.add(task)
    return [split(child[:],[len(r) for r in parent.solution.routes]) for parent in (a,b)]


def taskshift(env,ind):
    """Deterministic, path-triggered bottleneck reassignment; never random relocate."""
    current=ind;radius=2*env.instance.sweep_width
    for receiver in range(env.instance.robot_count):
        if not env.active():break
        evaluation=current.evaluation.route_evaluations[receiver]
        if not evaluation.chosen_states:continue
        starts=[env.instance.depot]+evaluation.exit_points
        ends=evaluation.entry_points+[env.instance.depot]
        # Snapshot segment indexes/anchors, independent of mutations while scanning.
        anchors=current.solution.routes[receiver][:]
        encounters=[]
        for pos,(start,end) in enumerate(zip(starts,ends)):
            for task in env.ids:
                if task in anchors:continue
                point=env.centers[task]
                excess=env.distance(start,point)+env.distance(point,end)-env.distance(start,end)
                if excess<=radius:
                    encounters.append((pos,excess,task))
        seen=set()
        for pos,excess,task in sorted(encounters):
            if task in seen or not env.active():continue
            seen.add(task);donor=next(k for k,r in enumerate(current.solution.routes) if task in r)
            costs=current.evaluation.per_robot_costs
            if donor==receiver or costs[donor]<max(costs)-1e-9 or costs[receiver]>=costs[donor]:continue
            out=clone(current.solution);out.routes[donor].remove(task)
            # Preserve snapshot's natural insertion anchor despite previous transfers.
            anchor=anchors[pos] if pos<len(anchors) else None
            insertion=out.routes[receiver].index(anchor) if anchor in out.routes[receiver] else len(out.routes[receiver])
            out.routes[receiver].insert(insertion,task)
            candidate=env.evaluate(out,'TaskShift_candidate')
            if rank(candidate)<rank(current):
                current=candidate;env.phases['TaskShift_transfer']+=1
    return current


def mutate(env,solution):
    rng=env.rng;cfg=env.config
    flat=[t for r in solution.routes for t in r];counts=[len(r) for r in solution.routes]
    if len(flat)>1 and rng.random()<cfg.mutation_probability:
        a,b=rng.sample(range(len(flat)),2);flat[a],flat[b]=flat[b],flat[a]
        env.phases['swap_mutation']+=1
    if len(flat)>1 and rng.random()<cfg.mutation_probability:
        a,b=sorted(rng.sample(range(len(flat)),2));flat[a:b+1]=reversed(flat[a:b+1])
        env.phases['reverse_mutation']+=1
    if rng.random()<cfg.mutation_probability:
        cuts=sorted(rng.choices(range(len(flat)+1),k=len(counts)-1));bounds=[0]+cuts+[len(flat)]
        counts=[b-a for a,b in zip(bounds,bounds[1:])];env.phases['count_mutation']+=1
    return split(flat,counts)


def solve(instance,config=None):
    env=SearchEnvironment(instance,config or SearchConfig(max_time=instance.task_count))
    cfg=env.config;rng=env.rng
    order=sorted(env.ids,key=lambda t:env.work[t],reverse=True)
    population=[env.evaluate(env.construct(order),'greedy_seed')]
    while len(population)<cfg.population_size and env.active():
        population.append(env.evaluate(env.random_solution(),'random_initialization'))
    env.initialization_seconds=env.elapsed();generation=0
    while env.active(generation):
        children=[]
        while len(children)<cfg.population_size and env.active():
            parents=rng.choices(population,weights=[1/max(1e-9,p.score) for p in population],k=2)
            for child in half_crossover(*parents):
                if not env.active():break
                individual=env.evaluate(mutate(env,child),'genetic_offspring')
                if rng.random()<cfg.taskshift_probability:
                    env.phases['TaskShift_calls']+=1
                    individual=taskshift(env,individual)
                children.append(individual)
                if len(children)>=cfg.population_size:break
        if children:
            elites=sorted(population,key=rank)[:max(1,math.ceil(cfg.elite_fraction*cfg.population_size))]
            # Replace worst offspring only when the elite is better.
            for elite in elites:
                worst=max(range(len(children)),key=lambda i:rank(children[i]))
                if rank(elite)<rank(children[worst]):children[worst]=elite
            population=children
        generation+=1;env.record('generation',generation)
    return env.finish(generation)
