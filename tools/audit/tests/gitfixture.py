# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Throwaway git repositories for tests (Windows-safe cleanup of read-only git objects)."""
import os
import shutil
import stat
import subprocess
import tempfile


class GitRepo:
    def __init__(self):
        self.path = tempfile.mkdtemp(prefix="thoron-test-")
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        cmd = ["git", "-C", self.path, "-c", "user.name=t", "-c", "user.email=t@e",
               "-c", "core.autocrlf=false", *args]
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()

    def write(self, rel, data: bytes):
        full = os.path.join(self.path, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)

    def remove(self, rel):
        os.remove(os.path.join(self.path, *rel.split("/")))

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def cleanup(self):
        def make_writable(func, path, _exc):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(self.path, onerror=make_writable)
