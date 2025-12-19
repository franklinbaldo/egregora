# Auto-Merge Setup for Jules PRs

## Overview

Jules can only create PRs (`AUTO_CREATE_PR` mode). To automatically merge them when CI passes, you need to configure GitHub's auto-merge feature at the repository level.

## Setup Instructions

### 1. Enable Auto-Merge Feature

In your GitHub repository settings:
- Navigate to **Settings** → **General**
- Scroll to **Pull Requests**
- Enable **"Allow auto-merge"**

### 2. Configure Branch Protection Rules

For the `main` branch:
- Navigate to **Settings** → **Branches** → **Branch protection rules**
- Add or edit rule for `main`
- Enable:
  - ✅ **Require status checks to pass before merging**
  - ✅ **Require branches to be up to date before merging**
  - ✅ Specify which CI checks must pass (e.g., tests, linting, build)

### 3. Optional: GitHub Action for Auto-Enable

You can create a GitHub Action that automatically enables auto-merge on Jules PRs:

```yaml
# .github/workflows/jules-auto-merge.yml
name: Enable Auto-Merge for Jules PRs

on:
  pull_request:
    types: [opened]

jobs:
  auto-merge:
    if: github.actor == 'google-labs-jules[bot]'
    runs-on: ubuntu-latest
    steps:
      - name: Enable auto-merge
        run: gh pr merge --auto --squash "${{ github.event.pull_request.number }}"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Current Jules Personas with AUTO_CREATE_PR

- **Curator** (daily at 9 AM): Creates UX evaluation PRs
- **Forge** (hourly): Creates UX implementation PRs
- **Artisan** (Tuesdays at 10 AM): Creates improvement PRs
- **Janitor** (daily at 8 AM): Creates cleanup PRs

All will auto-merge when CI passes (once repository is configured).

## References

- [GitHub Auto-Merge Documentation](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)
- [Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
