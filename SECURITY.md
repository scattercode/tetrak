# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/scattercode/tetrak/security/advisories/new)
(Security tab → "Report a vulnerability"). Do not open a public issue for a
security problem.

We aim to acknowledge reports within seven days. This is a small
collaborative project, not a company with a security team, but we take
reports seriously and will keep you informed as we investigate.

## Supported versions

Only the latest release receives fixes. There are no maintenance branches.

## What we do ourselves

- Trivy scans the dependencies for known vulnerabilities on every push and
  pull request, and Dependabot keeps the workflow actions current.
- The `claude` backend sends page images to the Anthropic API, and is the only
  backend that sends anything off the machine. Its API key is read from the
  environment or a local `.env`, which is gitignored; never commit one.
- Model weights the optional backends download are verified by the packages
  that ship them. The Armenian recogniser checks a pinned SHA-256 before
  loading, because a `.pth` file is a pickle and loading an untrusted one
  executes code.
