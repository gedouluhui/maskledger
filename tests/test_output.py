import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_audit import dataset
from maskledger.audit import audit_coco
from maskledger.errors import InputError
from maskledger.report import write_report
from maskledger.demo import make_demo


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'input.json'
        self.source.write_text(json.dumps(dataset()))

    def test_report_failure_is_not_a_partial_final_report(self):
        r=audit_coco(self.source,self.source);self.assertEqual(r['status'],'equivalent')
        original=Path.write_text
        for filename in ['report.json','index.html']:
            out=self.root/filename.replace('.','-');before={p.name for p in self.root.iterdir()}
            def fail(path,*args,**kwargs):
                if path.name==filename:raise OSError('injected output failure')
                return original(path,*args,**kwargs)
            with patch.object(Path,'write_text',fail),self.assertRaises(OSError):write_report(r,out)
            self.assertFalse(out.exists(),filename)
            self.assertEqual({p.name for p in self.root.iterdir()},before)
        out=self.root/'good';write_report(r,out)
        before=(out/'report.json').read_bytes()
        with self.assertRaises(InputError):write_report(r,out)
        self.assertEqual((out/'report.json').read_bytes(),before)

    def test_transient_publish_denial_is_retried(self):
        r=audit_coco(self.source,self.source);self.assertEqual(r['status'],'equivalent')
        destination=self.root/'published';original=Path.rename;attempts={'n':0}
        def flaky(path,target):
            attempts['n']+=1
            if attempts['n']<=2:raise PermissionError(13,'Access is denied','payload')
            return original(path,target)
        with patch.object(Path,'rename',flaky):write_report(r,destination)
        self.assertGreaterEqual(attempts['n'],3)
        self.assertTrue((destination/'report.json').exists())
        self.assertTrue((destination/'index.html').exists())

    def test_persistent_publish_denial_leaves_no_output_or_lock(self):
        r=audit_coco(self.source,self.source);self.assertEqual(r['status'],'equivalent')
        destination=self.root/'denied'
        with patch.object(Path,'rename',side_effect=PermissionError(13,'Access is denied','payload')):
            with self.assertRaises(PermissionError):write_report(r,destination)
        self.assertFalse(destination.exists())
        self.assertFalse((self.root/'.denied.lock').exists())

    def test_demo_inputs_are_in_same_transaction(self):
        original=Path.write_bytes;out=self.root/'demo'
        def fail(path,data):
            if path.name=='candidate.json':raise OSError('injected final artifact failure')
            return original(path,data)
        with patch.object(Path,'write_bytes',fail),self.assertRaises(OSError):make_demo(out)
        self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
