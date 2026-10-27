from pathlib import Path
import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.models import MultiRobotSolution

ROOT = Path(__file__).resolve().parents[1]


def check_solver(module):
    from importlib import import_module
    implementation = import_module('mrta_rect_coverage.comparison_algorithms.' + module)
    from mrta_rect_coverage.comparison_algorithms.common import SearchConfig, SearchEnvironment
    instance = load_instance(ROOT / 'data/R2_T10_0.txt')
    config = SearchConfig(max_time=30, max_generations=4, population_size=6, seed=3)
    a = implementation.solve(instance, config)
    b = implementation.solve(instance, config)
    assert a.best_solution.routes == b.best_solution.routes
    assert a.best_evaluation.makespan == b.best_evaluation.makespan
    assert a.iterations == b.iterations == 4
    assert a.history and a.evaluations > config.population_size
    assert a.best_evaluation.makespan <= a.initial_makespan
    assert all(x['best_makespan'] >= y['best_makespan'] for x,y in zip(a.history,a.history[1:]))
    ev = SearchEnvironment(instance, SearchConfig(max_time=1)).evaluator
    assert ev.evaluate(a.best_solution).makespan == a.best_evaluation.makespan
    assert sorted(t for r in a.best_solution.routes for t in r) == sorted(t.task_id for t in instance.tasks)
    assert a.phase_counts


def test_cdabc_complete_repeatable_search():
    check_solver('cdabc')


def test_rnsga_complete_repeatable_search():
    check_solver('rnsga')


def test_sga_ts_complete_repeatable_search():
    check_solver('sga_ts')


def test_mrhdabc_complete_repeatable_search():
    check_solver('mrhdabc')


def test_all_six_neighborhoods_preserve_complete_task_multiset():
    from mrta_rect_coverage.comparison_algorithms.common import SearchConfig, SearchEnvironment, KINDS
    instance=load_instance(ROOT/'data/R2_T10_0.txt')
    env=SearchEnvironment(instance,SearchConfig(max_time=5))
    for kind in KINDS:
        for critical in (False,True):
            for _ in range(10):
                solution=env.neighbor(env.initial,kind,critical=critical)
                ev=env.evaluator.evaluate(solution)
                assert ev.makespan>0
                assert sorted(t for r in solution.routes for t in r)==list(range(1,11))


def test_taskshift_uses_path_encounters_and_reduces_real_bottleneck():
    from mrta_rect_coverage.comparison_algorithms.common import SearchConfig, SearchEnvironment
    from mrta_rect_coverage.comparison_algorithms.sga_ts import taskshift
    from mrta_rect_coverage.core.models import Instance, TaskRegion
    tasks=[TaskRegion(1,10,0,12,50),TaskRegion(2,20,24,22,26),TaskRegion(3,30,24,32,26)]
    instance=Instance('path', (0,0),2,1,1,3,5,tasks)
    env=SearchEnvironment(instance,SearchConfig(max_time=10))
    before=env.evaluate(MultiRobotSolution([[3],[1,2]]),'test')
    after=taskshift(env,before)
    assert after.score < before.score
    assert env.phases['TaskShift_transfer']>0


@pytest.mark.parametrize('module',['cdabc','rnsga','sga_ts','mrhdabc'])
def test_medium_fixed_generation_replay_and_improvement(module):
    from importlib import import_module
    from mrta_rect_coverage.comparison_algorithms.common import SearchConfig, SearchEnvironment
    instance=load_instance(ROOT/'data/R4_T40_0.txt')
    solve=import_module('mrta_rect_coverage.comparison_algorithms.'+module).solve
    config=SearchConfig(max_time=30,max_generations=3,population_size=6,seed=1,scout_limit=1,local_depth=5)
    a,b=solve(instance,config),solve(instance,config)
    assert a.best_solution.routes==b.best_solution.routes
    assert a.best_evaluation.makespan==b.best_evaluation.makespan
    assert a.best_evaluation.makespan<a.initial_makespan
    assert a.iterations==b.iterations==3
    assert SearchEnvironment(instance,SearchConfig(max_time=1)).evaluator.evaluate(a.best_solution).makespan==a.best_evaluation.makespan


def test_genetic_encodings_and_empty_route_moves_are_feasible():
    import random
    from mrta_rect_coverage.comparison_algorithms.common import SearchConfig, SearchEnvironment, ordered_crossover, KINDS
    from mrta_rect_coverage.comparison_algorithms.rnsga import sequence_cross
    from mrta_rect_coverage.comparison_algorithms.sga_ts import half_crossover
    instance=load_instance(ROOT/'data/R2_T10_0.txt');env=SearchEnvironment(instance,SearchConfig(max_time=5))
    a=env.evaluate(MultiRobotSolution([list(range(1,11)),[]]),'test')
    b=env.evaluate(MultiRobotSolution([[],list(range(10,0,-1))]),'test')
    rng=random.Random(4)
    for _ in range(30):
        for mode in range(3):
            x=list(range(10));y=x[:];rng.shuffle(y)
            assert sorted(sequence_cross(x,y,rng,mode))==x
            env.evaluator.evaluate(ordered_crossover(a.solution,b.solution,rng,mode))
        for child in half_crossover(a,b):env.evaluator.evaluate(child)
        for kind in KINDS:env.evaluator.evaluate(env.neighbor(a,kind,critical=True))
