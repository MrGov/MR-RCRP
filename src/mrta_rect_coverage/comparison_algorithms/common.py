"""Shared evaluation, elementary moves and encodings; no population search loop."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal
import math
import random
from time import perf_counter

from ..core.cost_matrix import CostMatrix
from ..core.dp_evaluator import RouteDPEvaluator
from ..core.models import MultiRobotSolution, SolutionEvaluation, RouteEvaluation
from ..core.solution_evaluator import MultiRobotSolutionEvaluator
from ..core.state_generator import generate_all_states
from ..heuristics.constructors import spatial_sort_constructor
from ..heuristics.neighborhood import (RelocateMove, SwapMove, TwoOptMove,
    apply_relocate, apply_swap, apply_two_opt)


@dataclass
class SearchConfig:
    max_time: float = 40.0
    evaluation_mode: Literal['exact', 'greedy'] = 'exact'
    seed: int = 0
    population_size: int = 12
    max_generations: int | None = None
    scout_limit: int = 20
    local_depth: int = 8
    mutation_probability: float = 0.05
    taskshift_probability: float = 0.05
    elite_fraction: float = 0.05

    def __post_init__(self):
        if self.evaluation_mode not in ('exact', 'greedy'):
            raise ValueError('evaluation_mode must be exact or greedy')
        if not math.isfinite(self.max_time) or self.max_time <= 0:
            raise ValueError('max_time must be finite and positive')
        if self.population_size < 4 or self.local_depth < 1 or self.scout_limit < 1:
            raise ValueError('population >= 4; positive depth and scout limit required')
        if self.max_generations is not None and self.max_generations < 0:
            raise ValueError('max_generations must be nonnegative')
        if not all(0 <= p <= 1 for p in (self.mutation_probability,self.taskshift_probability,self.elite_fraction)):
            raise ValueError('probabilities must lie in [0,1]')


@dataclass
class Individual:
    solution: MultiRobotSolution
    evaluation: SolutionEvaluation

    @property
    def score(self):
        return self.evaluation.makespan


@dataclass
class SearchResult:
    best_solution: MultiRobotSolution
    best_evaluation: SolutionEvaluation
    initial_makespan: float
    runtime_seconds: float
    initialization_seconds: float
    iterations: int
    evaluations: int
    route_dp_calls: int
    cache_misses: int
    history: list[dict]
    phase_counts: dict
    search_makespan: float
    selected_search_routes: list[list[int]]
    final_recheck_seconds: float
    total_runtime_seconds: float
    greedy_calls: int
    greedy_cache_misses: int
    final_route_dp_calls: int
    deadline_reached: bool
    budget_overrun_seconds: float


class SearchDeadline(Exception):
    """Unwind nested search immediately, preserving the complete incumbent."""


class GreedyRouteEvaluator:
    """One legal state per step; no DP layers or lookahead except depot return."""
    def __init__(self, costs, states):
        self.costs, self.states = costs, states
        self.cache = {}
        self.calls = self.cache_misses = 0

    def evaluate_route(self, route):
        self.calls += 1
        key = tuple(route)
        if key in self.cache:
            return self.cache[key]
        self.cache_misses += 1
        chosen, transitions, cumulative, predecessors = [], [], [], []
        previous = None
        total = 0.0
        for position, task in enumerate(route):
            def incoming(state):
                return (self.costs.depot_to_state(state.state_id) if previous is None
                        else self.costs.transition(previous, state.state_id))
            last = position == len(route)-1
            state = min(self.states[task], key=lambda s: incoming(s) + s.processing_time
                        + (self.costs.state_to_depot(s.state_id) if last else 0.0))
            transition = incoming(state)
            total += transition + state.processing_time
            chosen.append(state); transitions.append(transition); cumulative.append(total)
            predecessors.append(previous); previous = state.state_id
        if chosen:
            transitions.append(self.costs.state_to_depot(previous))
            total += transitions[-1]
        result = RouteEvaluation(list(route), [s.state_id for s in chosen], total,
            chosen, [s.entry_point for s in chosen], [s.exit_point for s in chosen],
            cumulative, transitions, predecessors)
        self.cache[key] = result
        return result


def clone(solution):
    return MultiRobotSolution([r[:] for r in solution.routes])


def signature(individual):
    # Homogeneous robot labels do not distinguish allocations for diversity.
    return tuple(sorted(tuple(r) for r in individual.solution.routes))


def rank(individual):
    # Makespan is primary; total duration breaks exact ties without a new objective.
    return individual.score, sum(individual.evaluation.per_robot_costs)


class SearchEnvironment:
    def __init__(self, instance, config):
        self.started = perf_counter()  # Includes state/cost setup and initialization.
        self.instance, self.config = instance, config
        self.rng = random.Random(config.seed)
        states = generate_all_states(instance)
        costs = CostMatrix(instance.depot, states, travel_speed=instance.travel_speed)
        self.states, self.costs = states, costs
        self.dp = RouteDPEvaluator(costs, states)
        self.greedy = GreedyRouteEvaluator(costs, states)
        self.evaluator = MultiRobotSolutionEvaluator(self, instance=instance)
        self.work = {t:min(s.processing_time for s in ss) for t,ss in states.items()}
        self.centers = {t.task_id:((t.x_left+t.x_right)/2,(t.y_bottom+t.y_top)/2) for t in instance.tasks}
        self.ids = list(self.centers)
        self.best = None
        self.evaluations = 0
        self.history = []
        self.phases = Counter()
        self.generation = 0
        # One complete bootstrap evaluation is mandatory even for a budget smaller
        # than setup. Afterwards every route evaluation checks the same deadline.
        self._bootstrap = True
        first = self.evaluate(spatial_sort_constructor(instance), 'initial_reference')
        self._bootstrap = False
        self.initial_makespan = first.score
        self.initial = first
        self.initialization_seconds = 0.0

    def elapsed(self):
        return perf_counter()-self.started

    def active(self, generation=None):
        return self.elapsed() < self.config.max_time and (generation is None or
            self.config.max_generations is None or generation < self.config.max_generations)

    def check_deadline(self):
        if not self._bootstrap and self.elapsed() >= self.config.max_time:
            raise SearchDeadline()

    def evaluate_route(self, route):
        self.check_deadline()
        evaluator = self.dp if self.config.evaluation_mode == 'exact' else self.greedy
        return evaluator.evaluate_route(route)

    route = evaluate_route

    def evaluate(self, solution, phase):
        self.check_deadline()
        ind = Individual(solution, self.evaluator.evaluate(solution))
        self.evaluations += 1
        self.phases[phase] += 1
        if self.best is None or rank(ind) < rank(self.best):
            self.best = Individual(clone(solution), ind.evaluation)
            self.record(phase)
        return ind

    def record(self, phase, generation=0):
        if phase in ('cycle', 'archive_update', 'generation', 'colony_update', 'finished'):
            self.generation = generation
        self.history.append(dict(elapsed_seconds=self.elapsed(),best_makespan=self.best.score,
            evaluations=self.evaluations,phase=phase,generation=generation))

    def finish(self, generation):
        self.record('finished',generation)
        search_seconds = self.elapsed()
        stats = self.dp.statistics()
        # Freeze the search-selected allocation/order. Independent Exact-DP only
        # reoptimizes its legal state chain; it never reselects a search candidate.
        final_started = perf_counter()
        final_dp = RouteDPEvaluator(self.costs, self.states)
        final_dp._e13_final_recheck = True
        final = MultiRobotSolutionEvaluator(final_dp, instance=self.instance).evaluate(self.best.solution)
        recheck_seconds = perf_counter()-final_started
        return SearchResult(clone(self.best.solution),final,self.initial_makespan,
            search_seconds,self.initialization_seconds,generation,self.evaluations,
            stats['calls'],stats['cache_misses'],self.history,dict(self.phases),
            self.best.score,[r[:] for r in self.best.solution.routes],recheck_seconds,
            self.elapsed(),self.greedy.calls,self.greedy.cache_misses,
            final_dp.statistics()['calls'],search_seconds >= self.config.max_time,
            max(0.0,search_seconds-self.config.max_time))

    def random_solution(self):
        self.check_deadline()
        tasks = self.ids[:];self.rng.shuffle(tasks)
        routes = [[] for _ in range(self.instance.robot_count)]
        for t in tasks:routes[self.rng.randrange(len(routes))].append(t)
        return MultiRobotSolution(routes)

    def distance(self,a,b):
        return abs(a[0]-b[0])+abs(a[1]-b[1])

    def insert(self, solution, task, robots=None):
        """Best insertion using the configured evaluator, including partial routes."""
        costs = [self.route(r).total_cost for r in solution.routes]
        best = None
        for k in (range(len(costs)) if robots is None else robots):
            r = solution.routes[k]
            for p in range(len(r)+1):
                c = self.route(r[:p]+[task]+r[p:]).total_cost
                score = (max([c]+[v for j,v in enumerate(costs) if j!=k]),c-costs[k],k,p)
                if best is None or score < best:best=score
        out = clone(solution);out.routes[best[2]].insert(best[3],task)
        return out

    def construct(self, order, *, top_k=None):
        out = MultiRobotSolution([[] for _ in range(self.instance.robot_count)])
        for task in order:
            self.check_deadline()
            robots=None
            if top_k:
                costs=[self.route(r).total_cost for r in out.routes]
                robots=[self.rng.choice(sorted(range(len(costs)),key=lambda k:costs[k])[:top_k])]
            out=self.insert(out,task,robots)
        return out

    def critical(self, ind):
        return max(range(len(ind.solution.routes)),key=lambda k:ind.evaluation.per_robot_costs[k])

    def neighbor(self, ind, kind, *, critical=False, best_insert=False):
        """Six literature neighborhoods, sharing the project's elementary moves."""
        self.check_deadline()
        s=ind.solution;rng=self.rng
        occupied=[k for k,r in enumerate(s.routes) if r]
        if not occupied:return clone(s)
        a=self.critical(ind) if critical else rng.choice(occupied)
        if not s.routes[a]:a=rng.choice(occupied)
        i=rng.randrange(len(s.routes[a]))
        if kind.startswith('SR'):
            if len(s.routes[a])<2:return clone(s)
            j=rng.choice([p for p in range(len(s.routes[a])) if p!=i])
            if kind=='SR-Insert':
                if best_insert:
                    out=clone(s);t=out.routes[a].pop(i)
                    return self.insert(out,t,[a])
                return apply_relocate(s,RelocateMove(a,i,a,j))
            if kind=='SR-Exchange':return apply_swap(s,SwapMove(a,i,a,j))
            return apply_two_opt(s,TwoOptMove(a,min(i,j),max(i,j)))
        others=[k for k in range(len(s.routes)) if k!=a]
        if not others:return clone(s)
        b=rng.choice(others)
        if kind=='MR-Insert':
            if not critical and ind.evaluation.per_robot_costs[a]<ind.evaluation.per_robot_costs[b] and s.routes[b]:
                a,b=b,a;i=rng.randrange(len(s.routes[a]))
            if best_insert:
                out=clone(s);t=out.routes[a].pop(i)
                return self.insert(out,t,[b])
            return apply_relocate(s,RelocateMove(a,i,b,rng.randrange(len(s.routes[b])+1)))
        if kind=='MR-Exchange':
            if not s.routes[b]:return clone(s)
            return apply_swap(s,SwapMove(a,i,b,rng.randrange(len(s.routes[b]))))
        out=clone(s);j=rng.randrange(len(s.routes[b])+1)
        out.routes[a],out.routes[b]=s.routes[a][:i]+s.routes[b][j:],s.routes[b][:j]+s.routes[a][i:]
        return out

    def tournament(self, population):
        return min(self.rng.sample(population,2),key=rank)


