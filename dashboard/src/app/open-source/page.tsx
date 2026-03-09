import Link from "next/link";

const GITHUB_URL = "https://github.com/philbertopia/ihatebanks";

const included = [
  {
    icon: "⚙",
    title: "Python Backtesting Engine",
    path: "ovtlyr/backtester/",
    description:
      "Runs historical simulations across 5 years of options data. Walk-forward validation, slippage modeling, Sharpe ratio, drawdown — all computed from raw option chain snapshots.",
  },
  {
    icon: "⌘",
    title: "Strategy Runners & CLI",
    path: "main.py",
    description:
      "Seven terminal commands covering every workflow: daily scans, position tracking, rolling, backtesting, and stats. Dry-run mode on by default — no real orders until you turn it off.",
  },
  {
    icon: "◈",
    title: "This Dashboard",
    path: "dashboard/",
    description:
      "The Next.js app you are looking at. Strategy leaderboard, backtest explorer, and education hub. Deployable to Vercel for free in under five minutes.",
  },
];

const steps = [
  {
    n: "01",
    title: "Clone the repository",
    code: `git clone ${GITHUB_URL}.git\ncd ihatebanks`,
  },
  {
    n: "02",
    title: "Set up a Python virtual environment",
    code: `python -m venv venv\nsource venv/bin/activate   # Windows: venv\\Scripts\\activate\npip install -r requirements.txt`,
  },
  {
    n: "03",
    title: "Configure environment variables",
    code: `cp .env.example .env\n# Open .env and add your Alpaca API keys\n# Only needed for live paper trading — backtests work without any keys`,
  },
  {
    n: "04",
    title: "Run the test suite",
    code: `pytest -q\n# All tests should pass before running anything else`,
  },
  {
    n: "05",
    title: "Run your first backtest",
    code: `python main.py backtest\n# Simulates the strategy on cached historical data`,
  },
  {
    n: "06",
    title: "Start the dashboard",
    code: `cd dashboard\nnpm install\nnpm run dev\n# Open http://localhost:3000`,
  },
];

const commands = [
  { cmd: "python main.py scan", desc: "Full daily workflow — check positions, roll if needed, scan for new trades, open positions, print report" },
  { cmd: "python main.py positions", desc: "Refresh and display all currently open positions" },
  { cmd: "python main.py report", desc: "Print the daily report without placing any trades" },
  { cmd: "python main.py collect", desc: "Cache today's options chain data for future backtests" },
  { cmd: "python main.py generate", desc: "Generate synthetic historical options data using yfinance + Black-Scholes" },
  { cmd: "python main.py backtest", desc: "Run the backtester against cached local data" },
  { cmd: "python main.py stats", desc: "Show aggregate P/L, win rate, and trade history from the local database" },
];

const repoMap = `ihatebanks/
├── main.py              ← Start here. All CLI commands live in this file.
├── server.py            ← FastAPI server (used with live dashboard backend)
├── requirements.txt     ← Python dependencies
├── config/
│   └── settings.yaml   ← Strategy parameters and execution settings
├── ovtlyr/
│   ├── backtester/     ← Backtesting engine, walk-forward, metrics
│   ├── scanner/        ← Daily option chain scanner and filters
│   ├── strategy/       ← Allocation logic and risk controls
│   ├── positions/      ← Position tracking and rolling
│   └── api/            ← Alpaca client and FastAPI routes
├── scripts/
│   └── export_dashboard_data.py  ← Regenerates static JSON for the dashboard
├── dashboard/          ← Next.js frontend (this site)
│   ├── content/        ← Education markdown (lessons, articles, glossary)
│   └── src/app/        ← Pages: /, /strategies, /backtest, /education
└── tests/              ← Python test suite (pytest)`;

