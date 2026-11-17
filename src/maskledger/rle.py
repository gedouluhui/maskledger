"""Bounded COCO RLE decoding in Python; malformed counts never enter native code."""
import numpy as np
from .errors import InputError

MAX_RUNS = 2_000_000


def dimensions(height, width, max_pixels):
    if any(type(v) is not int or v <= 0 for v in (height, width, max_pixels)):
        raise InputError('dimensions and max_pixels must be positive integers')
    if height * width > max_pixels:
        raise InputError('mask exceeds max_pixels budget')
    return height * width


def _compressed(text):
    if not text or len(text) > MAX_RUNS * 7:
        raise InputError('RLE counts empty or over encoded-length budget')
    runs = []
    i = 0
    while i < len(text):
        x = 0
        for k in range(7):
            if i >= len(text):
                raise InputError('truncated compressed RLE count')
            c = ord(text[i]) - 48
            i += 1
            if c < 0 or c > 63:
                raise InputError('invalid compressed RLE character')
            x |= (c & 31) << (5 * k)
            if not c & 32:
                if c & 16:
                    x -= 1 << (5 * (k + 1))
                break
        else:
            raise InputError('compressed RLE integer overflow')
        if len(runs) > 2:
            x += runs[-2]
        if x < 0:
            raise InputError('negative reconstructed RLE count')
        runs.append(x)
        if len(runs) > MAX_RUNS:
            raise InputError('RLE exceeds run budget')
    return runs


def decode_rle(segmentation, height, width, *, max_pixels=16_777_216):
    size = dimensions(height, width, max_pixels)
    if not isinstance(segmentation, dict) or set(segmentation) != {'size', 'counts'}:
        raise InputError('RLE must contain exactly size and counts')
    declared = segmentation['size']
    if (not isinstance(declared, list) or len(declared) != 2 or
            any(type(v) is not int for v in declared) or declared != [height, width]):
        raise InputError('RLE size does not match image dimensions')
    counts = segmentation['counts']
    if isinstance(counts, str):
        counts = _compressed(counts)
    if not isinstance(counts, list) or not counts or len(counts) > MAX_RUNS:
        raise InputError('RLE counts must be a nonempty bounded list or compressed string')
    if any(type(n) is not int or n < 0 or n > size for n in counts) or sum(counts) != size:
        raise InputError('RLE counts must be nonnegative integers summing exactly to image area')
    flat = np.zeros(size, dtype=bool)
    pos = 0
    for index, run in enumerate(counts):
        if index % 2:
            flat[pos:pos + run] = True
        pos += run
    return flat.reshape((height, width), order='F')
