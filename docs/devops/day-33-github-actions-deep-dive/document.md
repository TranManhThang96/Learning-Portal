# Day 33: GitHub Actions Deep Dive — Document

## 1. GitHub Actions Workflow Syntax Cheat Sheet

### Workflow Structure

```yaml
name: Workflow Name               # Display name
run-name: Deploy ${{ inputs.env }} # Dynamic run name

on:                                # Trigger events
  push:
    branches: [main]
    paths: ['src/**']
    tags: ['v*']
  pull_request:
    branches: [main]
    types: [opened, synchronize]
  schedule:
    - cron: '0 2 * * 1-5'
  workflow_dispatch:
    inputs:
      env:
        type: choice
        options: [dev, staging, prod]
  workflow_call:                   # Reusable workflow
    inputs:
      service:
        type: string
        required: true
    secrets:
      TOKEN:
        required: true
    outputs:
      result:
        value: ${{ jobs.build.outputs.tag }}

permissions:                       # Global permissions
  contents: read
  packages: write
  id-token: write

concurrency:                       # Concurrency control
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:                               # Global env vars
  GO_VERSION: '1.22'

defaults:                          # Default settings
  run:
    shell: bash
    working-directory: ./src

jobs:
  job-name:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    if: github.ref == 'refs/heads/main'
    environment: production
    needs: [previous-job]
    outputs:
      tag: ${{ steps.meta.outputs.tags }}
    strategy:
      fail-fast: false
      matrix:
        version: ['1.21', '1.22']
    services:                      # Service containers
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
    steps:
      - uses: actions/checkout@v6  # Action step
      - name: Run command          # Shell step
        run: echo "hello"
        env:
          MY_VAR: value
        if: success()
        continue-on-error: false
        timeout-minutes: 5
        working-directory: ./app
```

### Context & Expressions

```yaml
# GitHub context
${{ github.sha }}                  # Full commit SHA
${{ github.ref }}                  # refs/heads/main or refs/pull/1/merge
${{ github.ref_name }}             # main or 1/merge
${{ github.event_name }}           # push, pull_request, etc.
${{ github.actor }}                # User who triggered
${{ github.repository }}           # owner/repo
${{ github.repository_owner }}     # owner
${{ github.run_id }}               # Unique run ID
${{ github.run_number }}           # Sequential number
${{ github.workspace }}            # Working directory path

# Job context
${{ job.status }}                  # success, failure, cancelled

# Steps context
${{ steps.step-id.outputs.name }}  # Step output
${{ steps.step-id.outcome }}       # success, failure, cancelled, skipped

# Runner context
${{ runner.os }}                   # Linux, macOS, Windows
${{ runner.arch }}                 # X64, ARM64
${{ runner.temp }}                 # Temp directory

# Matrix context
${{ matrix.version }}              # Current matrix value

# Secrets
${{ secrets.MY_SECRET }}           # Secret value (masked in logs)
${{ secrets.GITHUB_TOKEN }}        # Auto-generated token

# Expressions
${{ contains(github.ref, 'release') }}
${{ startsWith(github.ref, 'refs/tags/') }}
${{ format('Hello {0}', github.actor) }}
${{ toJSON(github.event) }}
${{ fromJSON(steps.result.outputs.matrix) }}
${{ hashFiles('**/go.sum') }}
```

### Conditional Execution

```yaml
# Job conditions
jobs:
  deploy:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

# Step conditions
steps:
  - if: success()                  # Previous steps succeeded (default)
  - if: failure()                  # Any previous step failed
  - if: always()                   # Always run
  - if: cancelled()                # Workflow cancelled
  - if: contains(github.event.pull_request.labels.*.name, 'deploy')
  - if: github.event_name == 'pull_request'
  - if: matrix.os == 'ubuntu-latest'
  - if: steps.cache.outputs.cache-hit != 'true'
```

---

## 2. Common Actions Reference

### Essential Actions

| Action | Purpose | Usage |
|--------|---------|-------|
| `actions/checkout@v6` | Checkout repo | Every workflow |
| `actions/setup-go@v5` | Setup Go | Go projects |
| `actions/setup-node@v4` | Setup Node.js | Node projects |
| `actions/setup-python@v5` | Setup Python | Python projects |
| `actions/cache@v4` | Cache dependencies | Speed up builds |
| `actions/upload-artifact@v4` | Upload artifacts | Share between jobs |
| `actions/download-artifact@v4` | Download artifacts | Get from other jobs |

### Docker Actions

| Action | Purpose |
|--------|---------|
| `docker/setup-buildx-action@v3` | Setup Docker Buildx |
| `docker/build-push-action@v5` | Build & push images |
| `docker/metadata-action@v5` | Generate tags/labels |
| `docker/login-action@v3` | Registry login |

### Security Actions

