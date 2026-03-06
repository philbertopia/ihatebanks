# I Hate Banks

Open-source options strategy research and education stack:

- Python backtesting engine and strategy runners
- Static-data export pipeline for public dashboard
- Next.js web app for strategy leaderboard, backtest explorer, and education hub

This repository is organized so anyone can clone it, run it locally, and publish it to GitHub + Vercel.

## Mission

I Hate Banks is an open research initiative dedicated to transparent, reproducible, and open-source study of systematic options strategies.

I Hate Banks exists to:

- Promote financial literacy through transparent, open tools
- Make quantitative strategy research accessible beyond institutional walls
- Challenge opaque, gatekept models of financial knowledge
- Publish strategy logic, assumptions, and backtests as open research artifacts

If this project helps you, please share it, fork it, and contribute to it.

See also: `MISSION.md`

## Not Investment Advice

All content and code are for educational and research purposes only.  
Backtests are hypothetical and are not guarantees of future results.  
Options involve substantial risk and may not be suitable for all investors.

## Repository Structure

```text
.
|- config/                      # YAML settings (universes, watchlists, macro calendar)
|- data/                        # Local data outputs and backtest artifacts (mostly ignored in git)
|- db/                          # Local sqlite database files
|- dashboard/                   # Next.js frontend
|  |- content/                  # Markdown education content
|  |- public/data/              # Static JSON served by frontend
|  |- scripts/                  # Frontend content scripts (seed, validate, index)
|  `- src/                      # App Router pages, components, utilities
|- ovtlyr/                      # Python package (engines, API routes, core modules)
|- scripts/                     # Root scripts (ex: export static dashboard data)
|- tests/                       # Python test suite
|- main.py                      # Primary Python CLI entrypoint
`- server.py                    # FastAPI server entrypoint
```

## Prerequisites

- Python 3.11+ (3.12 also works)
- Node.js 20+
- npm 10+

## Quick Start (Python + API)

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy env template and set keys if needed:

```bash
cp .env.example .env
```

4. Run tests:

```bash
pytest -q
```

5. Start API server:

```bash
python server.py
```

## Quick Start (Dashboard)

```bash
cd dashboard
npm install
npm run content:seed
npm run content:validate
npm run content:index
npm run build
npm run dev
```

Open `http://localhost:3000`.

## Common Workflows

### Refresh static strategy data used by frontend

Run from repo root:

```bash
python scripts/export_dashboard_data.py
```

This writes JSON files consumed by the dashboard from `dashboard/public/data`.

### Create a new educational article

```bash
cd dashboard
npm run new:article -- --slug your-article-title
```

Then run:

```bash
npm run content:validate
npm run content:index
```

## Optional Make Targets

If you use `make`, quick aliases are available:

```bash
make test
make export-data
make content-validate
make dashboard-build
make open-source-check
```

## Open Source Publishing Checklist

See:

- `docs/OPEN_SOURCE_RELEASE_CHECKLIST.md`
- `docs/PROJECT_STRUCTURE.md`

Optional local audit:

```bash
python scripts/open_source_check.py
```

## Contributing

See `CONTRIBUTING.md`.

## Security

See `SECURITY.md`.

## License

MIT License. See `LICENSE`.
