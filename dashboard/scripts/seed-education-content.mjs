import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";

const root = process.cwd();
const baseDir = path.join(root, "content");

const DIRS = {
  glossary: path.join(baseDir, "glossary"),
  lessons: path.join(baseDir, "lessons"),
  articles: path.join(baseDir, "articles"),
  explainers: path.join(baseDir, "strategy-explainers"),
};

const REF = (topic) => [
  {
    title: "tastylive options education channel",
    url: "https://www.youtube.com/@tastylive",
    source: "youtube",
    why_it_matters: `Practical, trade-focused context for ${topic}.`,
  },
  {
    title: "Investopedia options and derivatives hub",
    url: "https://www.investopedia.com/trading/options-and-derivatives-4689659",
    source: "article",
    why_it_matters:
      "Baseline reference for definitions, payoff structure, and risk language.",
  },
  {
    title: "Cboe Options Institute",
    url: "https://www.cboe.com/optionsinstitute/",
    source: "docs",
    why_it_matters:
      "Exchange-level educational material on options mechanics and risk.",
  },
];

const GLOSSARY = [
  ["option-contract", "Option Contract", "options-basics"], ["call-option", "Call Option", "options-basics"],
  ["put-option", "Put Option", "options-basics"], ["strike-price", "Strike Price", "options-basics"],
  ["expiration-date", "Expiration Date", "options-basics"], ["premium", "Premium", "options-basics"],
  ["intrinsic-value", "Intrinsic Value", "options-basics"], ["extrinsic-value", "Extrinsic Value", "options-basics"],
  ["moneyness", "Moneyness", "options-basics"], ["delta", "Delta", "options-basics"],
  ["gamma", "Gamma", "risk"], ["theta", "Theta", "risk"], ["vega", "Vega", "volatility"], ["rho", "Rho", "options-basics"],
  ["implied-volatility", "Implied Volatility", "volatility"], ["historical-volatility", "Historical Volatility", "volatility"],
  ["iv-rank", "IV Rank", "volatility"], ["iv-percentile", "IV Percentile", "volatility"],
  ["bid-ask-spread", "Bid Ask Spread", "execution"], ["open-interest", "Open Interest", "execution"],
  ["liquidity", "Liquidity", "execution"], ["slippage", "Slippage", "execution"],
  ["assignment", "Assignment", "strategy"], ["early-assignment", "Early Assignment", "risk"],
  ["covered-call", "Covered Call", "strategy"], ["cash-secured-put", "Cash Secured Put", "strategy"],
  ["put-credit-spread", "Put Credit Spread", "strategy"], ["call-credit-spread", "Call Credit Spread", "strategy"],
  ["max-profit", "Max Profit", "risk"], ["max-loss", "Max Loss", "risk"], ["breakeven", "Breakeven", "risk"],
  ["risk-reward-ratio", "Risk Reward Ratio", "risk"], ["position-sizing", "Position Sizing", "risk"],
  ["drawdown", "Drawdown", "risk"], ["sharpe-ratio", "Sharpe Ratio", "risk"], ["profit-factor", "Profit Factor", "risk"],
  ["win-rate", "Win Rate", "risk"], ["walk-forward-testing", "Walk Forward Testing", "strategy"],
  ["out-of-sample", "Out of Sample", "strategy"], ["overfitting", "Overfitting", "strategy"],
];

const LESSON_TOPICS = [
  "Options foundations",
  "Calls and puts payoffs",
  "Moneyness, DTE, intrinsic and extrinsic",
  "Greeks in practice",
  "Volatility and IV rank",
  "Liquidity, spreads, and slippage",
  "Risk management basics",
  "Put credit spreads",
  "Call credit spreads",
  "Wheel strategy mechanics",
  "Intraday options workflow",
  "Backtesting, walk-forward, and overfitting",
];

