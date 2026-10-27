def test_e12_frozen_development_sample_and_budget():
    from mrta_rect_coverage.experiments.e12_comparison import entries, baseline_config, METHODS
    rows=entries()
    assert all(r['split']=='development' for r in rows)
    assert len({r['n_tasks'] for r in rows})>=3
    assert len({r['scenario'] for r in rows})>=3
    assert set(METHODS)=={'B1','CDABC','RNSGA','SGA-TS','MRHDABC','Proposed'}
    for row in rows:
        for method in METHODS[1:-1]:
            cfg=baseline_config(method,row['n_tasks'],1)
            assert cfg.max_time==row['n_tasks'] and cfg.seed==1
