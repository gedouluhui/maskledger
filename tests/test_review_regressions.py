import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from test_audit import dataset
from maskledger.audit import audit_coco
from maskledger.coco import load_coco, read_json, annotation_mask
from maskledger.errors import InputError
from maskledger.report import write_report


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.a=self.root/'a.json';self.b=self.root/'b.json'
        for p in (self.a,self.b):p.write_text(json.dumps(dataset()),encoding='utf-8')

    def test_mapping_hash_is_the_first_used_bytes(self):
        mapping=self.root/'map.json';original=b'[{"reference_id":7,"candidate_id":7}]'
        mapping.write_bytes(original)
        def read_then_change(path):
            data,digest=read_json(path)
            mapping.write_text('[]',encoding='utf-8')
            return data,digest
        with patch('maskledger.audit.read_json',side_effect=read_then_change):
            result=audit_coco(self.a,self.b,id_map=mapping)
        self.assertEqual(result['status'],'equivalent')
        self.assertEqual(result['inputs']['id_map_sha256'],hashlib.sha256(original).hexdigest())

    def test_polygon_expansion_rejected_before_native(self):
        ann={'id':1,'segmentation':[[0,0,32768,1]*32]}
        with patch('maskledger.coco.coco_mask.frPyObjects') as native:
            with self.assertRaises(InputError):
                annotation_mask(ann,{'width':32768,'height':1})
            native.assert_not_called()
        # Opposite control: bounded ordinary polygon remains supported.
        mask=annotation_mask({'id':1,'segmentation':[[0,0,4,0,4,4,0,4]]},{'width':4,'height':4})
        self.assertEqual(int(mask.sum()),16)

    def test_exponent_overflow_and_large_integer_are_input_errors(self):
        for raw in [self.a.read_text()[:-1]+',"score":1e999}', '{"x":'+('1'*5000)+'}']:
            self.a.write_text(raw,encoding='utf-8')
            with self.assertRaises(InputError):load_coco(self.a)

    def test_large_ids_are_exact_in_embedded_browser_data(self):
        a=dataset();a['annotations'][0]['id']=9007199254740993
        for p in (self.a,self.b):p.write_text(json.dumps(a),encoding='utf-8')
        report=audit_coco(self.a,self.b);out=self.root/'out'
        write_report(report,out)
        html=(out/'index.html').read_text(encoding='utf-8')
        embedded=json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>',html,re.S).group(1))
        self.assertEqual(embedded['findings'][0]['reference_id'],'9007199254740993')
        self.assertEqual(json.loads((out/'report.json').read_text())['findings'][0]['reference_id'],9007199254740993)

    def test_category_id_changes_have_full_evidence(self):
        b=dataset();b['categories'][0]['id']=2;b['annotations'][0]['category_id']=2
        self.b.write_text(json.dumps(b),encoding='utf-8')
        r=audit_coco(self.a,self.b)
        self.assertEqual(r['findings'][0].get('category_reference_id'),1)
        self.assertEqual(r['findings'][0].get('category_candidate_id'),2)

    def test_surrogate_names_are_safely_serializable(self):
        a=dataset();a['categories'][0]['name']='\ud800'
        for p in (self.a,self.b):p.write_text(json.dumps(a),encoding='utf-8')
        r=audit_coco(self.a,self.b)
        try:
            write_report(r,self.root/'out')
        except UnicodeError as exc:
            self.fail('serialization must not partially fail: '+str(type(exc)))
        self.assertTrue((self.root/'out'/'index.html').exists())


if __name__=='__main__':unittest.main()
