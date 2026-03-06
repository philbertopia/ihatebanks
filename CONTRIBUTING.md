# Contributing

Thanks for contributing.

## Ground Rules

- Keep pull requests focused and small when possible.
- Add or update tests for behavioral changes.
- Keep docs updated for any CLI, API, or UX changes.
- Never commit secrets (`.env`, keys, tokens, private credentials).

## Local Setup

### Python

```bash
pip install -r requirements.txt
pytest -q
```

### Dashboard

```bash
cd dashboard
npm install
npm run content:validate
npm run build
```

## Branch and PR Workflow

1. Fork and create a branch:

```bash
git checkout -b feat/short-description
```

2. Make changes and run checks.
3. Commit with clear message.
4. Open a PR that includes:
   - problem statement
   - what changed
   - test evidence
   - screenshots for UI changes

## Required Checks Before PR

- `pytest -q` (root)
- `npm run content:validate` (dashboard)
- `npm run build` (dashboard)

## Content Contributions (Education Hub)

Markdown lives in:

- `dashboard/content/glossary/`
- `dashboard/content/lessons/`
- `dashboard/content/articles/`
- `dashboard/content/strategy-explainers/`

After adding content:

```bash
cd dashboard
npm run content:validate
npm run content:index
```

## Style Notes

- Prefer explicit, readable code over clever shortcuts.
- Keep comments concise and useful.
- Preserve established naming and folder patterns.

