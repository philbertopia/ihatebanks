# Dashboard (Next.js)

Frontend for I Hate Banks:

- Strategy Leaderboard
- Backtest Explorer
- Education Hub (Glossary, Lessons, Articles, Strategy Explainers)

## Tech Stack

- Next.js App Router
- TypeScript
- Tailwind CSS
- Recharts
- SWR

## Local Development

```bash
npm install
npm run content:seed
npm run content:validate
npm run content:index
npm run dev
```

Open `http://localhost:3000`.

## Build

```bash
npm run build
```

## Content Publishing

Content lives in:

- `content/glossary/`
- `content/lessons/`
- `content/articles/`
- `content/strategy-explainers/`

Validation and indexing:

```bash
npm run content:validate
npm run content:index
```

Create article scaffold:

```bash
npm run new:article -- --slug your-article-title
```

## Static Data Mode

The frontend supports static JSON mode (no Python backend required) using files under `public/data/`.

To refresh strategy JSON from root project:

```bash
python scripts/export_dashboard_data.py
```

## Deploy (Vercel)

- Build command: `npm run build`
- Framework preset: Next.js
- Optional env:
  - `NEXT_PUBLIC_API_URL=static` (static mode)

