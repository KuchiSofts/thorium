# Security Policy

Security is Thoron's first priority. Thank you for helping keep its users safe.

## Supported versions

| Version | Supported |
|---|---|
| No Thoron release yet | — |
| After the first release: the latest release only | ✅ |

Thoron aims to ship within **7 days** of a Chrome release that fixes an actively exploited
vulnerability, and within **14 days** of each new Chrome major version (see [ROADMAP](ROADMAP.md#release-policy)).

## Reporting a vulnerability

**Please report privately.** Never use public issues, pull requests or discussions for security
problems.

1. Use GitHub's private reporting: **[Report a vulnerability](https://github.com/KuchiSofts/thorium/security/advisories/new)**.
2. Include:
   - the affected Thoron version and OS;
   - the steps to reproduce;
   - the impact;
   - and, if you have one, a proof of concept.
3. We **acknowledge within 72 hours** and keep you updated as we investigate.
4. **Coordinated disclosure:** we ask for up to **90 days** to fix the issue before public disclosure,
   or less once a fix has shipped. We credit reporters in the advisory and the changelog, unless you
   prefer to stay anonymous.

### What goes where

| The problem is in… | Report it to |
|---|---|
| Thoron's own code: updater, import, packaging, portable encryption, Thoron patches | Thoron (above) |
| Chromium itself | The Chromium project at https://issues.chromium.org (security template). We will pick up the fix and credit you. |
| Upstream Thorium patches | Thoron (above). We will coordinate with the Thorium project. Thorium's own policy is in its repository: https://github.com/Alex313031/thorium/blob/main/SECURITY.md |
| A bundled extension (uBlock Origin) | Its authors: https://github.com/gorhill/uBlock |

## How releases will be protected

There is no Thoron release yet. **In place today:** the upstream audit and extension verification
(below). **From the first release:** traceable builds and signed checksums. **From updater v1**
(ROADMAP P3): signed updates and profile snapshots.

- **Traceable builds:** every release is built from a tagged commit, with build details in
  `BUILDINFO.json`.
- **Signed checksums and updates:** `SHA256SUMS` and the update manifest are signed (Ed25519). The
  updater verifies the signature **before** reading anything, refuses older (downgrade) or expired
  manifests, and verifies every file's SHA-256.
- **Audited upstream code (in place now):** every upstream Thorium or Chromium change merged into
  Thoron is first audited with [`tools/audit`](tools/audit/README.md). It checks:
  - added binaries (including executables disguised as images);
  - submodule changes;
  - network endpoints;
  - remote-execution and persistence patterns;
  - changes to security features.

  A human reviews every finding.
- **Verified bundled extensions (in place now):** each is pinned by SHA-256 to the author's official
  release. Its CRX3 RSA signature is verified, and its ID is checked against the expected author key
  (`tools/audit/crx_id.py --expect <id>`). Chromium verifies the signature again at install time.
- **No telemetry:** Thoron only contacts its update manifest and package URLs for itself (see
  ROADMAP **S.10**).
- **Your data is never touched by updates:** the updater never writes inside your profile; major
  updates snapshot it first.

## Security history inherited from Thorium

Credit: **Alex313031** and the Thorium project. Major vulnerabilities that Thorium fixed, as listed in
the original Thorium security policy:

- libwebp WebP bug [CVE-2023-4863](https://nvd.nist.gov/vuln/detail/CVE-2023-4863): fixed in M117
- libvpx VP8 bug [CVE-2023-5217](https://nvd.nist.gov/vuln/detail/CVE-2023-5217): fixed in M117
- USB data validation bug [CVE-2023-5482](https://github.com/advisories/GHSA-7cjp-92p9-vr97): fixed in M120
- USB integer overflow bug [CVE-2023-5849](https://github.com/advisories/GHSA-pq78-6h8h-rcf4): fixed in M120
- Use-after-free bug [CVE-2024-4671](https://nvd.nist.gov/vuln/detail/CVE-2024-4671): fixed in M124
