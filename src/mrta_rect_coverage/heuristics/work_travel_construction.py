"""Budgeted work/travel insertion construction for the structural portfolio.

Task ordering and (makespan, marginal route cost) insertion ranking follow the
first heuristic in this project's CDABC adaptation (Guo et al., KBS 2024,
Section 4.2). This is a deterministic initialization contribution, not LLM work.
The deployment changes are incremental exact insertion pricing, a retained
complete spatial incumbent, and explicit deadline/price limits. Search is intact.
"""
from __future__ import annotations

from time import perf_counter

from ..core.models import MultiRobotSolution


class _ConstructionStop(Exception):
    pass


def improve_initialization(solver, *, deadline, price_cap=10000):
    """Replace solver.initial_solution only with a complete, verified better seed.

The caller sets an absolute construction deadline within the end-to-end solve
allowance and subtracts *all* setup time before solve(). No instance-ID rules,
cached external solutions, stochastic draws, or acceptance changes are used.
"""
    started = perf_counter()
    row = {'status': 'complete', 'price_requests': 0, 'assigned_tasks': 0,
           'selected': 'spatial_sort', 'selected_costs': None, 'stages': [],
           'deadline': deadline, 'price_cap': price_cap}

    def check():
        if perf_counter() >= deadline:
            raise _ConstructionStop('budget_exhausted')

    def evaluate_complete(solution):
        # Check before every uncached route; final integrity check reuses them.
        for route in solution.routes:
            check()
            solver.route_dp.evaluate_route(route)
        check()
        return solver.solution_evaluator.evaluate(solution)

    try:
        check()
        original = evaluate_complete(solver.initial_solution)
        row['selected_costs'] = original.per_robot_costs
        row['bootstrap_makespan'] = original.makespan
        row['stages'].append({'phase': 'spatial_sort', 'makespan': original.makespan})
        instance = solver.instance
        ids = [t.task_id for t in instance.tasks]
        work = {t: min(s.processing_time for s in solver.states_by_task[t]) for t in ids}
        travel = {t.task_id: (abs((t.x_left + t.x_right) / 2 - instance.depot[0]) +
                             abs((t.y_bottom + t.y_top) / 2 - instance.depot[1])) /
                            instance.travel_speed for t in instance.tasks}
        def normalized(values):
            lo, hi = min(values.values()), max(values.values())
            return {t: (values[t] - lo) / max(1e-12, hi - lo) for t in ids}
        nw, nt = normalized(work), normalized(travel)
        travel_tasks = [t for t in ids if nt[t] > nw[t]]
        process_tasks = [t for t in ids if nt[t] <= nw[t]]
        order = sorted(travel_tasks, key=travel.get) + sorted(process_tasks, key=work.get, reverse=True)
        row['task_order'] = order
        routes = [[] for _ in range(instance.robot_count)]
        costs = [0.] * instance.robot_count
        for task in order:
            check()
            best = None
            for robot, route in enumerate(routes):
                check()
                tables = solver.insertion_pricer.tables(route)
                other = max((c for j, c in enumerate(costs) if j != robot), default=0.)
                for position in range(len(route) + 1):
                    check()
                    if row['price_requests'] >= price_cap:
                        raise _ConstructionStop('price_cap')
                    row['price_requests'] += 1
                    cost = solver.insertion_pricer.insertion_cost_at(tables, position, task)
                    option = (max(other, cost), cost - costs[robot], robot, position, cost)
                    if best is None or option < best:
                        best = option
            _, _, robot, position, cost = best
            routes[robot].insert(position, task)
            costs[robot] = cost
            row['assigned_tasks'] += 1
        candidate = MultiRobotSolution(routes)
        evaluation = evaluate_complete(candidate)
        row['stages'].append({'phase': 'work_travel_exact', 'makespan': evaluation.makespan,
                              'per_robot_costs': evaluation.per_robot_costs,
                              'elapsed_seconds': perf_counter() - started})
        if (evaluation.makespan, sum(evaluation.per_robot_costs)) < (original.makespan, sum(original.per_robot_costs)):
            solver.initial_solution = candidate
            row['selected'] = 'work_travel_exact'
            row['selected_costs'] = evaluation.per_robot_costs
    except _ConstructionStop as exc:
        row['status'] = str(exc)
    row['elapsed_seconds'] = perf_counter() - started
    return row
