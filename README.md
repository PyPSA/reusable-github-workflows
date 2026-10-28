# PyPSA reusable workflows

This repo holds reusable GitHub Actions workflows for PyPSA and other Python projects.
A caller repo uses a workflow with a few lines of YAML.
The workflows use composite actions in `.github/actions/`.

| Workflow | Purpose |
| --- | --- |
| [`test.yml`](#testyml) | Test matrix in a pixi env (library mode or project mode). |
| [`release.yml`](#releaseyml) | Tag-to-release chain: prepare, test, build, TestPyPI, GitHub release, PyPI. |
| [`benchmark.yml`](#benchmarkyml) | CodSpeed benchmarks, or a pytest-benchmark comparison of base and head. |
| [`pypsa-eur.yml`](#pypsa-euryml) | Run PyPSA-Eur with the caller package at the current commit. |
| [`link-check.yml`](#link-checkyml) | Check links with lychee. |

## Versioning and pinning

Each release has a tag `v1.x.y`. The `v1` tag moves to the latest `v1.x.y` release on the default branch.
Pre-release tags do not move `v1`.

Pin a workflow in one of two ways:

- Major tag: `uses: PyPSA/reusable-github-workflows/.github/workflows/test.yml@v1`.
- Full commit SHA: `uses: PyPSA/reusable-github-workflows/.github/workflows/test.yml@<sha> # v1.2.3`.
  Use this form if your repo requires SHA pins (for example with zizmor).
  Use this form for `release.yml`. The release run can publish to PyPI, and a SHA cannot move.

The workflows load their composite actions with the self-repository syntax `uses: $/.github/actions/<name>`.
GitHub resolves `$/` to this repo at the same commit as the called workflow.
Thus the actions always match the workflow version that you pin.
Self-hosted runners must use runner version 2.336.0 or newer.

Dependabot updates both forms. Add this to `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule: {interval: monthly}
    groups:
      github-actions: {patterns: ["*"]}
```

## test.yml

Runs the tests in a pixi env on a matrix of OS and Python versions (library mode) or pixi environments (project mode).
Library mode builds a wheel with `hynek/build-and-inspect-python-package` and installs it with uv into a throwaway pixi env.
Project mode starts when you set `pixi-task`. It uses the pixi manifest of the repo.

| Input | Type | Default | Description |
| --- | --- | --- | --- |
| `extras` | string | `dev` | Comma-separated extras to install with the wheel. |
| `pixi-add` | string | | Space-separated conda-forge specs to add to the env, e.g. `glpk coin-or-cbc` or `openjdk>=22`. |
| `uv-locked` | boolean | `false` | Install dependencies from `uv.lock` before the wheel. |
| `cooldown` | string | `7d` | Ignore conda and PyPI releases newer than this age (library mode). Empty disables. `uv-locked` installs ignore it. |
| `matrix` | string | `auto` | `single`, `lean`, `full` or `auto` (`lean` on push and PR, `full` on schedule, dispatch and tags). |
| `python-versions` | string | | JSON list that overrides the Python versions from the trove classifiers. |
| `os-full` | string | `["ubuntu-latest","macos-latest","windows-latest"]` | JSON list of runners for the full matrix. |
| `pytest-args` | string | | Extra pytest arguments. |
| `test-command` | string | | Command that replaces the default pytest command. |
| `pixi-task` | string | | Pixi task to run. Setting it switches to project mode. |
| `pixi-environments` | string | `["default"]` | Project mode: JSON list of pixi environments, or a regex such as `^py3`. |
| `manifest-path` | string | | Project mode: path of the pixi manifest. |
| `pixi-version` | string | `v0.81.0` | Pixi version. |
| `cache-path` | string | | Extra path to cache, e.g. cutouts. |
| `cache-key` | string | | Key of the extra cache. |
| `coverage` | boolean | `false` | Upload coverage to Codecov from the ubuntu leg with the last version. A separate `coverage` job uploads with OIDC. |
| `coverage-file` | string | `coverage.xml` | Coverage report file. |
| `artifact-suffix` | string |  | Suffix of the `Packages` artifact name. Set it if `test.yml` runs more than once in a workflow run. |
| `vars-env` | string | | Space-separated repository or organization variable (`vars`) names to export to the job env. |
| `working-directory` | string | `.` | Directory of the package, relative to the repo root. |

```yaml
name: Test
on:
  push: {branches: [main]}
  pull_request:
  schedule: [{cron: "0 5 * * 1"}]
  workflow_dispatch:
permissions: {}
jobs:
  test:
    uses: PyPSA/reusable-github-workflows/.github/workflows/test.yml@v1
    with:
      pixi-add: glpk coin-or-cbc
      coverage: true
    permissions: {contents: read, id-token: write}
```

The caller job must give `id-token: write`, also without `coverage: true`. Only the `coverage` job uses it. The test jobs run the package code and do not get it.

## release.yml

Runs the release chain for a tag push. The jobs are:

1. `prepare` (only if `prepare-command` is set and `dry-run` is false). If the tag does not point at the prepare commit, the job runs the command, commits the changes with the PyPSA bot and moves the tag to the new commit. The new tag starts a new run. The first run then stops.
2. `test`: calls `test.yml` with the values in `test-inputs`.
3. `build`: builds the sdist and wheel (artifact `Packages-release`). The job fails if the wheel version is not the tag without the leading `v`. Use PEP 440 tags, for example `v1.2.0rc1`.
4. `testpypi` and `smoke` (only if `testpypi: true`): upload to TestPyPI, then install the package from TestPyPI in a fresh env and run `smoke-command`. The install retries for up to 5 minutes.
5. `github-release`: creates the GitHub release. A tag with an `a`, `b` or `rc` suffix makes a pre-release.
6. `publish` (only if `pypi: true`): uploads to PyPI with trusted publishing.

A failure in a job stops all later jobs. `dry-run: true` builds and verifies, but does not upload or release.
The output `ready` is `true` when all checks passed and the run is not a dry run.

| Input | Type | Default | Description |
| --- | --- | --- | --- |
| `prepare-command` | string |  | Bash command that updates files before the release. Pixi is on PATH. Empty skips the prepare stage. |
| `release-branch` | string |  | Branch that gets the prepare commit. Its tip must be the tag commit. Empty means the default branch. |
| `prepare-commit-message` | string |  | Commit message of the prepare commit. Empty means `[github-actions.ci] prepare release <tag>`. |
| `test` | boolean | `true` | Run test.yml before the build. |
| `test-inputs` | string | `{}` | JSON object with test.yml inputs (string values for string inputs, true/false for boolean inputs). |
| `build` | boolean | `true` | Build and verify the sdist and wheel (artifact Packages-release). Set false for repos without a Python package. |
| `pypi` | boolean | `true` | Publish to PyPI. Needs build. |
| `testpypi` | boolean | `false` | Publish to TestPyPI and run a smoke check before the GitHub release and PyPI. |
| `smoke-command` | string |  | Command for the TestPyPI smoke check. Empty means `python -c "import <top-level module>"`. |
| `tag` | string |  | Release tag. Empty means the ref name of the trigger. |
| `release-notes-file` | string |  | File with the release body. Empty means generated release notes. |
| `release-notes-url` | string |  | URL put in a line above the release body. |
| `github-release` | boolean | `true` | Create the GitHub release. |
| `dry-run` | boolean | `false` | Build and verify only. Skip the TestPyPI upload, the GitHub release and PyPI. |
| `working-directory` | string | `.` | Directory of the package, relative to the repo root. |

`test-inputs` takes the `test.yml` inputs as a JSON object. Use JSON strings for string inputs and JSON booleans for boolean inputs.
Use the same values as your test caller, so that you keep the test settings in one place.
An empty string falls back to the `test.yml` default. Thus `"extras": ""` installs the `dev` extra.
The nested `test.yml` uses the artifact suffix `-release-test`.

```yaml
name: Release
on:
  push: {tags: ["v*.*.*"]}
permissions: {}
jobs:
  release:
    uses: PyPSA/reusable-github-workflows/.github/workflows/release.yml@<sha> # v1.x.y
    with:
      prepare-command: pixi run update-data
      testpypi: true
      test-inputs: '{"extras": "dev", "pixi-add": "openjdk>=22"}'
    permissions: {contents: write, id-token: write}
```

The caller job must give `contents: write` and `id-token: write`, also for a dry run.
GitHub checks the permissions of all called jobs before the run starts.

## benchmark.yml

Runs benchmarks in a library-mode pixi env. Set `mode` to one of:

- `codspeed`: runs `pytest <benchmark-path> --codspeed` with `CodSpeedHQ/action`, once per mode in `codspeed-modes`.
  A walltime run on the `codspeed-macro` runner starts on non-PR events, and on PRs with the label `walltime-label`.
  The jobs use OIDC (`id-token: write`) and never block a merge (`continue-on-error`).
  The `benchmarks` extra must contain `pytest-codspeed`.
- `compare`: on a PR, runs pytest-benchmark at the base commit and at the head commit on the same runner.
  The job writes `pytest-benchmark compare` to the step summary and to a sticky PR comment (same-repo PRs only).
  If you set `fail-threshold`, the job fails when a benchmark mean is slower by more than that percent.
  On other events, the job runs the head commit only and writes the summary.
  The `benchmarks` extra must contain `pytest-benchmark`.

| Input | Type | Default | Description |
| --- | --- | --- | --- |
| `mode` | string | `codspeed` | `codspeed` (CodSpeed upload) or `compare` (pytest-benchmark, base vs head). |
| `benchmark-path` | string | `benchmarks` | Benchmark directory, relative to working-directory. |
| `extras` | string | `dev,benchmarks` | Comma-separated extras to install with the wheel. |
| `python-version` | string | `3.13` | Python version of the benchmark env. |
| `pixi-add` | string |  | Space-separated conda-forge specs to add to the env. |
| `cooldown` | string | `7d` | Ignore conda and PyPI releases newer than this age. Empty disables. |
| `pytest-args` | string |  | Extra pytest arguments. |
| `codspeed-modes` | string | `["simulation","memory"]` | JSON list of CodSpeed modes for ubuntu-latest (codspeed mode only). |
| `walltime-label` | string | `trigger:benchmark` | PR label that starts the walltime run on codspeed-macro. Non-PR events always run it (codspeed mode only). |
| `fail-threshold` | string |  | Fail if a benchmark mean regresses by more than this percent. Empty never fails (compare mode only). |
| `vars-env` | string | | Space-separated repository or organization variable (`vars`) names to export to the job env. |
| `working-directory` | string | `.` | Directory of the package, relative to the repo root. |

```yaml
name: Benchmark
on:
  push: {branches: [main]}
  pull_request:
    types: [opened, synchronize, reopened, labeled]
  workflow_dispatch:
permissions: {}
jobs:
  benchmark:
    uses: PyPSA/reusable-github-workflows/.github/workflows/benchmark.yml@v1
    with:
      mode: codspeed
      pixi-add: glpk coin-or-cbc
    permissions: {contents: read, pull-requests: write, id-token: write}
```

The caller job must give all three permissions for both modes.

## pypsa-eur.yml

Runs a PyPSA-Eur pixi task with the caller package at the current commit (PR head SHA or `github.sha`).
The `pypsa-eur-swap` action removes the package from the PyPSA-Eur pixi env and adds it from the git commit.
The PyPSA-Eur `exclude-newer` cooldown stays. The swapped package and the `also-upgrade` packages skip it.
The job caches `data/` weekly and `cutouts/` monthly. It uploads `logs/`, `.snakemake/log/` and `results/` for 3 days.
If `paths` is set and no changed file matches, the job skips the run and reports success.

| Input | Type | Default | Description |
| --- | --- | --- | --- |
| `package` | string |  | Package name in the PyPSA-Eur pixi manifest. Empty means the caller repo name. |
| `pypsa-eur-ref` | string | `master` | Branch, tag or SHA of PyPSA/pypsa-eur. |
| `task` | string | `integration-tests-streamlined` | Pixi task to run in PyPSA-Eur. |
| `also-upgrade` | string |  | Space-separated packages to upgrade after the swap, e.g. linopy. |
| `paths` | string |  | Space- or newline-separated path globs. The run starts only if a change matches. Empty means always run. Schedule and dispatch events always run. |
| `vars-env` | string | | Space-separated repository or organization variable (`vars`) names to export to the job env. |

```yaml
name: PyPSA-Eur
on:
  push: {branches: [master]}
  pull_request:
  schedule: [{cron: "0 5 * * *"}]
  workflow_dispatch:
permissions: {}
jobs:
  pypsa-eur:
    uses: PyPSA/reusable-github-workflows/.github/workflows/pypsa-eur.yml@v1
    with:
      also-upgrade: linopy
      paths: |
        pypsa/**
        pyproject.toml
    permissions: {contents: read, pull-requests: read}
```

## link-check.yml

Checks links with lychee.
If the `config` file does not exist, the workflow uses a default: http and https links only, all status codes except 404 and 410 pass, timeouts pass.

| Input | Type | Default | Description |
| --- | --- | --- | --- |
| `globs` | string | `'./**/*.md' './**/*.py' './**/*.yaml' './**/*.yml' './**/*.toml'` | Space-separated, quoted file globs that lychee checks. |
| `config` | string | `.lychee.toml` | Lychee config file, relative to working-directory. If the file is missing, a built-in default is used. |
| `fail` | boolean | `true` | Fail the job when lychee finds broken links. |
| `working-directory` | string | `.` | Directory that holds the files to check. |

```yaml
name: Link check
on:
  schedule: [{cron: "0 6 * * 1"}]
  workflow_dispatch:
permissions: {}
jobs:
  link-check:
    uses: PyPSA/reusable-github-workflows/.github/workflows/link-check.yml@v1
    permissions: {contents: read}
```

## PyPI trusted publishing

PyPI trusted publishing does not officially support reusable workflows.
PyPI compares the trusted publisher with the workflow file in the caller repo.
The OIDC token names the reusable workflow in this repo.
Thus `publish` and `testpypi` in `release.yml` can fail with an `invalid-publisher` error.

If the upload fails, use the fallback:

1. Set `pypi: false` (and `testpypi: false`) in the `release.yml` call.
2. Add a `publish` job to the caller release file. The job uses the `ready` output and the `Packages-release` artifact.

```yaml
  publish:
    needs: release
    if: needs.release.outputs.ready == 'true'
    runs-on: ubuntu-latest
    environment: pypi
    permissions: {id-token: write}
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with: {name: Packages-release, path: dist}
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # v1.14.2
```

With `pypi: false`, `release.yml` still builds and verifies the artifact. A repo without a Python package sets `build: false` and `pypi: false`.

Do not use a PyPI API token. It is a long-lived secret in each repo.

## Per-repo setup

- **PyPI**: on pypi.org, add a trusted publisher for the caller repo, the caller release workflow file (for example `release.yml`) and the environment `pypi`.
- **TestPyPI**: for `testpypi: true`, add the same trusted publisher on test.pypi.org with the environment `testpypi`.
- **Environments**: create the GitHub environments `pypi` and `testpypi`. Add protection rules if you want a manual approval.
- **PyPSA bot** (only for `prepare-command`): create the GitHub environment `release`. Limit its deployment tags to `v*`. Set the environment secret `PYPSA_BOT_PRIVATE_KEY` and the variable `PYPSA_BOT_ID` (app ID). Only the `prepare` job can then read the key. Install the app on the repo. The app must be able to push to the release branch and to move tags (check branch and tag rulesets).
- **CodSpeed**: install the CodSpeed GitHub app on the repo and enable the repo on codspeed.io.
- **Codecov**: enable the repo on codecov.io. The upload uses OIDC, so the repo needs no `CODECOV_TOKEN`.
- **Secrets**: pass each secret by name. Do not use `secrets: inherit`.
  The workflows accept only these secrets: `CDSAPI_KEY`, `EARTHDATAHUB_API_KEY`, `MOSEKLM_LICENSE_FILE` and `GUROBI_LIC`.
  Each secret becomes an env var with the same name, but only in the steps that run the tests, benchmarks or PyPSA-Eur task.
  The names are the env var names that the code reads. If your repo secret has another name, map it in the call, for example `CDSAPI_KEY: ${{ secrets.CDSAPI_TOKEN }}`.
  A secret that the caller does not pass is an empty env var.
  Other steps and third-party actions do not get the secrets, and a job gets only the secrets that it names.
  To add a secret to the list, open a PR in this repo.
- **Variables**: list repository or organization variables (`vars`) in `vars-env`. The workflows export them to the job env.

  ```yaml
      secrets:
        CDSAPI_KEY: ${{ secrets.CDSAPI_TOKEN }}
      with:
        vars-env: CDSAPI_URL
  ```

## Network monitoring

Each job starts with `step-security/harden-runner` in audit mode. It logs the outbound network connections of the job, with a link to a report in the job summary.
The plan is to switch to block mode: the job can then reach only the listed hosts, so a compromised dependency cannot send secrets away.
Harden-runner sends the network events to StepSecurity. The free tier covers public repos. On macOS and Windows runners it supports only audit mode. The CodSpeed `codspeed-macro` runner skips it.
