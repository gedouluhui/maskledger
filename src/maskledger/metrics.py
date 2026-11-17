"""Pixel statistics with an explicit digital topology contract."""
import numpy as np
from scipy import ndimage
from .errors import InputError


def _topology(mask):
    components = int(ndimage.label(mask, structure=np.ones((3, 3), bool))[1])
    # Padding gives the exterior one connected component, even at image edges.
    background = np.pad(~mask, 1, constant_values=True)
    background_components = int(ndimage.label(background)[1])  # 4-neighbour cross
    return components, background_components - 1


def compare_masks(reference, candidate):
    """Compare two same-shape bool arrays; do not infer annotation correctness."""
    for name, mask in [('reference', reference), ('candidate', candidate)]:
        if not isinstance(mask, np.ndarray) or mask.dtype != np.bool_ or mask.ndim != 2 or not mask.size:
            raise InputError(f'{name}: expected a nonempty 2D boolean array')
    if reference.shape != candidate.shape:
        raise InputError('mask shapes differ')
    intersection = int(np.count_nonzero(reference & candidate))
    union = int(np.count_nonzero(reference | candidate))
    removed = int(np.count_nonzero(reference & ~candidate))
    added = int(np.count_nonzero(candidate & ~reference))
    rc, rh = _topology(reference)
    cc, ch = _topology(candidate)
    return dict(reference_area=int(reference.sum()), candidate_area=int(candidate.sum()),
                intersection=intersection, union=union, iou=intersection / union if union else None,
                added_pixels=added, removed_pixels=removed, reference_components=rc,
                candidate_components=cc, reference_holes=rh, candidate_holes=ch,
                equal=added == 0 and removed == 0)
