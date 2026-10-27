"""CDABC adapted from Guo et al., KBS 289 (2024) 111474, Section 4.

Two heuristic seeds, dynamic strategy lists, critical onlookers, two retained
collaborative following bees per source, and follower-guided scout escape.
"""
from .common import SearchConfig, SearchEnvironment, rank, clone


def solve(instance, config=None):
    env=SearchEnvironment(instance,config or SearchConfig(max_time=instance.task_count,scout_limit=50))
    rng=env.rng;cfg=env.config
    # Section 4.2: normalized dominant work/depot groups plus descending work.
    work=env.work;dist={t:env.distance(env.centers[t],instance.depot)/instance.travel_speed for t in env.ids}
    def norm(values,t):
        lo,hi=min(values.values()),max(values.values())
        return (values[t]-lo)/max(1e-12,hi-lo)
    travel=[t for t in env.ids if norm(dist,t)>norm(work,t)]
    process=[t for t in env.ids if t not in travel]
    orders=[sorted(travel,key=dist.get)+sorted(process,key=work.get,reverse=True),sorted(env.ids,key=work.get,reverse=True)]
    pop=[]
    for order in orders:
        if env.active():pop.append(env.evaluate(env.construct(order),'heuristic_initialization'))
    while len(pop)<cfg.population_size and env.active():pop.append(env.evaluate(env.random_solution(),'random_initialization'))
    if not pop:pop=[env.initial]
    followers=[[] for _ in pop];trials=[0]*len(pop)
    env.initialization_seconds=env.elapsed();generation=0

    def follow(i,candidate):
        old=pop[i]
        if rank(candidate)<rank(old):
            pop[i]=candidate;followers[i]=[old];trials[i]=0
        else:
            followers[i]=sorted(followers[i]+[candidate],key=rank)[:2];trials[i]+=1

    while env.active(generation):
        # Section 4.5: load-dependent depth and shuffled four-operator strategy list.
        ratio=instance.task_count/instance.robot_count
        depth=1 if ratio<15 else 2 if ratio<25 else 3
        strategies=['SR-Insert','SR-Exchange','MR-Insert','MR-Exchange']
        rng.shuffle(strategies)
        for i in range(len(pop)):
            if not env.active():break
            current=pop[i]
            for j in range(rng.randint(1,depth)):
                if not env.active():break
                current=env.evaluate(env.neighbor(current,strategies[(i+j)%4],best_insert=True),'employed')
            follow(i,current)
        for _ in range(len(pop)):
            if not env.active() or len(pop)<2:break
            chosen=env.tournament(pop);i=next(j for j,x in enumerate(pop) if x is chosen)
            current=chosen
            for kind in ('MR-Insert','MR-Exchange','SR-Exchange'):
                if not env.active():break
                c=env.evaluate(env.neighbor(current,kind,critical=True,best_insert=True),'onlooker_critical')
                if rank(c)<rank(current):current=c
            follow(i,current)
            worst=max(range(len(pop)),key=lambda j:rank(pop[j]))
            if rank(current)<rank(pop[worst]):pop[worst]=current;trials[worst]=0;followers[worst]=[]
        for i in range(len(pop)):
            if not env.active():break
            if trials[i]<cfg.scout_limit:continue
            current=rng.choice(followers[i]) if followers[i] else pop[i]
            for kind in ('SR-Exchange','MR-Exchange','SR-Insert','MR-Insert'):
                if not env.active():break
                current=env.evaluate(env.neighbor(current,kind,best_insert=True),'scout_collaborative')
            pop[i]=current;trials[i]=0;followers[i]=[]
        # Global best is independently retained even if scouts replace its source.
        generation+=1;env.record('cycle',generation)
    return env.finish(generation)