KINDS=('SR-Insert','SR-Exchange','SR-Cross','MR-Insert','MR-Exchange','MR-Cross')


def ordered_crossover(a,b,rng,mode=0):
    """Permutation+route-count encoding; OX, order-based or subtour inheritance."""
    x=[t for r in a.routes for t in r];y=[t for r in b.routes for t in r]
    n=len(x)
    if n<2:return clone(a)
    lo,hi=sorted(rng.sample(range(n+1),2))
    child=[None]*n
    if mode==1:
        positions=sorted(rng.sample(range(n),max(1,n//2)))
    else:positions=list(range(lo,hi))
    for i in positions:child[i]=x[i]
    used={t for t in child if t is not None}
    remaining=iter(t for t in y if t not in used)
    for i in range(n):
        if child[i] is None:child[i]=next(remaining)
    counts=[len(r) for r in (a.routes if rng.random()<.5 else b.routes)]
    out=[];start=0
    for count in counts:out.append(child[start:start+count]);start+=count
    return MultiRobotSolution(out)


def environmental_select(population, size, check=None):
    if check:check()
    ordered=sorted(population,key=rank);unique=[];seen=set()
    for ind in ordered:
        if check:check()
        key=signature(ind)
        if key not in seen:unique.append(ind);seen.add(key)
    if len(unique)<size:
        unique.extend(ordered[:size-len(unique)])
    return unique[:size]


def run_search(instance, config, search):
    """Deadline unwinding only; population mechanisms remain in each algorithm."""
    env = SearchEnvironment(instance, config)
    try:
        generation = search(env)
    except SearchDeadline:
        generation = env.generation
    if not env.initialization_seconds:
        env.initialization_seconds = env.elapsed()
    return env.finish(generation)
