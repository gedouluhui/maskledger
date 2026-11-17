"""Deterministic synthetic annotations; reported answers come from the auditor."""
import json
from pathlib import Path
import tempfile
import numpy as np
from .audit import audit_coco
from .errors import InputError
from .report import write_report


def _rle(mask):
    values = mask.ravel(order='F')
    runs, current, length = [], False, 0
    for value in values:
        if bool(value) == current: length += 1
        else:
            runs.append(length); length = 1; current = not current
    runs.append(length)
    return dict(size=list(mask.shape), counts=runs)


def make_demo(output_dir):
    output_dir = Path(output_dir)
    if output_dir.exists(): raise InputError('demo output exists; choose a new directory')
    h, w = 160, 224
    yy, xx = np.mgrid[:h, :w]
    ring = ((xx-112)**2+(yy-80)**2 < 55**2) & ((xx-112)**2+(yy-80)**2 > 27**2)
    disk = (xx-112)**2+(yy-80)**2 < 55**2
    islands = ((xx-62)**2+(yy-80)**2 < 30**2) | ((xx-162)**2+(yy-80)**2 < 30**2)
    bridge = islands.copy(); bridge[76:85,62:163] = True
    line = np.zeros((h,w),bool); line[30:130,111:113] = True
    unchanged = (abs(xx-112)<49) & (abs(yy-80)<41)
    pairs = [(ring,disk,'Hole filled'), (islands,bridge,'Islands connected'),
             (line,np.roll(line,1,axis=1),'One-pixel shift'),
             (unchanged,unchanged.copy(),'Unchanged rectangle'),
             (islands,(xx-62)**2+(yy-80)**2 < 30**2,'Component lost')]
    reference=dict(images=[],categories=[],annotations=[])
    candidate=dict(images=[],categories=[],annotations=[])
    for i,(a,b,name) in enumerate(pairs,1):
        for data,mask in [(reference,a),(candidate,b)]:
            data['images'].append(dict(id=i,width=w,height=h,file_name=f'synthetic-{i}.png'))
            data['categories'].append(dict(id=i,name=name))
            data['annotations'].append(dict(id=i,image_id=i,category_id=i,iscrowd=0,segmentation=_rle(mask)))
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='maskledger-demo-',dir=output_dir.parent) as temp:
        a,b=Path(temp)/'reference.json',Path(temp)/'candidate.json'
        a.write_text(json.dumps(reference),encoding='utf-8');b.write_text(json.dumps(candidate),encoding='utf-8')
        report=audit_coco(a,b)
        if report['summary'].get('equivalent') != 1 or report['summary'].get('changed') != 4:
            raise RuntimeError('demo audit did not detect its known positive and negative controls')
        report['demo']='Self-authored masks. No external data or model quality measurement.'
        write_report(report,output_dir)
        (output_dir/a.name).write_bytes(a.read_bytes());(output_dir/b.name).write_bytes(b.read_bytes())
    return report