const ARTICLE_TOPICS = [
  "Reading large returns responsibly",
  "Regime dependence in premium selling",
  "What OOS pass really means",
  "Drawdown psychology and system discipline",
  "Execution realism and slippage drag",
  "Benchmarking options strategies correctly",
  "Common backtest mistakes in options",
  "Alpaca execution and live trading friction",
  "Wheel versus credit spread tradeoffs",
  "Why volatility filters improve survival",
  "Interpreting profit factor in context",
  "From research to production playbook",
];

const EXPLAINERS = [
  ["pcs-legacy-replica", "PCS Legacy Replica Explainer", "openclaw_put_credit_spread|legacy_replica", "intermediate"],
  ["pcs-vix-optimal", "PCS VIX Optimal Explainer", "openclaw_put_credit_spread|pcs_vix_optimal", "intermediate"],
  ["ccs-baseline", "CCS Baseline Explainer", "openclaw_call_credit_spread|ccs_baseline", "intermediate"],
  ["ccs-defensive", "CCS Defensive Explainer", "openclaw_call_credit_spread|ccs_defensive", "intermediate"],
  ["wheel-d30-c30", "Wheel D30 C30 Explainer", "stock_replacement|wheel_d30_c30", "beginner"],
  ["wheel-d20-c30", "Wheel D20 C30 Explainer", "stock_replacement|wheel_d20_c30", "beginner"],
  ["wheel-d40-c30", "Wheel D40 C30 Explainer", "stock_replacement|wheel_d40_c30", "intermediate"],
  ["intraday-baseline", "Intraday Baseline Explainer", "intraday_open_close_options|baseline", "advanced"],
  ["intraday-conservative", "Intraday Conservative Explainer", "intraday_open_close_options|conservative", "advanced"],
  ["stock-replacement-full-filter-20pos", "Stock Replacement Full Filter 20 Position Explainer", "stock_replacement|full_filter_20pos", "intermediate"],
];

function md(...lines) {
  return lines.join("\n") + "\n";
}

async function ensureDirs() {
  await Promise.all(Object.values(DIRS).map((d) => fs.mkdir(d, { recursive: true })));
}

async function writeFile(dir, slug, fm, body) {
  const target = path.join(dir, `${slug}.md`);
  await fs.writeFile(target, matter.stringify(body, fm), "utf8");
}

async function seedGlossary() {
  for (const [slug, term, category] of GLOSSARY) {
    const fm = {
      slug,
      title: term,
      summary: `${term} is a core options concept used in strategy setup, risk control, and performance interpretation.`,
      published_at: "2026-03-06",
      author: "I Hate Banks Editorial Team",
      tags: ["glossary", "options"],
      level: "beginner",
      estimated_minutes: 4,
      references: REF(term),
      disclaimer_required: true,
      term,
      category,
    };
    const body = md(
      "## Definition",
      `${term} describes a concept that appears repeatedly in trade selection and risk management.`,
      "",
      "## Why it matters",
      "Understanding this term helps you interpret strategy rules and avoid misuse of backtest results.",
      "",
      "## Practical use",
      "- Define it in plain language before trading.",
      "- Connect it to one real trade example.",
      "- Verify how it changes risk, not only return."
    );
    await writeFile(DIRS.glossary, slug, fm, body);
  }
}

