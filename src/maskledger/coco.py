"""Read a deliberately bounded subset of COCO, without opening image files."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from pycocotools import mask as coco_mask
from .errors import InputError
from .rle import decode_rle, dimensions

MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_INSTANCES = 10_000
MAX_TOTAL_PIXELS = 268_435_456
MAX_VERTICES = 100_000


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise InputError('nonfinite JSON number')
    return value


def read_json(path):
    path = Path(path)
    try:
        with path.open('rb') as handle:
            raw = handle.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise InputError('JSON exceeds 32 MiB budget')
        data = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_unique, parse_float=_finite_float,
                          parse_constant=lambda _: (_ for _ in ()).throw(InputError('nonfinite JSON number')))
    except InputError:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise InputError(f'{path.name}: unreadable or malformed JSON') from exc
    return data, hashlib.sha256(raw).hexdigest()


def _id(value, label):
    if type(value) is not int or value < 0:
        raise InputError(f'{label}: expected a nonnegative integer ID')
    return value


def _index(rows, label, limit=MAX_INSTANCES):
    if not isinstance(rows, list) or len(rows) > limit:
        raise InputError(f'{label}: expected list within {limit} item budget')
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise InputError(f'{label}: entry must be an object')
        key = _id(row.get('id'), label)
        if key in result:
            raise InputError(f'{label}: duplicate ID {key}')
        result[key] = row
    return result


def annotation_mask(ann, image, *, max_pixels=16_777_216):
    h, w = image['height'], image['width']
    dimensions(h, w, max_pixels)
    seg = ann.get('segmentation')
    if isinstance(seg, dict):
        return decode_rle(seg, h, w, max_pixels=max_pixels)
    if not isinstance(seg, list) or not seg:
        raise InputError(f'annotation {ann["id"]}: missing/unsupported segmentation')
    count = 0
    raster_steps = 0
    for polygon in seg:
        if not isinstance(polygon, list) or len(polygon) < 6 or len(polygon) % 2:
            raise InputError('polygon: expected an even coordinate list with at least three vertices')
        count += len(polygon) // 2
        if count > MAX_VERTICES:
            raise InputError('polygon vertex budget exceeded')
        for i, value in enumerate(polygon):
            if type(value) not in (int, float):
                raise InputError('polygon coordinates must be finite numbers')
            try:
                valid = math.isfinite(value) and 0 <= value <= (w if i % 2 == 0 else h)
            except OverflowError:
                valid = False
            if not valid:
                raise InputError('polygon outside supported image rectangle or nonfinite')
        # COCO's native rasterizer samples each edge at 5x resolution. A vertex
        # cap alone does not bound this expansion (e.g. many long skinny edges).
        points = list(zip(polygon[::2], polygon[1::2]))
        for a, b in zip(points, points[1:] + points[:1]):
            raster_steps += math.ceil(5 * max(abs(a[0]-b[0]), abs(a[1]-b[1]))) + 2
            if raster_steps > 500_000:
                raise InputError('polygon exceeds 500000 estimated raster-edge steps')
    encoded = coco_mask.merge(coco_mask.frPyObjects(seg, h, w))
    safe = {'size': encoded['size'], 'counts': encoded['counts'].decode('ascii')}
    return decode_rle(safe, h, w, max_pixels=max_pixels)


def load_coco(path, *, max_pixels=16_777_216):
    data, digest = read_json(path)
    if not isinstance(data, dict):
        raise InputError('COCO root must be an object')
    images = _index(data.get('images'), 'images')
    categories = _index(data.get('categories'), 'categories')
    annotations = _index(data.get('annotations'), 'annotations')
    for image in images.values():
        dimensions(image.get('height'), image.get('width'), max_pixels)
    for category in categories.values():
        if not isinstance(category.get('name'), str) or len(category['name']) > 1024:
            raise InputError('category name must be a string up to 1024 characters')
    total = 0
    for ann in annotations.values():
        image_id = _id(ann.get('image_id'), 'image_id')
        category_id = _id(ann.get('category_id'), 'category_id')
        if image_id not in images or category_id not in categories:
            raise InputError(f'annotation {ann["id"]}: unknown image/category reference')
        if type(ann.get('iscrowd', 0)) is not int or ann.get('iscrowd', 0) not in (0, 1):
            raise InputError('iscrowd must be integer 0 or 1')
        image = images[image_id]
        total += image['height'] * image['width']
        if total > MAX_TOTAL_PIXELS:
            raise InputError('cumulative mask pixel budget exceeded')
        # Validate every segmentation, including unmatched instances; discard buffer.
        annotation_mask(ann, image, max_pixels=max_pixels)
    return dict(images=images, categories=categories, annotations=annotations,
                input=dict(name=Path(path).name, sha256=digest), pixels=total)
