from pathlib import Path

from mrta_rect_coverage.experiments import e2_c1_pilot as e2
from mrta_rect_coverage.experiments.e1_real_llm_pilot import build_f1_feedback, build_f2_feedback


def test_elite_retains_parent_and_excludes_partial_failure():
    parent = dict(operator_id='p', source_hash='a', generation=0, success_rate=1., avg_relative_improvement=.1)
    child = dict(operator_id='c', source_hash='b', generation=1, success_rate=1., avg_relative_improvement=.05)
    bad = dict(operator_id='bad', source_hash='x', generation=1, success_rate=.5, avg_relative_improvement=.9)
    assert e2.retain_elites([parent, child, bad]) == [parent, child]


def test_revision_has_real_parent_scalar_and_dp_only_in_f2(tmp_path):
    source = 'def repair(partial_solution, unassigned_tasks, context, rng): pass\n'
    path = tmp_path / 'parent.py'
    path.write_text(source)
    parent = dict(operator_id='p', source_path=str(path), source_hash=e2.source_hash(path),
                  avg_relative_improvement=.1, success_rate=1., trials=[])
    f1 = build_f1_feedback([parent])
    assert f1['weak_candidates'] == []
    scalar = e2.revision_prompt(parent, f1)
    rich = e2.revision_prompt(parent, build_f2_feedback([parent]))
    assert source in scalar and 'Parent evaluated performance' in scalar
    assert 'Behavioral diagnosis' not in scalar
    assert 'Behavioral diagnosis' in rich and 'Do not infer DP effects' in rich


def test_split_is_balanced_nonoverlapping():
    rows = [dict(instance_id=f'{family}{i}', family=family) for family in 'ABC' for i in range(8)]
    assigned = e2.assign_splits(rows)
    assert [sum(r['split'] == s for r in assigned) for s in e2.SPLITS] == [12, 6, 6]
    assert len({r['instance_id'] for r in assigned}) == 24
