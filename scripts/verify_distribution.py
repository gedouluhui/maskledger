"""Build from the sdist, install a fresh wheel, exercise the real installed CLI.

Run from a checkout with build/setuptools/wheel available. Output is local
verification evidence, not a publishable bundle; no existing directory is reused.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tomllib


def validate_sdist(path, expected_root, required_files):
    found=set();total=0
    with tarfile.open(path) as archive:
        members=archive.getmembers()
        if len(members)>10000:raise ValueError('too many source members')
        for member in members:
            parts=PurePosixPath(member.name).parts
            if not parts or parts[0]!=expected_root or '..' in parts or '\\' in member.name:
                raise ValueError('unexpected source archive path')
            if not member.isfile() and not member.isdir():raise ValueError('archive links/devices are forbidden')
            if not member.isfile():continue
            relative='/'.join(parts[1:])
            if not relative or relative in found:raise ValueError('empty or duplicate source member')
            if any(s in relative for s in ['.venv/','.superpowers/','docs/superpowers/','artifacts/','HANDOVER']):
                raise ValueError('private/development-only member in source archive')
            total+=member.size
            if total>64*1024*1024:raise ValueError('source archive extraction budget exceeded')
            found.add(relative)
    missing=set(required_files)-found
    if missing:raise ValueError('missing required public files: '+', '.join(sorted(missing)))
    return sorted(found)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    metadata=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']
    package=metadata['name'];version=metadata['version']
    if package not in ('maskledger','frameledger'):raise ValueError('unexpected project')
    output=args.out.absolute()
    output.mkdir(parents=True,exist_ok=False)
    receipt={'project':package,'version':version,'started_at':datetime.now(timezone.utc).isoformat(),'phases':[]}
    environment=dict(os.environ)
    environment.pop('PYTHONPATH',None);environment['PYTHONIOENCODING']='utf-8'
    def run(label,command,cwd,expected=0,extra_env=None):
        env=dict(environment);env.update(extra_env or {})
        result=subprocess.run(list(map(str,command)),cwd=cwd,env=env,capture_output=True,
                              text=True,encoding='utf-8',errors='replace',timeout=300)
        (output/(label+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        receipt['phases'].append({'name':label,'returncode':result.returncode,'expected':expected})
        if result.returncode!=expected:raise RuntimeError(label+' failed; inspect its log')
        return result.stdout
    try:
        sources=output/'source-dist';sources.mkdir()
        run('build-sdist',[sys.executable,'-m','build','--sdist','--no-isolation','--outdir',sources],root)
        archives=list(sources.glob('*.tar.gz'))
        if len(archives)!=1:raise ValueError('expected exactly one sdist')
        archive=archives[0];prefix=package+'-'+version
        required={'scripts/test_mutants.py','scripts/verify_distribution.py','tests/test_cli.py','docs/index.html'}
        if package=='frameledger':required.update({'tests/fixtures.py','docs/tampered.html'})
        members=validate_sdist(archive,prefix,required)
        extracted=output/'extracted';extracted.mkdir()
        with tarfile.open(archive) as tar:tar.extractall(extracted,filter='data')
        source=extracted/prefix
        wheels=output/'wheels';wheels.mkdir()
        run('wheel-from-sdist',[sys.executable,'-m','build','--wheel','--no-isolation','--outdir',wheels],source)
        packages=list(wheels.glob('*.whl'))
        if len(packages)!=1:raise ValueError('expected exactly one wheel')
        wheel=packages[0];venv=output/'venv'
        run('create-venv',[sys.executable,'-m','venv',venv],output)
        bindir=venv/('Scripts' if os.name=='nt' else 'bin')
        python=bindir/('python.exe' if os.name=='nt' else 'python')
        console=bindir/(package+('.exe' if os.name=='nt' else ''))
        run('install-wheel',[python,'-m','pip','install','--disable-pip-version-check',wheel],output)
        cwd=output/'outside-source';cwd.mkdir()
        imported=run('installed-location',[python,'-I','-c',f'import {package};print({package}.__file__)'],cwd).strip()
        if not Path(imported).is_relative_to(venv):raise RuntimeError('import escaped fresh installed environment')
        run('installed-tests',[python,'-I','-m','unittest','discover','-s','tests','-v'],source,
            extra_env={'LEDGER_TEST_INSTALLED':'1'})
        run('source-mutants',[python,source/'scripts'/'test_mutants.py'],source)
        demo=cwd/'demo'
        run('installed-demo',[python,'-I','-m',package,'demo','--out',demo],cwd)
        if package=='maskledger':
            clean=json.loads(run('console-clean',[console,'compare',demo/'reference.json',demo/'reference.json','--out',cwd/'clean'],cwd))
            changed=json.loads(run('console-changed',[console,'compare',demo/'reference.json',demo/'candidate.json','--out',cwd/'changed'],cwd,expected=1))
            if clean['status']!='equivalent' or changed['status']!='changed':raise RuntimeError('wrong audit statuses')
        else:
            clean=json.loads(run('console-clean',[console,'audit',demo/'synthetic-vfr.mkv',demo/'samples'/'manifest.json','--out',cwd/'clean'],cwd))
            changed=json.loads(run('console-changed',[console,'audit',demo/'synthetic-vfr.mkv',demo/'samples'/'tampered-manifest.json','--out',cwd/'changed'],cwd,expected=1))
            if clean['status']!='pass' or changed['status']!='fail':raise RuntimeError('wrong audit statuses')
        run('console-no-overwrite',[console,'demo','--out',demo],cwd,expected=2)
        run('pip-check',[python,'-m','pip','check'],cwd)
        receipt.update(status='pass',installed_module=imported,source_members=len(members),
                       sdist_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                       wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
                       limitations='Source mutants intentionally exercise source copies; installed CLI tests use -I and no source PYTHONPATH.')
        print(json.dumps({'status':'pass','receipt':str(output/'receipt.json')},ensure_ascii=True))
        return 0
    except Exception as exc:
        receipt.update(status='fail',error=type(exc).__name__+': '+str(exc))
        print(json.dumps({'status':'fail','error':receipt['error']},ensure_ascii=True),file=sys.stderr)
        return 1
    finally:
        receipt['finished_at']=datetime.now(timezone.utc).isoformat()
        (output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=True,indent=2),encoding='utf-8')


if __name__=='__main__':raise SystemExit(main())
