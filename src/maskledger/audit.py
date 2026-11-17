"""One-to-one annotation accounting; identity is declared, not guessed."""
import base64
from collections import Counter
from importlib.metadata import version
import io
import numpy as np
from PIL import Image
from . import __version__
from .coco import load_coco, annotation_mask, read_json
from .errors import InputError
from .metrics import compare_masks

MAX_PREVIEWS = 80


def _png(rgb):
    image = Image.fromarray(rgb)
    image.thumbnail((384, 384), Image.Resampling.NEAREST)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def _previews(a, b):
    shape = a.shape if a is not None else b.shape
    if a is None: a = np.zeros(shape, bool)
    if b is None: b = np.zeros(shape, bool)
    results = {}
    for label, mask, color in [('reference', a, (40,97,205)), ('candidate', b, (22,135,124))]:
        rgb = np.full((*shape, 3), 242, np.uint8)
        rgb[mask] = color
        results[label] = _png(rgb)
    diff = np.full((*shape, 3), 242, np.uint8)
    diff[a & b] = (140,155,177)
    diff[a & ~b] = (40,97,205)
    diff[b & ~a] = (194,95,35)
    results['difference'] = _png(diff)
    return results


def _pairs(a, b, mapping):
    if mapping is None:
        return [(key, key) for key in sorted(a.keys() & b.keys())], None
    rows, digest = read_json(mapping)
    if not isinstance(rows, list) or len(rows) > 10_000:
        raise InputError('ID map must be a bounded list')
    pairs, used_a, used_b = [], set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'reference_id', 'candidate_id'}:
            raise InputError('ID map entries require reference_id and candidate_id')
        x, y = row['reference_id'], row['candidate_id']
        if type(x) is not int or type(y) is not int or x not in a or y not in b:
            raise InputError('ID map refers to an unknown annotation ID')
        if x in used_a or y in used_b:
            raise InputError('ID map must be one-to-one')
        used_a.add(x); used_b.add(y); pairs.append((x, y))
    return pairs, digest


def audit_coco(reference_path, candidate_path, *, id_map=None, max_pixels=16_777_216):
    reference = load_coco(reference_path, max_pixels=max_pixels)
    candidate = load_coco(candidate_path, max_pixels=max_pixels)
    aa, bb = reference['annotations'], candidate['annotations']
    if not aa:
        raise InputError('no evidence: reference contains no instances')
    pairs, mapping_digest = _pairs(aa, bb, id_map)
    used_a, used_b = {x for x, _ in pairs}, {y for _, y in pairs}
    pairs += [(x, None) for x in sorted(aa.keys() - used_a)]
    pairs += [(None, y) for y in sorted(bb.keys() - used_b)]
    findings = []
    for x, y in pairs:
        a, b = aa.get(x), bb.get(y)
        im_a = reference['images'][a['image_id']] if a else None
        im_b = candidate['images'][b['image_id']] if b else None
        if a and b and (a['image_id'] != b['image_id'] or
                        (im_a['height'], im_a['width']) != (im_b['height'], im_b['width'])):
            raise InputError(f'annotation {x}->{y}: incompatible image identity/dimensions')
        ma = annotation_mask(a, im_a, max_pixels=max_pixels) if a else None
        mb = annotation_mask(b, im_b, max_pixels=max_pixels) if b else None
        category_a = reference['categories'][a['category_id']] if a else None
        category_b = candidate['categories'][b['category_id']] if b else None
        metrics = compare_masks(ma, mb) if a and b else None
        reasons = []
        if not a: status = 'extra'
        elif not b: status = 'missing'
        else:
            if (category_a['id'], category_a['name']) != (category_b['id'], category_b['name']):
                reasons.append('category_changed')
            if a.get('iscrowd', 0) != b.get('iscrowd', 0): reasons.append('crowd_changed')
            if not metrics['equal']: reasons.append('pixels_changed')
            status = 'changed' if reasons else 'equivalent'
        finding = dict(reference_id=x, candidate_id=y, image_id=(a or b)['image_id'],
                       category_reference_id=category_a['id'] if a else None,
                       category_candidate_id=category_b['id'] if b else None,
                       category_reference=category_a['name'] if a else None,
                       category_candidate=category_b['name'] if b else None,
                       crowd_reference=a.get('iscrowd', 0) if a else None,
                       crowd_candidate=b.get('iscrowd', 0) if b else None,
                       status=status, reasons=reasons, metrics=metrics,
                       previews=_previews(ma, mb) if len(findings) < MAX_PREVIEWS else None)
        findings.append(finding)
    summary = dict(Counter(f['status'] for f in findings))
    return dict(schema_version=1, tool_version=__version__,
                status='equivalent' if summary.get('equivalent', 0) == len(findings) else 'changed',
                inputs=dict(reference=reference['input'], candidate=candidate['input'],
                            id_map_sha256=mapping_digest),
                policy=dict(foreground_connectivity=8, background_connectivity=4,
                            rasterizer=f'pycocotools {version("pycocotools")}',
                            max_pixels=max_pixels, max_previews=MAX_PREVIEWS,
                            preview_max_side=384, instance_matching='explicit-map' if id_map is not None else 'annotation-id',
                            scope='Instance pixels, category ID/name, crowd and declared identity. Not image content, bbox, keypoints, source truth or conversion cause.'),
                summary=summary, findings=findings)