| Action | Purpose |
|--------|---------|
| `aquasecurity/trivy-action` | Vulnerability scanning |
| `gitleaks/gitleaks-action@v2` | Secret scanning |
| `github/codeql-action/analyze` | SAST scanning |

### Cloud Actions

| Action | Purpose |
|--------|---------|
| `aws-actions/configure-aws-credentials@v4` | AWS OIDC auth |
| `google-github-actions/auth@v2` | GCP OIDC auth |
| `azure/login@v2` | Azure OIDC auth |

---

## 3. Caching Patterns

### Go

```yaml
- uses: actions/setup-go@v5
  with:
    go-version: '1.22'
    cache: true   # Auto-cache ~/go/pkg/mod and ~/.cache/go-build
```

### Node.js

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'  # Auto-cache ~/.npm

# Or manual for node_modules
- uses: actions/cache@v4
  with:
    path: node_modules
    key: ${{ runner.os }}-node-${{ hashFiles('package-lock.json') }}
```

### Python

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
    cache: 'pip'  # Auto-cache ~/.cache/pip
```

### Docker

```yaml
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

---

## 4. Security Hardening Checklist

```
Permissions:
□ permissions: explicitly set (not default write-all)
□ Each job has minimal permissions needed
□ GITHUB_TOKEN scoped to required permissions

Actions:
□ All actions pinned by SHA (not tag)
□ Only trusted actions used (actions/*, verified creators)
□ Dependabot configured for actions updates
□ No actions from unknown publishers without review

Secrets:
□ No hardcoded secrets in workflow files
□ Secrets masked in logs (automatic for ${{ secrets.* }})
□ OIDC used instead of static credentials
□ Secret rotation schedule defined

Runners:
□ GitHub-hosted runners for standard workloads
□ Self-hosted runners in isolated network if needed
□ Ephemeral runners (no persistent state)
□ Runner groups with access control (self-hosted)

Fork PRs:
□ pull_request (not pull_request_target) for fork PRs
□ Require approval before running CI on fork PRs
□ No secrets exposed to fork PR workflows

Script safety:
□ No direct ${{ }} in run: blocks (use env: instead)
□ Shell strict mode in scripts (set -euo pipefail)
□ No eval or dynamic code execution from inputs

Artifacts:
□ Minimal retention days (1-7 days)
□ No secrets in artifacts
□ SBOM generated for container images
□ Image signing configured (cosign)
```

---

## 5. Workflow Debugging Reference

### Enable Debug Logging

```bash
# Set repository secrets:
ACTIONS_RUNNER_DEBUG=true     # Runner diagnostic logs
ACTIONS_STEP_DEBUG=true       # Step debug logs

# Or re-run with debug: UI → "Re-run jobs" → ✅ "Enable debug logging"
```

### CLI Commands (gh)

```bash
# List workflow runs
gh run list --limit 10

# View specific run
gh run view <run-id>

# View run logs
gh run view <run-id> --log

# View failed step
gh run view <run-id> --log-failed

# Re-run failed jobs
gh run rerun <run-id> --failed

# Watch run in real-time
gh run watch <run-id>

# Trigger manual workflow
gh workflow run ci.yaml -f environment=staging

# List workflows
gh workflow list

# View workflow
gh workflow view ci.yaml
```

### Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `Resource not accessible by integration` | Insufficient permissions | Add required `permissions:` |
| `No matching runner found` | Runner label mismatch | Check `runs-on:` label |
| `This request has been automatically failed` | Timeout exceeded | Increase `timeout-minutes` |
| `The workflow is not valid` | YAML syntax error | Validate YAML, check indentation |
| `Repository actions are disabled` | Actions not enabled | Settings → Actions → Enable |
| `pull_request. paths: is not valid` | Wrong path syntax | Use glob patterns: `'src/**'` |

---

## 6. Cost Optimization Tips

```
1. Cancel redundant runs:
   concurrency: { cancel-in-progress: true }
   Savings: 30-50% for active PRs

2. Path filters:
   paths: ['src/**', 'Dockerfile']
   Savings: 40-70% for monorepos

3. Skip CI for docs:
   paths-ignore: ['**.md', 'docs/**']
   Savings: 10-20%

4. Conditional expensive steps:
   if: github.ref == 'refs/heads/main'
   Savings: 20-40% (skip on PRs)

5. Cache everything:
   dependencies, Docker layers, build outputs
   Savings: 50-80% time reduction

6. Smaller runners for simple jobs:
   runs-on: ubuntu-latest (not larger runners)
   Savings: variable (larger runners cost 2-16x more)

7. Minimal artifact retention:
   retention-days: 1 (not default 90)
   Savings: storage costs

8. Combine steps:
   One step with multiple commands > multiple steps
   Savings: step overhead (~2s per step)
```

