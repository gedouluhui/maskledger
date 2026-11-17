import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .errors import InputError


def main(argv=None):
    parser=argparse.ArgumentParser(prog='maskledger',description='Evidence of segmentation conversion loss, offline.')
    parser.add_argument('--version',action='version',version=__version__)
    commands=parser.add_subparsers(dest='command',required=True)
    compare=commands.add_parser('compare',help='Compare COCO instance masks by declared identity')
    compare.add_argument('reference',type=Path);compare.add_argument('candidate',type=Path)
    compare.add_argument('--id-map',type=Path)
    compare.add_argument('--max-pixels',type=int,default=16_777_216)
    compare.add_argument('--out',type=Path,required=True)
    demo=commands.add_parser('demo',help='Generate self-authored controls and run a real audit')
    demo.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.out.exists(): raise InputError('output already exists; choose a new directory')
        if args.command=='demo':
            from .demo import make_demo
            report=make_demo(args.out);code=0
        else:
            from .audit import audit_coco
            from .report import write_report
            report=audit_coco(args.reference,args.candidate,id_map=args.id_map,max_pixels=args.max_pixels)
            write_report(report,args.out)
            code=0 if report['status']=='equivalent' else 1
        print(json.dumps({'status':report['status'],'summary':report['summary'],'report':str(args.out/'index.html')},ensure_ascii=True))
        return code
    except (InputError,OSError) as exc:
        print(f'maskledger: {exc}',file=sys.stderr)
        return 2
