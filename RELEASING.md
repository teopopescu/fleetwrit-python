# Releasing to PyPI

## Overview

Two packages ship to PyPI:

- **`fleetwrit`** — the SDK, from this repo
  ([`fleetwrit-python`](https://github.com/teopopescu/fleetwrit-python)).
- **`fleetwrit-server`** — the local server, from the
  [`fleetwrit`](https://github.com/teopopescu/fleetwrit) repo, built from
  `./server`.

Both publish via GitHub Actions using PyPI **Trusted Publishing** (OIDC): the
workflow authenticates to PyPI directly, so there is no long-lived API token
stored anywhere.

## One-time setup

1. Create a PyPI account and turn on 2FA.
2. Add a **Trusted Publisher** on PyPI for each project:
   - `fleetwrit`: owner `teopopescu`, repo `fleetwrit-python`, workflow
     `publish.yml`, environment `pypi`.
   - `fleetwrit-server`: owner `teopopescu`, repo `fleetwrit`, workflow
     `publish-server.yml`, environment `pypi`.
3. Create a GitHub Environment named `pypi` in each repo.

## Release (in order)

Release the SDK first so the server's `fleetwrit` dependency resolves.

1. In `fleetwrit-python`, publish a GitHub Release tagged `v0.0.1` — this fires
   `publish.yml`.
2. Verify: `pip install fleetwrit`.
3. In `fleetwrit`, publish a GitHub Release tagged `v0.0.1` — this fires
   `publish-server.yml`.
4. Verify: `pip install "fleetwrit[dev-server]" && fleetwrit dev`.

## Dry run (optional)

Build and check locally before tagging:

```bash
python -m build            # SDK
python -m build server     # server
twine check dist/*
```

Optionally upload to TestPyPI first to rehearse the publish.

## Note

API tokens are only needed for later paid/Cloud/Enterprise distribution.
Open-source releases use Trusted Publishing and need no stored token.
