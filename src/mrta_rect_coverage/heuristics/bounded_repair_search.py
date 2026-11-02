"""Host-owned depth-two repair search; isolated code only ranks task-pair IDs.

No single-task costs are added as joint estimates. Every second insertion is
priced against the actual route created by the first insertion. All robots and
all slots are eligible. The greedy incumbent and every tail completion use the
existing solver repair; all their insertion prices count against the same cap.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
import random
from time import perf_counter

from ..core.models import MultiRobotSolution
from ..llm.operator_evolution.candidate_execution import CandidateProxy
from ..llm.operator_evolution.candidate_security import code_sha256, validate_candidate_source
from ..llm.operator_evolution.persistent_candidate_execution import PersistentCandidateProxy


@dataclass(frozen=True)
class SearchBudget:
    max_tasks: int = 6
    max_pairs: int = 2
    first_width: int = 3
    second_width: int = 2
    completions_per_pair: int = 2
    max_expansions: int = 36
    max_prices: int = 4096

    def __post_init__(self):
        if any(v < 0 for v in asdict(self).values()) or self.max_prices < 1:
            raise ValueError("nonnegative search caps and positive price budget required")


def reference_rank_pairs(features, rng):
    """Fixed reference: prioritize high exact singleton regret, then slot conflict."""
    return [p['id'] for p in sorted(features['pairs'], key=lambda p: (
        -p['regret_sum'], -int(p['same_best_slot']), p['id']))]


def validate_pair_ids(result, features):
    ids = [p['id'] for p in features['pairs']]
    if (not isinstance(result, list) or any(type(x) is not str for x in result)
            or len(result) != len(ids) or set(result) != set(ids)):
        raise ValueError("strategy must return a permutation of supplied pair identifiers")
    return result


class StrategyExecutor:
    """Reuse hash-bound subprocesses. Fresh namespace and validation on every call."""
    def __init__(self, path, *, expected_hash=None, executor='warm', timeout_ms=150):
        started = perf_counter()
        self.path = Path(path)
        source = self.path.read_text(encoding='utf-8')
        self.code_hash = code_sha256(source)
        if expected_hash and expected_hash != self.code_hash:
            raise ValueError('strategy source hash mismatch')
        validate_candidate_source(source, 'pair_strategy')
        proxy = CandidateProxy(self.path, 'pair_strategy', self.code_hash, timeout_ms)
        if executor not in ('warm', 'original'):
            raise ValueError('unknown executor')
        self.backend = PersistentCandidateProxy.from_validated(proxy) if executor == 'warm' else proxy
        self.loading_seconds = perf_counter() - started
        self.samples = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if isinstance(self.backend, PersistentCandidateProxy):
            self.backend.close()
        self.closed = True

    def __call__(self, features, rng):
        if self.closed:
            raise RuntimeError('strategy executor closed')
        # Original and resident receive copies, including identical RNG state.
        try:
            outcome = self.backend.execute((deepcopy(features), deepcopy(rng)), timeout_ms=self.backend.timeout_ms)
            self.samples.append({k: getattr(outcome, k) for k in
                ('status', 'wall_time_ms', 'runtime_ms', 'startup_ms', 'validation_import_ms')})
            if outcome.status != 'success':
                raise RuntimeError(f'{outcome.status}: {outcome.error_message}')
            return validate_pair_ids(outcome.result, features)
        except BaseException:
            self.close()
            raise

    def statistics(self):
        return {'hash': self.code_hash, 'loading_seconds': self.loading_seconds,
                'calls': len(self.samples), 'samples': self.samples, 'closed': self.closed}


class _BudgetedPrices:
    def __init__(self, base, limit):
        self.base, self.limit, self.used = base, limit, 0

    def insertion_costs(self, route, task_id):
        needed = len(route) + 1
        if self.used + needed > self.limit:
            raise RuntimeError('exact pricing budget exceeded')
        self.used += needed
        return self.base.insertion_costs(route, task_id)


def _tail_cost(routes, count):
    slots = sum(map(len, routes)) + len(routes)
    return count * slots + count * (count - 1) // 2


class BoundedRepairSearch:
    def __init__(self, solver, *, ranker=reference_rank_pairs, budget=None):
        self.solver, self.ranker = solver, ranker
        self.budget = budget or SearchBudget()
        self.records = []

    def __call__(self, partial, removed, partial_eval):
        start = perf_counter()
        s, cap = self.solver, self.budget
        routes, tasks = deepcopy(partial.routes), list(removed)
        full_ids = sorted(t.task_id for t in s.instance.tasks)
        if (len(routes) != s.instance.robot_count or
                sorted([t for r in routes for t in r] + tasks) != full_ids):
            raise ValueError('invalid partial solution / removed task coverage')
        if _tail_cost(routes, len(tasks)) > cap.max_prices:
            raise ValueError('price cap cannot fund common greedy completion for this input')
        pricer = _BudgetedPrices(s.insertion_pricer, cap.max_prices)
        before = s.insertion_pricer.statistics()
        dp_before = s.route_dp.statistics()
        record = {'config': asdict(cap), 'selected_pairs': [], 'joint_branches': [],
                  'completions': [], 'expansions': 0, 'budget_stop': False,
                  'strategy_error': None, 'features': None, 'ranked_pairs': []}

        def complete(rr, remaining):
            original = s.insertion_pricer
            try:
                s.insertion_pricer = pricer
                pp = MultiRobotSolution(deepcopy(rr))
                return s._greedy_insertion(pp, list(remaining), s.solution_evaluator.evaluate_partial(pp))
            finally:
                s.insertion_pricer = original

        def options(rr, costs, task):
            result = []
            for robot, route in enumerate(rr):
                others = max((v for i, v in enumerate(costs) if i != robot), default=0.)
                for pos, cost in enumerate(pricer.insertion_costs(route, task)):
                    newcosts = list(costs)
                    newcosts[robot] = cost
                    result.append({'robot': robot, 'position': pos, 'cost': cost,
                                   'makespan': max(others, cost), 'total': sum(newcosts)})
            return sorted(result, key=lambda p: (p['makespan'], p['total'], p['robot'], p['position']))

        def apply(rr, costs, task, opt):
            newroutes, newcosts = deepcopy(rr), list(costs)
            newroutes[opt['robot']].insert(opt['position'], task)
            newcosts[opt['robot']] = opt['cost']
            record['expansions'] += 1
            return newroutes, newcosts

        incumbent = complete(routes, tasks)
        incumbent_eval = s.solution_evaluator.evaluate(incumbent)
        record['greedy_makespan'] = incumbent_eval.makespan
        best = incumbent
        best_key = (incumbent_eval.makespan, sum(incumbent_eval.per_robot_costs))
        base_costs = list(s.solution_evaluator.evaluate_partial(MultiRobotSolution(routes)).per_robot_costs)
        slots = sum(map(len, routes)) + len(routes)
        if len(tasks) >= 2 and cap.max_expansions and pricer.used + slots * len(tasks) <= cap.max_prices:
            singleton = {t: options(routes, base_costs, t) for t in tasks}
            task_features = {}
            for t, opts in singleton.items():
                region = next(x for x in s.instance.tasks if x.task_id == t)
                task_features[str(t)] = {
                    'best': opts[0], 'regret': opts[1]['makespan'] - opts[0]['makespan'] if len(opts)>1 else 0.,
                    'top_slots': opts[:6],
                    'best_by_robot': [min((x for x in opts if x['robot']==r), key=lambda x: x['cost']) for r in range(len(routes))],
                    'center': [(region.x_left+region.x_right)/2, (region.y_bottom+region.y_top)/2],
                }
            pool = sorted(tasks, key=lambda t: (-task_features[str(t)]['regret'], t))[:cap.max_tasks]
            pairs = []
            for a, b in combinations(sorted(pool), 2):
                x, y = task_features[str(a)], task_features[str(b)]
                pairs.append({'id': f'{a}:{b}', 'tasks': [a,b], 'regret_sum': x['regret']+y['regret'],
                              'same_best_robot': x['best']['robot']==y['best']['robot'],
                              'same_best_slot': (x['best']['robot'],x['best']['position'])==(y['best']['robot'],y['best']['position']),
                              'center_distance': sum(abs(u-v) for u,v in zip(x['center'],y['center']))})
            features = {'pairs': pairs, 'tasks': task_features, 'routes': routes, 'route_costs': base_costs,
                        'budget': asdict(cap), 'prices_remaining': cap.max_prices-pricer.used}
            record['features'] = deepcopy(features)
            try:
                ranked = validate_pair_ids(self.ranker(deepcopy(features), deepcopy(s.rng)), features)
            except Exception as exc:
                ranked = []
                record['strategy_error'] = f'{type(exc).__name__}: {exc}'
            pair_map = {p['id']: p['tasks'] for p in pairs}
            record['ranked_pairs'] = list(ranked)
            for pair_id in ranked[:cap.max_pairs]:
                # Reserve every planned greedy tail before adding any branch.
                tail_prices = _tail_cost(routes, len(tasks)) - (2*slots + 1)
                reserve = cap.completions_per_pair * tail_prices
                expand_prices = 2 * cap.first_width * (slots + 1)
                expand_count = 2 * cap.first_width * (1 + cap.second_width)
                if (pricer.used + reserve + expand_prices > cap.max_prices or
                        record['expansions'] + expand_count > cap.max_expansions):
                    record['budget_stop'] = True
                    break
                record['selected_pairs'].append(pair_id)
                a, b = pair_map[pair_id]
                leaves = []
                for first, second in ((a,b), (b,a)):
                    for first_rank, opt in enumerate(singleton[first][:cap.first_width]):
                        rr, costs = apply(routes, base_costs, first, opt)
                        seconds = options(rr, costs, second)
                        for next_opt in seconds[:cap.second_width]:
                            rr2, costs2 = apply(rr, costs, second, next_opt)
                            leaf = {'pair': pair_id, 'order': [first,second], 'first_rank': first_rank,
                                    'robots': [opt['robot'],next_opt['robot']],
                                    'positions': [opt['position'],next_opt['position']],
                                    'routes': rr2, 'costs': costs2, 'makespan': max(costs2)}
                            leaves.append(leaf)
                            record['joint_branches'].append(leaf)
                # Select distinct route sequences by exact partial objective, no independent-delta sum.
                unique = {}
                for leaf in sorted(leaves, key=lambda l: (l['makespan'],sum(l['costs']))):
                    unique.setdefault(tuple(map(tuple,leaf['routes'])), leaf)
                for leaf in list(unique.values())[:cap.completions_per_pair]:
                    full = complete(leaf['routes'], [t for t in tasks if t not in (a,b)])
                    evaluation = s.solution_evaluator.evaluate(full)
                    key = (evaluation.makespan, sum(evaluation.per_robot_costs))
                    record['completions'].append({'branch': leaf, 'routes': full.routes, 'makespan': key[0],
                                                  'costs': evaluation.per_robot_costs})
                    if key < best_key:
                        best, best_key = full, key
        elif len(tasks) >= 2:
            record['budget_stop'] = True
        if not s._is_valid_full_solution(best):
            raise RuntimeError('host search violated task coverage')
        after = s.insertion_pricer.statistics()
        dp_after = s.route_dp.statistics()
        record.update(price_requests=pricer.used, makespan=best_key[0], routes=deepcopy(best.routes),
                      pricing_work={k: after[k]-before[k] for k in (
                          'table_builds','insertion_prices','price_cache_hits',
                          'insertion_requests','insertion_cache_hits','insertion_computations',
                          'table_build_seconds','insertion_compute_seconds')},
                      dp_work={k: dp_after[k]-dp_before[k] for k in ('calls','cache_misses')},
                      runtime_seconds=perf_counter()-start)
        self.records.append(record)
        return best
