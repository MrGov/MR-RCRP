import pytest

from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.experiments.e5_destroy_repair import ROOT, read


def test_e6_methods_share_frozen_e5_pools_and_b1_settings():
    from mrta_rect_coverage.experiments.e6_pair_selection import config_for, make_solver

    selected = read(ROOT / "outputs/e5_llm_destroy_repair/selected_operators.json")
    instance = load_instance(ROOT / "data/R2_T10_0.txt")
    v1 = make_solver(instance, 0, selected, "V1", iterations=0)
    v2 = make_solver(instance, 0, selected, "V2", iterations=0)
    assert list(v1.destroy_ops) == list(v2.destroy_ops)
    assert list(v1.repair_ops) == list(v2.repair_ops)
    assert len(v1.destroy_ops) == len(v1.repair_ops) == 4
    assert v1.initial_solution == v2.initial_solution
    assert v1.config.pair_selection_mode == "independent"
    assert v2.config.pair_selection_mode == "coupled"
    assert v2._coupled_selection_probability() == pytest.approx(1 / 16)
    assert config_for(instance, 0, "V2").max_runtime_seconds == 10.0
    assert config_for(instance, 0, "V2").segment_length == 20
    assert config_for(instance, 0, "V2").reaction_factor == .2
