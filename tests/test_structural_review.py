from copy import deepcopy
from pathlib import Path
import random

from mrta_rect_coverage.heuristics.structural_search import (
    StructuralExecutor, StructuralKernel, reference_step, PairPortfolioSolver,
)
from mrta_rect_coverage.experiments.structural_population import ROOT, read
from mrta_rect_coverage.experiments.structural_review import pair_set
from mrta_rect_coverage.core.instance_loader import load_instance
from mrta_rect_coverage.heuristics.alns_solver import ALNSConfig

OUT=ROOT/'outputs/structural_population/run_001'

def test_review_single_pair_is_not_split_into_operator_name_characters():
    pair=['r1_c3:destroy','r1_c3:repair']
    assert pair_set(pair)==[pair]
    assert pair_set([pair])==[pair]

def test_suspect_duplicate_is_source_distinct_but_locally_identical():
    a=read(OUT/'archive.json')
    x,y=a['r2_c3'],a['r3_c3']
    assert x['hash']!=y['hash']
    assert x['fingerprint']==y['fingerprint']
    assert y['duplicate_of']=='r2_c3'
    assert Path(ROOT/x['source']).read_bytes()!=Path(ROOT/y['source']).read_bytes()

def test_reference_and_executor_have_identical_decisions_on_frozen_features():
    entry=next(e for e in read(OUT/'entries.json')['development'] if e['instance_id']=='development/BASE/R2_T20_0')
    p=ROOT/'sources'/'reference.py'
    reference_path=OUT/'sources'/'reference.py'
    source=Path(reference_path).read_text(encoding='utf-8')
    import hashlib
    digest=hashlib.sha256(Path(reference_path).read_bytes()).hexdigest()
    s=PairPortfolioSolver(load_instance(ROOT/'data/structural_benchmark_v1'/entry['path']),
        config=ALNSConfig.enhanced(iterations=1,random_seed=23))
    k=StructuralKernel(s,reference_step)
    ev=s.solution_evaluator.evaluate(s.initial_solution)
    f=k.destroy_features(s.initial_solution,ev,4)
    rng=random.Random(701)
    direct=reference_step(deepcopy(f),random.Random(701))
    del p
    with StructuralExecutor(reference_path,expected_hash=digest) as executor:
        isolated=executor(deepcopy(f),random.Random(701))
    assert direct==isolated
