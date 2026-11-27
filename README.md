# MaskLedger

[![CI](https://github.com/gedouluhui/maskledger/actions/workflows/ci.yml/badge.svg)](https://github.com/gedouluhui/maskledger/actions/workflows/ci.yml)

**Find the structure your segmentation conversion lost.**

[Interactive demo](https://gedouluhui.github.io/maskledger/) · [中文](README.zh-CN.md) · [Offline example](docs/index.html) · [MIT license](LICENSE)

A mask can have a high overlap score and still lose a hole, join two separate objects, or erase a thin structure. MaskLedger compares **two COCO instance-segmentation annotation files** and produces inspectable pixel and topology evidence—without a model, image upload, database, or running service.

## Try it

Python 3.11 or newer:

```sh
git clone https://github.com/gedouluhui/maskledger.git
cd maskledger
python -m pip install .
maskledger demo --out demo-output
```

Open `demo-output/index.html`. Select the filled ring, connected islands, one-pixel shift, unchanged rectangle, or lost component. The demo runs the real auditor on self-authored annotations; the results are not prewritten.

The committed `docs/index.html` is an actual generated report. Download and open it locally for an installation-free look. It makes no network requests.

## Audit your conversion

```sh
maskledger compare before.json after.json --out conversion-report
```

The default identity contract is **identical annotation IDs, image IDs and image dimensions**. Reordering annotations is harmless. Missing and extra annotations remain explicit; no nearest-shape matcher silently pairs them away.

If your converter changed annotation IDs, supply a one-to-one mapping:

```json
[
  {"reference_id": 7, "candidate_id": 42},
  {"reference_id": 8, "candidate_id": 43}
]
```

```sh
maskledger compare before.json after.json --id-map mapping.json --out mapped-report
```

When a mapping is supplied, unmapped annotations are missing/extra—even if their IDs happen to agree. Mapping bytes are hashed from the same read used for the audit.

### What you get

- Reference / candidate / difference previews, filterable by instance and status.
- Pixel IoU, intersection, union, area, added and removed pixels.
- Connected components and holes under an explicit digital topology convention.
- Separate missing, extra, category-ID/name and crowd changes.
- `report.json` with input SHA256s, rasterizer version, policy and every finding; the HTML uses the same results.

A difference is **not automatically a bad label or converter bug**. Sometimes the destination format intentionally cannot represent the original structure. Without conversion logs, MaskLedger reports the difference—not an invented cause.

| Exit | Meaning |
|---|---|
| `0` | Complete comparison; all declared instances equivalent |
| `1` | Complete comparison; at least one change/missing/extra instance |
| `2` | Invalid, unsupported, over-budget input, or no reference instances |

`demo` exits zero only after its known changed and unchanged controls are correctly produced. This does not relabel the demo's changed annotations as equivalent.

## Exact scope

**Supported:** COCO polygon lists and compressed/uncompressed COCO RLE; same-space 2D instance masks; integer IDs; one-to-one identity maps. Crowds are not silently skipped. Polygon lists use COCO's union rasterization, not a hole-aware vector format.

**Not supported:** direct YOLO text/LabelMe import, inferred matching, image-content/EXIF checks, automatic label repair, semantic truth, model quality, bounding-box or keypoint auditing. Normalize those formats to the supported representation using your existing conversion pipeline, preserving identity, then audit the before/after artifacts.

Topology uses **8-connected foreground and 4-connected background**. Empty union means undefined IoU (`null`), not a perfect score. Byte identity of JSON is not required; equivalent masks may use different encodings. Polygon coordinates outside the image rectangle are explicitly rejected in this version.

Default resource limits: 32 MiB JSON; 10,000 entries per collection; 16,777,216 pixels per mask; 268,435,456 cumulative mask pixels per input; 100,000 polygon vertices and 500,000 estimated 5× raster-edge steps per annotation. The edge budget bounds an expansion that a vertex count alone does not control. RLE has bounded runs and integer expansion. These are workload guards, **not a security sandbox or a hard process-memory guarantee**.

At most 80 instances receive embedded previews, each reduced to a maximum side of 384 pixels. All numerical findings remain present. Numerical measurements always use full-resolution masks. HTML converts large integer IDs to decimal strings to avoid JavaScript precision loss; archived JSON retains integer IDs.

Input annotations are read-only. Output directories must be new. By default source image files are not opened at all. Reports contain category names and mask previews: review them before sharing your own data.

## Python API

```python
import numpy as np
from maskledger.metrics import compare_masks
from maskledger.audit import audit_coco

reference = np.ones((5, 5), dtype=bool)
reference[2, 2] = False
candidate = np.ones((5, 5), dtype=bool)
print(compare_masks(reference, candidate)["reference_holes"])  # 1
report = audit_coco("before.json", "after.json")
```

## Why another tool?

[Datumaro](https://open-edge-platform.github.io/datumaro/latest/docs/command-reference/compare.html) already compares datasets. [FiftyOne](https://docs.voxel51.com/user_guide/evaluation/detections.html) already offers mask IoU and interactive inspection. MaskLedger does not claim those capabilities are novel. Its narrower workflow is an offline, explicit-identity **conversion-loss evidence package**, including holes/components, coverage accounting and a shareable standalone report. Use the larger tools when you need dataset management, inferred matching or model evaluation.

## Development and verification

```sh
python -m pip install . build
# Run from the repository root; src can also be added to PYTHONPATH while editing.
python -m unittest discover -s tests -v
python scripts/test_mutants.py
python -m build
```

Tests include hand-authored topology cases, compressed RLE checks against pycocotools, real CLI output/exit codes, malicious label text, exact large-ID browser data, malformed JSON and native raster-expansion limits. Tests establish these contracts, not universal correctness or dataset accuracy. Core code received an independent review and a scoped verification of the resulting fixes. Version 0.1.1 makes report publication transactional (staged output committed only after both JSON and HTML succeed) and ships a source archive that rebuilds its wheel and re-runs the installed CLI in a fresh environment; a fresh independent review of these additions is outstanding. Real-world user validation remains open.

Please report a minimal synthetic before/after pair, command, Python/dependency versions and expected result. Do not post confidential annotations. Small adapters and independent regression cases are welcome; avoid broad new format support without a stated pixel/identity contract.

## License and dependencies

Original code and self-authored demo annotations: MIT. NumPy, Pillow, SciPy and pycocotools retain their own licenses (BSD-family / MIT-CMU and bundled third-party notices as applicable). No Ultralytics code, model weights, external datasets, private media or standalone third-party binaries are bundled. AI assistance was used for implementation and review; the executable checks and scope above are the basis for claims.

## Quickstart and support

### Problem
Find pixel and topology structure lost when converting between two COCO instance-segmentation annotation files.

### Install
```sh
python -m pip install .
```

### Success
```sh
maskledger demo --out demo-output
```
Expected: The real auditor reproduces its known changed and unchanged controls; exit 0.

### Deliberate failure
```sh
maskledger compare demo-output/reference.json demo-output/candidate.json --out conversion-report
```
Expected: The changed synthetic annotations produce a changed report and exit 1.

### Evidence and coverage boundaries
Evidence includes hand-authored topology cases, compressed RLE checks against pycocotools, real CLI output and exit codes, malicious label text, exact large-ID browser data, malformed JSON, native raster limits, and mutation checks. A difference is not automatically a bad label or converter bug without conversion logs.

### Support status
Version 0.1.1 supports Python 3.11+ and the documented COCO polygon/RLE subset. Report publication is transactional in this version, but a fresh independent re-review and real-world user validation remain outstanding. Maintenance is best-effort with no SLA.

### Limitations
Direct YOLO/LabelMe import, inferred matching, image-content checks, automatic repair, semantic truth, and model quality are outside scope. Topology is 8-connected foreground with 4-connected background; workload guards are not a security sandbox or hard memory guarantee.
