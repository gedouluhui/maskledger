import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_audit import dataset


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a, self.b = self.root/'a.json', self.root/'b.json'
        for p in (self.a, self.b): p.write_text(json.dumps(dataset()), encoding='utf-8')

    def cli(self, *args):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
        return subprocess.run([sys.executable, '-m', 'maskledger', *map(str,args)], cwd=self.root,
                              env=env, capture_output=True, text=True, timeout=30)

    def test_complete_equivalence_writes_report(self):
        out = self.root/'report'
        run = self.cli('compare', self.a, self.b, '--out', out)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue((out/'report.json').is_file())
        self.assertEqual(json.loads((out/'report.json').read_text())['status'], 'equivalent')
        page = (out/'index.html').read_text(encoding='utf-8')
        self.assertIn('MaskLedger', page)
        self.assertNotIn('src="http', page)

    def test_changed_is_exit_one(self):
        b = dataset(); b['annotations'][0]['segmentation']['counts'] = [15]
        self.b.write_text(json.dumps(b), encoding='utf-8')
        run = self.cli('compare', self.a, self.b, '--out', self.root/'report')
        self.assertEqual(run.returncode, 1, run.stderr)

    def test_invalid_is_exit_two_without_report(self):
        self.b.write_text('{"invalid":true}', encoding='utf-8')
        out = self.root/'report'
        run = self.cli('compare', self.a, self.b, '--out', out)
        self.assertEqual(run.returncode, 2)
        self.assertFalse(out.exists())

    def test_does_not_overwrite_inputs(self):
        before = self.a.read_bytes()
        run = self.cli('compare', self.a, self.b, '--out', self.root)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(self.a.read_bytes(), before)

    def test_hostile_name_not_executable(self):
        a = dataset(); a['categories'][0]['name'] = '</script><img src=x onerror=alert(1)>'
        for p in (self.a,self.b): p.write_text(json.dumps(a), encoding='utf-8')
        out = self.root/'report'
        self.cli('compare',self.a,self.b,'--out',out)
        self.assertTrue((out/'index.html').exists())
        html = (out/'index.html').read_text(encoding='utf-8')
        self.assertNotIn('</script><img',html)
        self.assertIn('textContent',html)

    def test_demo_checks_real_cases(self):
        out = self.root/'demo'
        run = self.cli('demo','--out',out)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertTrue((out/'report.json').exists())
        r=json.loads((out/'report.json').read_text())
        self.assertEqual(r['status'],'changed')
        self.assertGreater(r['summary'].get('equivalent',0),0)
        self.assertGreater(r['summary'].get('changed',0),0)
        self.assertEqual(self.cli('demo','--out',out).returncode,2)


if __name__ == '__main__': unittest.main()
