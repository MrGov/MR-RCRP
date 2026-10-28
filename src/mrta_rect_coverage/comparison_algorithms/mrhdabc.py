"""MRHDABC adapted from ABC-Bi.pdf, Section 4, Algorithms 1--7.

Homogeneous MRNEH/MRNEHIG/IG/random initialization, all six neighborhoods,
ordinary employed search, binary-tournament critical onlookers, multi-operator
scouts and random/guided restarts. Spatial groups stand in for original regions;
no capacity, heterogeneity, permissions or multiple depot trips are introduced.
"""
from .common import SearchConfig, SearchEnvironment, run_search, KINDS, clone, rank


def grouped_order(env,priority,random_within=False):
    """Intrinsic angular sectors stand in for the paper's given farming regions."""
    import math
    # Equal-count angular sectors avoid collapsing all first-quadrant tasks
    # into one group (all current benchmarks place depot at the lower left).
    ordered=sorted(env.ids,key=lambda t:(math.atan2(env.centers[t][1]-env.instance.depot[1],
        env.centers[t][0]-env.instance.depot[0]),t))
    groups=[ordered[k*len(ordered)//env.instance.robot_count:(k+1)*len(ordered)//env.instance.robot_count]
            for k in range(env.instance.robot_count)]
    env.rng.shuffle(groups);out=[]
    for group in groups:
        if random_within:env.rng.shuffle(group)
        else:group.sort(key=priority.get,reverse=True)
        out.extend(group)
    return out


def solve(instance, config=None):
    return run_search(instance, config or SearchConfig(max_time=instance.task_count,scout_limit=150,local_depth=5), _search)


def _search(env):
    instance=env.instance
    cfg=env.config;rng=env.rng
    # MR priority is underspecified in the supplied algorithm. Normalize true
    # minimum service workload and depot travel equally, with 10% perturbation.
    distance={t:env.distance(env.centers[t],instance.depot)/instance.travel_speed for t in env.ids}
    maxwork=max(env.work.values());maxdist=max(distance.values())
    priority={t:(env.work[t]/maxwork+distance[t]/max(1e-12,maxdist))*rng.uniform(.9,1.1) for t in env.ids}
    pop=[];quarter=max(1,cfg.population_size//4)
    for i in range(cfg.population_size):
        if not env.active():break
        if i==0:
            order=sorted(env.ids,key=priority.get,reverse=True)
            # Adaptive swap perturbation in MRNEH before exact best-position insertion.
            if len(order)>1:
                a,b=rng.sample(range(len(order)),2);order[a],order[b]=order[b],order[a]
            solution=env.construct(order,top_k=min(3,instance.robot_count));phase='MRNEH_initialization'
        elif i<=quarter:
            solution=env.construct(grouped_order(env,priority),top_k=min(3,instance.robot_count));phase='MRNEHIG_initialization'
        elif i<=2*quarter:
            solution=env.construct(grouped_order(env,priority,True));phase='IG_initialization'
        else:solution=env.random_solution();phase='random_initialization'
        pop.append(env.evaluate(solution,phase))
    if not pop:pop=[env.initial]
    trials=[0]*len(pop);env.initialization_seconds=env.elapsed();generation=0
    while env.active(generation):
        for i in range(len(pop)):
            if not env.active():break
            current=pop[i];improved=False
            for _ in range(cfg.local_depth):
                if not env.active():break
                kind=rng.choice(KINDS)
                current=env.evaluate(env.neighbor(current,kind),'employed_'+kind)
                if current.score<pop[i].score-1e-9:
                    pop[i]=current;trials[i]=0;improved=True;break
            if not improved:trials[i]+=1
        for _ in range(len(pop)):
            if not env.active() or len(pop)<2:break
            parent=env.tournament(pop);kind=rng.choice(KINDS)
            candidate=env.evaluate(env.neighbor(parent,kind,critical=True),'onlooker_critical_'+kind)
            worst=max(range(len(pop)),key=lambda j:rank(pop[j]))
            if candidate.score<pop[worst].score-1e-9:pop[worst]=candidate;trials[worst]=0
            else:trials[worst]+=1
        for i in range(len(pop)):
            if not env.active():break
            if trials[i]<=cfg.scout_limit:continue
            improved=False;current=pop[i]
            actions=[(kind,flag) for kind in KINDS for flag in (False,True)];rng.shuffle(actions)
            for kind,critical in actions:
                if not env.active():break
                current=env.evaluate(env.neighbor(current,kind,critical=critical),'scout_multi_operator')
                if current.score<pop[i].score-1e-9:
                    pop[i]=current;improved=True;break
            if not improved and env.active():
                if rng.random()<.5:
                    pop[i]=env.evaluate(env.random_solution(),'scout_random_restart')
                else:
                    current=env.best
                    for _ in range(max(2,instance.task_count//5)):
                        if not env.active():break
                        current=env.evaluate(env.neighbor(current,rng.choice(KINDS)),'scout_guided_restart')
                    pop[i]=current
            trials[i]=0
        # Homogeneous counterpart of round-based load balance: critical-to-lowest
        # route best insertion using Exact-DP time, without extra depot rounds.
        if env.active():
            elite=min(pop,key=rank);a=env.critical(elite)
            b=min(range(instance.robot_count),key=lambda k:elite.evaluation.per_robot_costs[k])
            best=elite
            for t in elite.solution.routes[a]:
                if not env.active() or a==b:break
                out=clone(elite.solution);out.routes[a].remove(t);out=env.insert(out,t,[b])
                candidate=env.evaluate(out,'critical_load_balance')
                if rank(candidate)<rank(best):best=candidate
            worst=max(range(len(pop)),key=lambda j:rank(pop[j]))
            if rank(best)<rank(pop[worst]):pop[worst]=best;trials[worst]=0
        generation+=1;env.record('colony_update',generation)
    return generation
