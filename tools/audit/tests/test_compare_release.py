# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
import contextlib
import io
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

    def test_injected_dll_is_never_reported_identical(self):
        zpath = os.path.join(self.tmp, "release.zip")
        with zipfile.ZipFile(zpath, "w") as z:
            z.writestr("Pkg/thorium.exe", b"A")
        inst = os.path.join(self.tmp, "install")
        os.makedirs(inst)
        for name, data in (("thorium.exe", b"A"), ("version.dll", b"evil")):
            with open(os.path.join(inst, name), "wb") as f:
                f.write(data)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            default_rc = compare_release.main([zpath, inst])
        self.assertEqual(default_rc, 0)
        self.assertNotIn("RESULT: identical to release", out.getvalue())
        self.assertIn("WARNING", out.getvalue())
        self.assertIn("version.dll", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(compare_release.main([zpath, inst, "--strict"]), 1)


if __name__ == "__main__":
    unittest.main()
