from dataclasses import asdict
from itertools import combinations

import pytest

from mrta_rect_coverage.experiments.dataset_protocol import extract_intrinsic_features, write_generated_instance
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.core.state_generator import generate_all_states


def test_structural_repeats_pairing_geometry_and_nonoverlap(tmp_path):
    from mrta_rect_coverage.experiments.dataset_protocol import generate_structural_instance, STRUCTURAL_SCENARIOS
    for rep in range(3):
        base=generate_structural_instance('BASE',rep)
        for scenario in STRUCTURAL_SCENARIOS:
            generated=generate_structural_instance(scenario,rep)
            assert generated==generate_structural_instance(scenario,rep)
            i=generated.instance
            assert i.robot_count==4 and i.task_count==40 and i.depot==(0,0)
            assert generated.split=='development'
            for t in i.tasks:assert min(t.width,t.height)>0 and min(t.x_left,t.y_bottom)>=0
            for a,b in combinations(i.tasks,2):
                assert a.x_right<=b.x_left or b.x_right<=a.x_left or a.y_top<=b.y_bottom or b.y_top<=a.y_bottom
            if scenario in ('TURN-HIGH','TRAVEL-HIGH','SWEEP-NARROW'):
                assert i.tasks==base.instance.tasks
                params=asdict(i);original=asdict(base.instance)
                changed=[k for k in params if params[k]!=original[k]]
                assert changed==[{'TURN-HIGH':'turning_time','TRAVEL-HIGH':'travel_speed','SWEEP-NARROW':'sweep_width'}[scenario]]
            if scenario=='SPATIAL':
                assert [(t.width,t.height) for t in i.tasks]==[(t.width,t.height) for t in base.instance.tasks]
            if scenario=='HV-GEOM':
                for a,b in zip(i.tasks,base.instance.tasks):
                    assert a.width*a.height==pytest.approx(b.width*b.height)
                    assert (a.x_left+a.x_right,a.y_bottom+a.y_top)==pytest.approx((b.x_left+b.x_right,b.y_bottom+b.y_top))
            path=write_generated_instance(generated,tmp_path/scenario)
            assert load_instance(path)==i
            assert len(path.read_text().strip().splitlines())==6
            assert all(len(s)==8 for s in generate_all_states(i).values())


def test_intrinsic_differences_are_real_without_optimization():
    from mrta_rect_coverage.experiments.dataset_protocol import generate_structural_instance
    for rep in range(3):
        f={s:extract_intrinsic_features(generate_structural_instance(s,rep).instance) for s in
            ('BASE','HV-GEOM','SPATIAL','BOTTLENECK','TURN-HIGH','TRAVEL-HIGH','SWEEP-NARROW')}
        b=f['BASE']
        assert f['HV-GEOM']['relative_hv_gap_mean']>b['relative_hv_gap_mean']+.15
        assert f['TURN-HIGH']['preferred_turning_share_mean']>b['preferred_turning_share_mean']+.05
        assert f['TRAVEL-HIGH']['travel_processing_pressure_ratio']==pytest.approx(2*b['travel_processing_pressure_ratio'])
        assert f['SWEEP-NARROW']['sweeps_h_mean']>b['sweeps_h_mean']
        assert f['SWEEP-NARROW']['mean_p_min']>b['mean_p_min']
        assert f['BOTTLENECK']['workload_cv']>b['workload_cv']+.5
        assert abs(f['BOTTLENECK']['sum_p_min']/b['sum_p_min']-1)<.02
        assert f['SPATIAL']['pairwise_distance_mean']>b['pairwise_distance_mean']*1.2


def test_structural_dataset_manifest_and_refusal_to_overwrite(tmp_path):
    from mrta_rect_coverage.experiments.dataset_protocol import build_structural_dataset
    manifest=build_structural_dataset(tmp_path/'new')
    assert manifest['split']=='development' and len(manifest['entries'])==21
    assert len({e['instance_id'] for e in manifest['entries']})==21
    assert all(e['base_pair_id'] for e in manifest['entries'])
    with pytest.raises(FileExistsError):build_structural_dataset(tmp_path/'new')


def test_structural_validation_uses_real_dp_and_detects_tampering(tmp_path):
    from mrta_rect_coverage.experiments.dataset_protocol import build_structural_dataset, validate_structural_dataset
    root=tmp_path/'data';build_structural_dataset(root)
    result=validate_structural_dataset(root,tmp_path/'results')
    assert result['reproducible_txt_files']==result['loaded_instances']==result['exact_dp_complete_evaluations']==21
    assert result['state_count']==21*40*8
    assert result['b1_smoke_runs']==[]
    path=root/'BASE/R4_T40_0.txt';path.write_text(path.read_text()+'\n')
    with pytest.raises(ValueError,match='hash'):validate_structural_dataset(root,tmp_path/'bad')


def test_legacy_development_artifacts_keep_original_generation_hashes(tmp_path):
    import json
    from pathlib import Path
    from mrta_rect_coverage.experiments.dataset_protocol import SANITY_FAMILY_MATRIX, generate_instance
    root=Path(__file__).resolve().parents[1]
    manifest=json.loads((root/'manifests/r2-sanity-v1_development.json').read_text())
    specs={s.family_id:s for s in SANITY_FAMILY_MATRIX if s.split=='development'}
    for entry in manifest['entries']:
        generated=generate_instance(specs[entry['family_id']],entry['replicate_id'])
        assert generated.generation_config_hash==entry['generation_config_hash']
        path=write_generated_instance(generated,tmp_path/entry['family_id'])
        assert path.read_bytes()==(root/entry['file_path']).read_bytes()
