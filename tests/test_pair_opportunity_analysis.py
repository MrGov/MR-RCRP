"""Narrow reporting checks: ranking freedom and nonidentical tail completions."""
from mrta_rect_coverage.experiments.bounded_pair_opportunity import (
    choice_counts, diagnostic_evidence,
)


def test_choice_counts_do_not_confuse_ranking_freedom_with_search_usefulness():
    def record(available, selected):
        return {'features': {'pairs': list(range(available))} if available else None,
                'selected_pairs': list(range(selected))}

    counts = choice_counts([record(1, 1), record(2, 2), record(6, 2),
                            record(6, 1), record(6, 0), record(0, 0)], 2)
    assert counts == {
        'calls': 6, 'only_one_pair': 1, 'zero_candidates': 1,
        'all_pairs_searched_more_than_one': 1, 'zero_pairs_expanded': 2,
        'budget_limited_prefix': 2, 'choice_opportunity': 2,
    }


def test_diagnostic_distinguishes_route_diversity_and_unchanged_bottleneck():
    partial = [[], [1]]
    completions = [
        {'branch': {'routes': [[2, 3], [1]], 'makespan': 10.},
         'routes': [[2, 4, 3], [1]], 'makespan': 10.},
        {'branch': {'routes': [[3, 2], [1]], 'makespan': 10.},
         'routes': [[3, 4, 2], [1]], 'makespan': 11.},
    ]
    value = {'post_ls': 9., 'kernel': {'completions': completions}}
    reference = {'repair': 10., 'post_ls': 9., 'kernel': {
        'features': {'routes': partial, 'route_costs': [0., 10.]},
        'greedy_makespan': 10.,
    }}
    row = {'per_pair': {'2:3': value}, 'deployed_policies': {'reference': reference},
           'case': {'source_ref': 'record#/case/0', 'instance_id': 'development/example', 'band': 'early'},
           'best_forced_pair': '2:3', 'post_ls_range': [9., 9.], 'actionable': False,
           'distinct_completed_routes': 1, 'distinct_post_ls_routes': 1}
    result = diagnostic_evidence(row)
    assert result['distinct_retained_partials'] == result['distinct_tail_completed_routes'] == 2
    assert result['retained_leaves_preserving_bottleneck_route'] == 2
    assert result['tail_completions_preserving_bottleneck_route'] == 2
    assert result['retained_partial_makespans'] == [10.]
    assert result['tail_makespan_range'] == [10., 11.]
    assert result['best_forced_post_ls'] == result['reference_post_ls'] == 9.
