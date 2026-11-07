# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import os
import shutil
import tempfile
import unittest
import zipfile

from tools.audit import compare_release


class CompareReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="thoron-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_identical_different_missing_extra(self):
        zpath = os.path.join(self.tmp, "release.zip")
        with zipfile.ZipFile(zpath, "w") as z:
            z.writestr("Pkg_1.0/thorium.exe", b"A")
            z.writestr("Pkg_1.0/1.0/x.dll", b"B")
            z.writestr("Pkg_1.0/README.txt", b"readme")
        inst = os.path.join(self.tmp, "install")
        os.makedirs(os.path.join(inst, "1.0"))
        for rel, data in (("thorium.exe", b"A"), ("1.0/x.dll", b"C"), ("evil.dll", b"E")):
            with open(os.path.join(inst, *rel.split("/")), "wb") as f:
                f.write(data)

        result = compare_release.compare(zpath, inst)

        self.assertEqual(result["identical"], ["thorium.exe"])
        self.assertEqual(result["different"], ["1.0/x.dll"])
        self.assertEqual(result["missing"], ["README.txt"])
        self.assertEqual(result["extra"], ["evil.dll"])


if __name__ == "__main__":
    unittest.main()
