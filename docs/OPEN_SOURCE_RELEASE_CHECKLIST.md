# Open Source Release Checklist

Use this checklist before publishing to GitHub.

## 1. Repository Hygiene

- [ ] Confirm repository root is the Git root you want to publish.
- [ ] If `dashboard/.git` exists as a nested repository, remove or de-initialize it before publishing as one repo.
- [ ] Confirm `.gitignore` is active and excludes local cache/build/secrets.

## 2. Secret Safety

- [ ] Ensure `.env` is not committed.
- [ ] Confirm only `.env.example` is tracked.
- [ ] Search code and docs for accidental API keys/tokens.

Quick scan (PowerShell):

```powershell
rg -n "ALPACA|API_KEY|SECRET|TOKEN|PASSWORD" .
```

## 3. Build and Test

- [ ] `pytest -q`
- [ ] `cd dashboard && npm run content:validate`
- [ ] `cd dashboard && npm run content:index`
- [ ] `cd dashboard && npm run build`

## 4. Data and Artifacts

- [ ] Do not commit `data/cache/*.parquet`.
- [ ] Commit only small, intentional sample/static JSON needed for demos.
- [ ] Ensure local DB/log files are ignored.

## 5. Docs and Community Files

- [ ] `README.md` is accurate.
- [ ] `LICENSE` exists.
- [ ] `CONTRIBUTING.md` exists.
- [ ] `CODE_OF_CONDUCT.md` exists.
- [ ] `SECURITY.md` exists.

## 6. First GitHub Push

If starting from this local folder:

```bash
git init
git add .
git commit -m "Initial open-source release"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