async function seedLessons() {
  for (let i = 0; i < LESSON_TOPICS.length; i += 1) {
    const n = i + 1;
    const topic = LESSON_TOPICS[i];
    const slug = `lesson-${String(n).padStart(2, "0")}-${topic.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;
    const fm = {
      slug,
      title: topic,
      summary: `Structured lesson ${n} covering ${topic.toLowerCase()} with practical links to strategy behavior.`,
      published_at: "2026-03-06",
      author: "I Hate Banks Editorial Team",
      tags: ["lesson", "education"],
      level: n <= 3 ? "beginner" : n <= 10 ? "intermediate" : "advanced",
      estimated_minutes: n <= 3 ? 18 : n <= 10 ? 22 : 25,
      references: REF(topic),
      disclaimer_required: true,
      lesson_number: n,
      learning_objectives: [`Define core concepts in ${topic.toLowerCase()}.`, "Map concept to strategy design decisions.", "Identify common implementation mistakes."],
      key_takeaways: ["Process beats prediction.", "Risk controls are part of edge.", "Validation is required before deployment."],
    };
    const body = md(
      "## Overview",
      `This lesson explains ${topic.toLowerCase()} and shows where it appears in real strategy workflows.`,
      "",
      "## Lesson walkthrough",
      "1. Concept primer",
      "2. Risk implications",
      "3. Strategy application",
      "",
      "## Apply it",
      "Review one strategy page and identify how this lesson changes your interpretation of its metrics."
    );
    await writeFile(DIRS.lessons, slug, fm, body);
  }
}

async function seedArticles() {
  for (const topic of ARTICLE_TOPICS) {
    const slug = topic.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const fm = {
      slug,
      title: topic,
      summary: `Educational article on ${topic.toLowerCase()} for readers evaluating options systems critically.`,
      published_at: "2026-03-06",
      author: "I Hate Banks Editorial Team",
      tags: ["article", "options", "research"],
      level: "intermediate",
      estimated_minutes: 10,
      references: REF(topic),
      disclaimer_required: true,
      thesis: `${topic} should be evaluated with a risk-first and validation-first mindset.`,
      related_strategies: ["openclaw_put_credit_spread|legacy_replica", "openclaw_call_credit_spread|ccs_baseline"],
    };
    const body = md(
      "## Thesis",
      `${topic} requires context from drawdown, execution quality, and out-of-sample evidence.`,
      "",
      "## Evidence framework",
      "- Compare return and drawdown jointly.",
      "- Verify assumptions and fill realism.",
      "- Prefer stable behavior across regimes.",
      "",
      "## Practical checklist",
      "Use this framework before promoting any strategy to production."
    );
    await writeFile(DIRS.articles, slug, fm, body);
  }
}

async function seedExplainers() {
  for (const [slug, title, strategyKey, level] of EXPLAINERS) {
    const fm = {
      slug,
      title,
      summary: `${title} covers setup rules, entries, exits, and failure modes for educational use.`,
      published_at: "2026-03-06",
      author: "I Hate Banks Editorial Team",
      tags: ["strategy-explainer", "options"],
      level,
      estimated_minutes: 12,
      references: REF(title),
      disclaimer_required: true,
      strategy_key: strategyKey,
      setup_rules: ["Define universe and contract constraints.", "Set risk budget and position caps.", "Require liquidity and spread quality checks."],
      entry_logic: ["Use strategy-specific regime filters.", "Select strikes and DTE by rules, not discretion.", "Validate credit or extrinsic quality before entry."],
      exit_logic: ["Take profit at predefined thresholds.", "Cut risk via stop logic and time exits.", "Document exits for post-trade review."],
      risk_profile: ["Tail moves can dominate PnL distribution.", "Correlated exposure can cluster losses.", "Execution friction can reduce expected edge."],
      common_failure_modes: ["Filter drift under pressure.", "Over-sizing after winning streaks.", "Ignoring OOS and execution constraints."],
    };
    const body = md(
      "## How it works",
      "This explainer translates strategy rules into operational steps and risk controls.",
      "",
      "## What to watch",
      "- Regime mismatch",
      "- Position concentration",
      "- Execution quality decay",
      "",
      "## Use with site data",
      "Pair this explainer with the Strategies and Backtest pages to compare theory and evidence."
    );
    await writeFile(DIRS.explainers, slug, fm, body);
  }
}

async function run() {
  await ensureDirs();
  await Promise.all([seedGlossary(), seedLessons(), seedArticles(), seedExplainers()]);
  console.log("[seed:education] generated 40 glossary, 12 lessons, 12 articles, 10 strategy explainers.");
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
