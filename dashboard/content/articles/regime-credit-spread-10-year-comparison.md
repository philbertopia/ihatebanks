---
slug: regime-credit-spread-10-year-comparison
title: Regime credit spread 10-year comparison
summary: >-
  Local research note comparing all six regime-credit-spread variants over a
  continuous 2016-2025 extension, now positioned as one family inside the
  broader first-wave credit-spread 10-year research coverage.
published_at: '2026-03-08'
updated_at: '2026-03-09'
author: I Hate Banks Editorial Team
tags:
  - article
  - backtesting
  - regime-analysis
  - options
  - research
level: intermediate
estimated_minutes: 16
references:
  - title: Option Alpha channel
    url: 'https://www.youtube.com/@OptionAlpha'
    source: youtube
    why_it_matters: >-
      Useful practical context for comparing defined-risk premium-selling
      profiles across bullish, bearish, and neutral market states.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Foundation for understanding credit spread mechanics, assignment risk, and
      why high win-rate strategies still require careful drawdown analysis.
  - title: CME - Equity Index Volatility Basics
    url: 'https://www.cmegroup.com/education/courses/introduction-to-volatility.html'
    source: article
    why_it_matters: >-
      Helpful background for thinking about regime shifts, volatility quality,
      and why premium-selling behavior changes across long market cycles.
disclaimer_required: true
thesis: >-
  The continuous 2016-2025 research sweep confirms
  `openclaw_regime_credit_spread|regime_legacy_defensive` as the strongest
  local regime-credit-spread profile, but the result should remain outside the
  official dashboard metrics until the longer data source is part of the main
  cached research pipeline.
related_strategies:
  - openclaw_regime_credit_spread|regime_legacy_defensive
  - openclaw_regime_credit_spread|regime_balanced
  - openclaw_regime_credit_spread|regime_defensive
  - openclaw_regime_credit_spread|regime_vix_baseline
---
## Why this note exists
The regime-credit-spread family already had strong local `2020-2025` persisted
results, but that still left one important question open: which regime router
looks best when the test is stretched across a longer market cycle.

This note now sits inside the broader local research rollout documented in
[Credit spread 10-year research coverage](/education/articles/credit-spread-10-year-research-coverage).
That broader note explains why the first-wave site coverage now includes the
top regime, put-credit-spread, and call-credit-spread variants together rather
than treating the regime family as a one-off exception.

To answer that, I ran a separate research-only `2016-01-01` through
`2025-12-31` comparison across all six local regime variants:

- `regime_legacy_defensive`
- `regime_balanced`
- `regime_defensive`
- `regime_vix_baseline`
- `regime_legacy_defensive_bear_only`
- `regime_vix_baseline_bear_only`

This note summarizes that sweep and keeps it distinct from the official
dashboard data.

## Why the 10-year run is research-only
The project cache does not contain a continuous SPY and QQQ history for the full
`2016-2025` window. The broader scripted research runner found a real
price-history gap from December 13, 2016 through January 1, 2020. For this
regime engine, that can be filled defensibly with adjusted ETF closes because
the engine only consumes underlying price history, not full option-chain
history.

That still does not make the result equivalent to the main pipeline. The
official local dashboard metrics are intentionally anchored to the normal cached
research source and persisted through the standard backtest payload files. This
10-year work is a research layer, not a replacement for that official dataset.

## What the scripted comparison found
The winner is `openclaw_regime_credit_spread|regime_legacy_defensive`.

Its continuous `2016-2025` result came in at:

- total return `+229.67%`
- Sharpe `3.68`
- max drawdown `2.88%`
- `893` trades
- win rate `96.64%`
- walk-forward average OOS return `+12.55%`
- walk-forward average OOS Sharpe `5.65`
- walk-forward average OOS max drawdown `1.06%`

The broader family remained strong. `regime_balanced` finished close behind at
`+227.18%` with a lower OOS Sharpe of `4.99`. `regime_vix_baseline` still
produced `+205.87%`. Even the two bear-only variants stayed positive over the
full extension.

## Why the winner is still the practical leader
`regime_legacy_defensive` is not first just because it had the highest return.
It also led the family on the OOS-first ranking rule used in the research
runner. That matters because the point of this family is not raw upside alone.
It is to combine already credible bullish and bearish spread templates into a
router that stays stable when market tone changes.

The winning profile does that best right now. It keeps the stronger bullish PCS
leg from `legacy_replica`, swaps in the more defensive CCS template when the
regime turns bearish or neutral, and still trades often enough for the sample to
mean something.

## Why `regime_defensive` is not the practical second choice
The OOS-first ranking still places `regime_defensive` near the top because its
walk-forward averages stayed clean. But the full-period run only produced `10`
trades over the entire `2016-2025` window and finished at `-0.22%` total
return.

That is exactly the kind of result that can look elegant in a summary table and
still be too sparse to trust. So the right reading is not that
`regime_defensive` is secretly better. The right reading is that the family
needs a trade-density sanity check whenever a very selective variant shows an
improbably clean OOS profile.

## How to use this locally
Use the local site in two layers:

1. Treat the standard Strategies, Backtest, and Walk-Forward pages as the
   official local metric layer because they still reflect the persisted
   `2020-2025` cache.
2. Use the new `10-Year Research` panels plus the broader
   [credit-spread coverage note](/education/articles/credit-spread-10-year-research-coverage)
   as the longer-horizon research layer.
3. Read the strategy explainer for `regime_legacy_defensive` if you want to see
   the routing logic that produced the current winning result.

That separation keeps the workspace honest. The official dashboard stays tied to
the normal pipeline, while the 10-year comparison remains visible, reproducible,
and clearly labeled as research.
