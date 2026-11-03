"""Reload a frozen deployment for a development solve, with zero model requests."""
import argparse
from pathlib import Path

from .structural_population import ROOT, Study, read, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--freeze',required=True)
    p.add_argument('--instance',required=True,help='An ID in the frozen development set')
    p.add_argument('--seed',type=int,default=23)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    frozen_path=ROOT/a.freeze
    output=ROOT/a.output
    if output.exists(): raise FileExistsError('Refusing to overwrite an existing solve')
    frozen=read(frozen_path)
    study=Study(frozen_path.parent/'config.json',resume=True)
    entry=next((e for e in study.entries['development'] if e['instance_id']==a.instance),None)
    if entry is None: raise ValueError('Only the frozen development set is available for replay')
    pairs=frozen['selected']['pairs']
    names={n.split(':')[0] for pair in (pairs or []) for n in pair if ':' in n}
    for name in names:
        source=frozen['sources'][name]
        if sha(ROOT/source['source'])!=source['hash'] or study.archive[name]['hash']!=source['hash']:
            raise ValueError('Frozen source mismatch')
    result=study.run_one(entry,a.seed,pairs)
    save(output,{'freeze_hash':sha(frozen_path),'selected':frozen['selected'],'model_requests':0,'result':result})
    print(f"makespan={result.get('makespan')}, valid={result['valid']}, output={output}")
    if not result['valid']: raise RuntimeError(result['error'])


if __name__=='__main__': main()
