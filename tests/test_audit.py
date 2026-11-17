import copy
import json
from pathlib import Path
import tempfile
import unittest
from maskledger.coco import load_coco
from maskledger.audit import audit_coco
from maskledger.errors import InputError


def dataset():
    return {'images': [{'id': 1, 'width': 5, 'height': 3, 'file_name': 'test.png'}],
            'categories': [{'id': 1, 'name': 'shape'}],
            'annotations': [{'id': 7, 'image_id': 1, 'category_id': 1, 'iscrowd': 0,
                             'segmentation': {'size': [3, 5], 'counts': [4, 1, 10]}}]}


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.a = self.root / 'a.json'
        self.b = self.root / 'b.json'
        self.addCleanup(self.tmp.cleanup)

    def write(self, a=None, b=None):
        self.a.write_text(json.dumps(a if a is not None else dataset()), encoding='utf-8')
        self.b.write_text(json.dumps(b if b is not None else dataset()), encoding='utf-8')

    def test_same(self):
        self.write()
        report = audit_coco(self.a, self.b)
        self.assertEqual(report.get('status'), 'equivalent')
        self.assertEqual(report['summary']['equivalent'], 1)
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_reordered(self):
        a = dataset()
        second = copy.deepcopy(a['annotations'][0]); second['id'] = 8
        a['annotations'].append(second)
        b = copy.deepcopy(a); b['annotations'].reverse()
        self.write(a, b)
        self.assertEqual(audit_coco(self.a, self.b).get('status'), 'equivalent')

    def test_missing_and_extra_are_not_automatched(self):
        b = dataset(); b['annotations'][0]['id'] = 8
        self.write(b=b)
        r = audit_coco(self.a, self.b)
        self.assertEqual(r.get('status'), 'changed')
        self.assertEqual(r['summary']['missing'], 1)
        self.assertEqual(r['summary']['extra'], 1)

    def test_explicit_identity_map(self):
        b = dataset(); b['annotations'][0]['id'] = 8
        self.write(b=b)
        mapping = self.root / 'map.json'
        mapping.write_text('[{"reference_id":7,"candidate_id":8}]', encoding='utf-8')
        r = audit_coco(self.a, self.b, id_map=mapping)
        self.assertEqual(r.get('status'), 'equivalent')
        mapping.write_text('[{"reference_id":99,"candidate_id":8}]', encoding='utf-8')
        with self.assertRaises(InputError):
            audit_coco(self.a, self.b, id_map=mapping)

    def test_class_semantics_and_crowd_checked(self):
        for field in ['category', 'crowd']:
            b = dataset()
            if field == 'category': b['categories'][0]['name'] = 'different'
            else: b['annotations'][0]['iscrowd'] = 1
            self.write(b=b)
            self.assertEqual(audit_coco(self.a, self.b).get('status'), 'changed')

    def test_candidate_empty_means_missing(self):
        b = dataset(); b['annotations'] = []
        self.write(b=b)
        self.assertEqual(audit_coco(self.a, self.b).get('status'), 'changed')

    def test_empty_source_is_no_evidence(self):
        a = dataset(); a['annotations'] = []
        self.write(a=a)
        with self.assertRaises(InputError): audit_coco(self.a, self.b)

    def test_known_pixel_difference(self):
        b = dataset(); b['annotations'][0]['segmentation']['counts'] = [5, 1, 9]
        self.write(b=b)
        r = audit_coco(self.a, self.b)
        self.assertEqual(r.get('status'), 'changed')
        self.assertEqual(r['findings'][0]['metrics']['added_pixels'], 1)
        self.assertEqual(r['findings'][0]['metrics']['removed_pixels'], 1)
        self.assertEqual(sum(r['summary'].values()), len(r['findings']))

    def test_coco_polygon_matches_known_bitmap(self):
        a = dataset(); a['images'][0].update(width=4, height=4)
        a['annotations'][0]['segmentation'] = {'size': [4,4], 'counts':[5,2,2,2,5]}
        b = copy.deepcopy(a); b['annotations'][0]['segmentation'] = [[1,1,3,1,3,3,1,3]]
        self.write(a, b)
        self.assertEqual(audit_coco(self.a, self.b).get('status'), 'equivalent')

    def test_invalid_inputs_fail_closed(self):
        cases = []
        a = dataset(); a['annotations'].append(copy.deepcopy(a['annotations'][0])); cases.append(a)
        a = dataset(); a['images'][0]['id'] = True; cases.append(a)
        a = dataset(); a['annotations'][0]['image_id'] = 999; cases.append(a)
        a = dataset(); a['annotations'][0]['category_id'] = 999; cases.append(a)
        a = dataset(); a['annotations'][0]['iscrowd'] = 2; cases.append(a)
        a = dataset(); a['images'][0]['width'] = 100000000; cases.append(a)
        a = dataset(); a['annotations'][0]['segmentation'] = [[0,0,100,0,1,2]]; cases.append(a)
        for a in cases:
            self.write(a=a)
            with self.subTest(a=a), self.assertRaises(InputError): load_coco(self.a)
        self.a.write_text('{"images":[],"images":[]}', encoding='utf-8')
        with self.assertRaises(InputError): load_coco(self.a)

    def test_incompatible_dimensions(self):
        a = dataset(); b = dataset()
        b['images'][0].update(width=3, height=5)
        b['annotations'][0]['segmentation']['size'] = [5,3]
        self.write(a,b)
        with self.assertRaises(InputError): audit_coco(self.a,self.b)


if __name__ == '__main__': unittest.main()
