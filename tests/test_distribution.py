import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'verify_distribution.py'
spec=importlib.util.spec_from_file_location('distribution_verifier',SCRIPT)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.archive=Path(self.tmp.name)/'source.tar.gz'

    def archive_with(self,names,symlink=False):
        with tarfile.open(self.archive,'w:gz') as tar:
            for name in names:
                info=tarfile.TarInfo(name);data=b'public fixture\n'
                if symlink:info.type=tarfile.SYMTYPE;info.linkname='../outside'
                else:info.size=len(data)
                tar.addfile(info,io.BytesIO(data) if not symlink else None)

    def test_valid_source_members(self):
        self.archive_with(['pkg-1.0/tests/fixtures.py','pkg-1.0/scripts/check.py'])
        self.assertEqual(module.validate_sdist(self.archive,'pkg-1.0',{'tests/fixtures.py'}),
                         ['scripts/check.py','tests/fixtures.py'])

    def test_missing_required_helper_is_not_a_pass(self):
        self.archive_with(['pkg-1.0/tests/test_case.py'])
        with self.assertRaises(ValueError):module.validate_sdist(self.archive,'pkg-1.0',{'tests/fixtures.py'})

    def test_traversal_wrong_root_and_private_files_rejected(self):
        for path in ['pkg-1.0/../secret','wrong-root/a.py','pkg-1.0/.venv/secrets',
                     'pkg-1.0/docs/superpowers/internal.md','pkg-1.0/artifacts/local.log']:
            self.archive_with([path])
            with self.subTest(path=path),self.assertRaises(ValueError):module.validate_sdist(self.archive,'pkg-1.0',set())

    def test_links_and_duplicate_members_rejected(self):
        self.archive_with(['pkg-1.0/link'],symlink=True)
        with self.assertRaises(ValueError):module.validate_sdist(self.archive,'pkg-1.0',set())
        self.archive_with(['pkg-1.0/a','pkg-1.0/a'])
        with self.assertRaises(ValueError):module.validate_sdist(self.archive,'pkg-1.0',set())


if __name__=='__main__':unittest.main()