export default function OpenSourcePage() {
  return (
    <main className="flex-1 min-h-screen bg-gray-950 text-white">
      <div className="max-w-4xl mx-auto px-6 py-16">

        {/* Hero */}
        <div className="mb-16">
          <div className="inline-flex items-center gap-2 bg-gray-800 border border-gray-700 rounded-full px-3 py-1 text-xs text-gray-400 mb-6">
            <span className="text-green-400">●</span>
            MIT License · Free to use, fork, and modify
          </div>
          <h1 className="text-5xl font-bold text-white mb-4 tracking-tight">
            Open Source
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mb-8 leading-relaxed">
            The full backtesting engine, strategy runners, and this dashboard are open source.
            Clone it, run it on your machine, fork it.
          </p>
          <div className="flex flex-wrap gap-3">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 bg-white text-gray-900 font-semibold px-5 py-2.5 rounded-lg hover:bg-gray-100 transition-colors text-sm"
            >
              View on GitHub →
            </a>
            <Link
              href="/strategies"
              className="inline-flex items-center gap-2 bg-gray-800 border border-gray-700 text-gray-200 font-medium px-5 py-2.5 rounded-lg hover:bg-gray-700 transition-colors text-sm"
            >
              Explore Strategies
            </Link>
          </div>
        </div>

        {/* What's Included */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-white mb-6">What&apos;s included</h2>
          <div className="grid md:grid-cols-3 gap-4">
            {included.map((item) => (
              <div key={item.path} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <div className="text-2xl mb-3 text-pink-400">{item.icon}</div>
                <h3 className="text-white font-semibold mb-1">{item.title}</h3>
                <p className="text-xs text-pink-300/70 font-mono mb-3">{item.path}</p>
                <p className="text-gray-400 text-sm leading-relaxed">{item.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Prerequisites */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-white mb-6">Prerequisites</h2>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex flex-col gap-4">
            {[
              { label: "Python 3.11+", note: "3.12 also works" },
              { label: "Node.js 20+ and npm 10+", note: "For the dashboard only" },
              {
                label: "Alpaca Markets paper account",
                note: "Free. Required only for live paper trading — backtests run without any API keys",
              },
            ].map((req) => (
              <div key={req.label} className="flex items-start gap-3">
                <span className="text-green-400 mt-0.5 shrink-0">✓</span>
                <div>
                  <span className="text-white font-medium text-sm">{req.label}</span>
                  <span className="text-gray-500 text-sm ml-2">— {req.note}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Setup Steps */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-white mb-6">Local setup</h2>
          <div className="flex flex-col gap-6">
            {steps.map((step) => (
              <div key={step.n} className="flex gap-5">
                <div className="shrink-0 w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-pink-600 flex items-center justify-center text-xs font-bold text-white">
                  {step.n}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white font-medium mb-2">{step.title}</p>
                  <pre className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-sm text-gray-300 font-mono overflow-x-auto whitespace-pre">
                    {step.code}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* CLI Commands */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-white mb-2">CLI commands</h2>
          <p className="text-gray-400 text-sm mb-6">All commands run from the repo root. Dry-run mode is on by default — no trades are placed.</p>
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left px-5 py-3 text-gray-500 font-medium">Command</th>
                  <th className="text-left px-5 py-3 text-gray-500 font-medium hidden md:table-cell">What it does</th>
                </tr>
              </thead>
              <tbody>
                {commands.map((row, i) => (
                  <tr
                    key={row.cmd}
                    className={i < commands.length - 1 ? "border-b border-gray-800/60" : ""}
                  >
                    <td className="px-5 py-3 align-top">
                      <code className="text-pink-300 font-mono text-xs whitespace-nowrap">{row.cmd}</code>
                      <p className="text-gray-400 text-xs mt-1 md:hidden">{row.desc}</p>
                    </td>
                    <td className="px-5 py-3 text-gray-400 hidden md:table-cell">{row.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Repo Map */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-white mb-2">Repository map</h2>
          <p className="text-gray-400 text-sm mb-6">Every folder has a single clear responsibility. Start at <code className="text-pink-300 font-mono text-xs">main.py</code>, then trace into the module you care about.</p>
          <pre className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-sm text-gray-300 font-mono overflow-x-auto whitespace-pre leading-relaxed">
            {repoMap}
          </pre>
        </section>

        {/* Dry Run callout */}
        <section className="mb-16">
          <div className="bg-blue-950/40 border border-blue-800/50 rounded-xl p-5 flex gap-4">
            <span className="text-blue-400 text-xl shrink-0">ℹ</span>
            <div>
              <p className="text-blue-200 font-medium text-sm mb-1">Dry run mode is on by default</p>
              <p className="text-blue-300/70 text-sm leading-relaxed">
                <code className="font-mono text-xs bg-blue-900/40 px-1 rounded">dry_run: true</code> is set in{" "}
                <code className="font-mono text-xs bg-blue-900/40 px-1 rounded">config/settings.yaml</code>.
                No real orders are placed until you set it to <code className="font-mono text-xs bg-blue-900/40 px-1 rounded">false</code> and provide live API credentials.
                Backtests always run in simulation mode regardless of this setting.
              </p>
            </div>
          </div>
        </section>

        {/* Disclaimer */}
        <div className="border-t border-gray-800 pt-8 text-gray-600 text-xs leading-relaxed">
          All code and content are for educational and research purposes only. Backtests are hypothetical and do not guarantee future results. Options trading involves substantial risk and is not appropriate for all investors.
        </div>

      </div>
    </main>
  );
}
