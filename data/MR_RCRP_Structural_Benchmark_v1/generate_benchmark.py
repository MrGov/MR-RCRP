"""Generate deterministic, structure-paired MR-RCRP six-line TXT instances.

Standalone development artifact aligned with the repository's current six-line
instance_loader.py contract and E10 paired structural-design principles.
No optimization outcome or LLM result is used by this generator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from statistics import mean, pstdev
from itertools import combinations

VERSION = "mr-rcrp-structural-crossscale-v1"
SIZES = [(2,10), (2,20), (4,40), (4,60), (8,80), (8,100)]
SCENARIOS = ("BASE", "HV-GEOM", "SPATIAL", "BOTTLENECK", "TURN-HIGH", "TRAVEL-HIGH", "SWEEP-NARROW")
SPLITS = {"development": 2, "validation": 2, "test": 4}
PARAMS = {"sweep_width": 3.0, "sweep_speed": 1.0, "travel_speed": 1.0, "turning_time": 5.0}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def seed_of(split: str, n_robots: int, n_tasks: int, replicate: int) -> int:
    key = f"{VERSION}\0{split}\0{n_robots}\0{n_tasks}\0{replicate}"
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")


def overlaps(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def ptime(w, h, params, mode):
    sw, vs, tau = params["sweep_width"],params["sweep_speed"],params["turning_time"]
    sweeps = max(1, math.ceil((h if mode=="H" else w)/sw))
    return sweeps * (w if mode=="H" else h) / vs + (sweeps-1)*tau


def pmin(w, h, params=PARAMS):
    return min(ptime(w,h,params,"H"), ptime(w,h,params,"V"))


def make_family(split, robots, tasks, rep):
    rng = random.Random(seed_of(split,robots,tasks,rep))
    sides = [rng.choice((12.0,15.0,18.0)) for _ in range(tasks)]
    dimensions = {scenario: [(x,x) for x in sides] for scenario in SCENARIOS}
    dimensions["HV-GEOM"] = [(3*s,s/3) if k%2==0 else (s/3,3*s) for k,s in enumerate(sides)]
    heavy = set(rng.sample(range(tasks), max(1, round(.10*tasks))))
    raw = [s*(2.4 if k in heavy else .6)*rng.uniform(.97,1.03) for k,s in enumerate(sides)]
    target=sum(pmin(s,s) for s in sides)
    def total(scale): return sum(pmin(x*scale,x*scale) for x in raw)
    lo,hi=.05,5.0
    for _ in range(80):
        mid=(lo+hi)/2
        if total(mid)<target: lo=mid
        else: hi=mid
    factor=min((lo,hi),key=lambda x:abs(total(x)-target))
    dimensions["BOTTLENECK"]=[(x*factor,x*factor) for x in raw]

    # Exclusion envelopes allow all paired structures to share the exact centers.
    envelope=[(max(dimensions[s][k][0] for s in SCENARIOS),
               max(dimensions[s][k][1] for s in SCENARIOS)) for k in range(tasks)]
    extent = 600.0*math.sqrt(tasks/40.0)
    centers,placed=[],[]
    for k,(w,h) in enumerate(envelope):
        for trial in range(10000):
            x=round(rng.uniform(7,extent-7)); y=round(rng.uniform(7,extent-7))
            rect=(x-w/2,y-h/2,x+w/2,y+h/2)
            if min(rect[0],rect[1])<0 or max(rect[2],rect[3])>extent:continue
            if all(not overlaps(rect,z) for z in placed):
                centers.append((float(x),float(y)));placed.append(rect);break
        else:raise RuntimeError(f"unable to place task {k+1} for R{robots}_T{tasks} ({split} {rep})")

    result={}
    for scenario in SCENARIOS:
        sizes=dimensions[scenario]
        rects=[]
        for (x,y),(w,h) in zip(centers,sizes):
            if scenario=="SPATIAL":x*=2.0
            rects.append((x-w/2,y-h/2,x+w/2,y+h/2))
        params=dict(PARAMS)
        if scenario=="TURN-HIGH":params["turning_time"]=10.0
        if scenario=="TRAVEL-HIGH":params["travel_speed"]=0.5
        if scenario=="SWEEP-NARROW":params["sweep_width"]=2.0
        result[scenario]=(rects,params)
    return result


def format_file(robots,tasks,rects,params):
    f=lambda x:format(x,".17g")
    lines=[f"{tasks} {robots}"," ".join(f(params[k]) for k in
           ("sweep_width","sweep_speed","travel_speed","turning_time"))]
    for k in (0,2,1,3):lines.append(" ".join(f(r[k]) for r in rects))
    return ("\n".join(lines)+"\n").encode("utf-8")


def intrinsic(rects,params):
    ws=[r[2]-r[0] for r in rects];hs=[r[3]-r[1] for r in rects]
    ph=[ptime(w,h,params,"H") for w,h in zip(ws,hs)]
    pv=[ptime(w,h,params,"V") for w,h in zip(ws,hs)]
    work=[min(a,b) for a,b in zip(ph,pv)]
    ctr=[((r[0]+r[2])/2,(r[1]+r[3])/2) for r in rects]
    dists=[abs(x-x2)+abs(y-y2) for (x,y),(x2,y2) in combinations(ctr,2)]
    turns=[]
    for w,h,a,b in zip(ws,hs,ph,pv):
        sweeps=math.ceil((h if a<=b else w)/params["sweep_width"])
        turns.append((sweeps-1)*params["turning_time"]/min(a,b))
    return {
        "relative_hv_gap_mean":mean(abs(a-b)/max(a,b) for a,b in zip(ph,pv)),
        "workload_cv":pstdev(work)/mean(work),
        "preferred_turning_share_mean":mean(turns),
        "travel_work_pressure":mean(dists)/params["travel_speed"]/mean(work),
        "processing_work_sum":sum(work),
        "sweep_h_mean":mean(math.ceil(h/params["sweep_width"]) for h in hs),
        "sweep_v_mean":mean(math.ceil(w/params["sweep_width"]) for w in ws),
    }


def validate_txt(path):
    ls=[x.split() for x in Path(path).read_text().strip().splitlines()]
    if len(ls)!=6:raise AssertionError("not six lines")
    tasks,robots=map(int,ls[0]);p=list(map(float,ls[1]));coords=[list(map(float,z)) for z in ls[2:]]
    if len(p)!=4 or any(len(a)!=tasks for a in coords):raise AssertionError("invalid column count")
    if any(not math.isfinite(x) for row in coords for x in row):raise AssertionError("nonfinite")
    rects=[(coords[0][i],coords[2][i],coords[1][i],coords[3][i]) for i in range(tasks)]
    if any(x1<0 or y1<0 or x2<=x1 or y2<=y1 for x1,y1,x2,y2 in rects):raise AssertionError("bad bounds")
    if any(overlaps(a,b) for a,b in combinations(rects,2)):raise AssertionError("overlap")
    if any(x<=0 for x in p[:3]) or p[3]<0:raise AssertionError("bad params")
    return robots,tasks,rects,p


def generate(root):
    root=Path(root)
    if root.exists() and any(root.iterdir()):raise FileExistsError(f"output directory must be empty: {root}")
    root.mkdir(parents=True,exist_ok=True)
    entries=[];rows=[];checks=[]
    for split,nrep in SPLITS.items():
        for robots,tasks in SIZES:
            for rep in range(nrep):
                group=make_family(split,robots,tasks,rep)
                base_rects=group["BASE"][0]
                base_features=intrinsic(*group["BASE"])
                for scenario,(rects,params) in group.items():
                    rel=Path(split)/scenario/f"R{robots}_T{tasks}_{rep}.txt"
                    path=root/rel;path.parent.mkdir(parents=True,exist_ok=True)
                    raw=format_file(robots,tasks,rects,params)
                    path.write_bytes(raw)
                    r0,t0,read_rects,p=validate_txt(path)
                    assert r0==robots and t0==tasks
                    assert all(math.isclose(a,b,abs_tol=1e-10) for r1,r2 in zip(rects,read_rects) for a,b in zip(r1,r2))
                    if scenario in ("TURN-HIGH","TRAVEL-HIGH","SWEEP-NARROW"):assert rects==base_rects
                    feature=intrinsic(rects,params)
                    if scenario=="HV-GEOM":assert feature["relative_hv_gap_mean"]>base_features["relative_hv_gap_mean"]+.15
                    if scenario=="BOTTLENECK":
                        assert feature["workload_cv"]>base_features["workload_cv"]+.35
                        assert abs(feature["processing_work_sum"]/base_features["processing_work_sum"]-1)<.05
                    if scenario=="SPATIAL":assert feature["travel_work_pressure"]>base_features["travel_work_pressure"]*1.2
                    if scenario=="TURN-HIGH":assert feature["preferred_turning_share_mean"]>base_features["preferred_turning_share_mean"]+.05
                    if scenario=="TRAVEL-HIGH":assert math.isclose(feature["travel_work_pressure"],base_features["travel_work_pressure"]*2,rel_tol=1e-12)
                    if scenario=="SWEEP-NARROW":assert feature["sweep_h_mean"]>base_features["sweep_h_mean"]
                    name=f"{split}/{scenario}/R{robots}_T{tasks}_{rep}"
                    entries.append({"instance_id":name,"split":split,"scenario":scenario,
                        "n_robots":robots,"n_tasks":tasks,"replicate":rep,
                        "generation_seed":seed_of(split,robots,tasks,rep),
                        "pair_id":f"{split}/R{robots}_T{tasks}_{rep}",
                        "path":rel.as_posix(),"sha256":sha(raw),"params":params})
                    rows.append({"instance_id":name,"split":split,"scenario":scenario,
                                 "robots":robots,"tasks":tasks,**{k:round(v,6) for k,v in feature.items()}})
    all_ids=[e["instance_id"] for e in entries]
    assert len(set(all_ids))==len(all_ids)
    assert len(entries)==sum(SPLITS.values())*len(SIZES)*len(SCENARIOS)
    manifest={"dataset_version":VERSION,"source_commit":"2c7b14aea4943126e1dcceb0e54d9fd5c1c61274",
       "format":"six-line MR-RCRP TXT, legacy production-loader compatible",
       "units":"model time and coordinate units (not calibrated physical units)",
       "robot_model":"homogeneous within each instance; common depot=(0,0)",
       "splits":SPLITS,"sizes":SIZES,"scenarios":list(SCENARIOS),
       "generation":"deterministic SHA256 seed per split/size/rep; seven variants share same geometry seed",
       "entries":entries}
    (root/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    import csv
    with (root/"intrinsic_features.csv").open("w",encoding="utf-8",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    results={}
    for scenario in SCENARIOS:
        selection=[r for r in rows if r["scenario"]==scenario and r["split"]=="development"]
        results[scenario]={key:round(mean(r[key] for r in selection),3) for key in
                           ("relative_hv_gap_mean","workload_cv","preferred_turning_share_mean","travel_work_pressure")}
    (root/"structure_summary.json").write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest,results


def validate(root):
    root=Path(root);m=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    assert m["dataset_version"]==VERSION
    for e in m["entries"]:
        f=root/e["path"]
        if sha(f.read_bytes())!=e["sha256"]:raise AssertionError(f"checksum mismatch: {f}")
        robots,tasks,_,_=validate_txt(f)
        assert (robots,tasks)==(e["n_robots"],e["n_tasks"])
    return len(m["entries"])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,default=Path("data/structural_benchmark_v1"))
    ap.add_argument("--validate",action="store_true")
    a=ap.parse_args()
    if a.validate:print(f"Verified {validate(a.output)} instance files")
    else:
        manifest,summ=generate(a.output)
        print(f"Generated {len(manifest['entries'])} files in {a.output}")
        print(json.dumps(summ,indent=2))

if __name__=="__main__":main()
