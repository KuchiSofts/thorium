# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Hosts a fresh profile contacts (ROADMAP S.10)."""
import unittest

from tools.qa import netlog_hosts as nh

LOG = ('{"constants":{},"events":[\n'
       '{"params":{"url":"https://update.googleapis.com/service/update2/json?cup2key=1"},"type":2},\n'
       '{"params":{"host":"clients2.google.com","port":443},"type":3},\n'
       '{"params":{"url":"http://127.0.0.1:5555/page"},"type":2},\n'
       '{"params":{"host":"localhost"},"type":3},\n'
       '{"params":{"url":"chrome://newtab/"},"type":2},\n'
       '{"params":{"url":"https://update.googleapis.com/other"},"type":2},\n'
       '{"params":{"host_port_pair":"accounts.google.com:443"}')   # cut off: the browser was stopped


class HostsTests(unittest.TestCase):
    def test_external_hosts_from_a_truncated_log(self):
        self.assertEqual(nh.hosts(LOG), {"update.googleapis.com": 2, "clients2.google.com": 1,
                                         "accounts.google.com": 1})

    def test_scheme_and_port_forms_are_one_host(self):
        log = ('{"params":{"host":"https://accounts.google.com"}},{"params":{"host":"accounts.google.com:443"}},'
               '{"params":{"host":"http://127.0.0.1:34519"}},{"params":{"host":"optimizationguide-pa.googleapis.com:443"}}')
        self.assertEqual(nh.hosts(log), {"accounts.google.com": 2, "optimizationguide-pa.googleapis.com": 1})

    def test_local_and_internal_are_ignored(self):
        found = nh.hosts(LOG)
        for local in ("127.0.0.1", "localhost", "newtab"):
            self.assertNotIn(local, found)

    def test_markdown(self):
        md = nh.to_markdown({"update.googleapis.com": 2}, "Thoron 158", 120)
        self.assertIn("| update.googleapis.com | 2 |", md)
        self.assertIn("120 s", md)


if __name__ == "__main__":
    unittest.main()
