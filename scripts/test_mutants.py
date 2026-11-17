"""Known-bad implementations must fail named behavioral tests; originals stay untouched."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
MUTANTS=[
 ('equal_always','metrics.py',[("equal=added == 0 and removed == 0","equal=True")],'test_core.py'),
 ('erase_holes','metrics.py',[("reference_holes=rh","reference_holes=0")],'test_core.py'),
 ('wrong_rle_order','rle.py',[("order='F'","order='C'")],'test_core.py'),
 ('drop_missing','audit.py',[("pairs += [(x, None) for x in sorted(aa.keys() - used_a)]","pairs += []")],'test_audit.py'),
 ('allow_infinite_json','coco.py',[("parse_float=_finite_float","parse_float=float")],'test_review_regressions.py'),
]


def run(root,pattern):
 env=dict(os.environ,PYTHONPATH=str(root/'src'))
 return subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',pattern,'-v'],
                       cwd=root,env=env,capture_output=True,text=True,timeout=60)


def main():
 originals={p:p.read_bytes() for p in (ROOT/'src').rglob('*.py')}
 for pattern in sorted({m[3] for m in MUTANTS}):
  p=run(ROOT,pattern)
  if p.returncode:
   print('BASELINE_FAILED',pattern,p.stdout,p.stderr);return 1
 caught=[]
 for name,file,replacements,pattern in MUTANTS:
  with tempfile.TemporaryDirectory(prefix='maskledger-mutant-') as tmp:
   root=Path(tmp)
   for folder in ['src','tests']:
    shutil.copytree(ROOT/folder,root/folder,ignore=shutil.ignore_patterns('__pycache__','*.egg-info'))
   target=root/'src'/'maskledger'/file;before=target.read_text(encoding='utf-8');after=before
   for old,new in replacements:
    if after.count(old)!=1:raise RuntimeError('invalid mutation anchor: '+name)
    after=after.replace(old,new,1)
   if after==before:raise RuntimeError('NOP mutation: '+name)
   target.write_text(after,encoding='utf-8',newline='\n')
   p=run(root,pattern);output=p.stdout+p.stderr
   detected=p.returncode!=0 and 'FAIL: test_' in output and 'AssertionError' in output
   print(('CAUGHT' if detected else 'MISSED'),name)
   if not detected:print(output)
   caught.append(detected)
 if any(p.read_bytes()!=data for p,data in originals.items()):raise RuntimeError('original source changed')
 print(f'{sum(caught)}/{len(caught)} named bad implementations caught; original source unchanged')
 return 0 if all(caught) else 1

if __name__=='__main__':raise SystemExit(main())
