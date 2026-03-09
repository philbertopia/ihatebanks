---
slug: credit-spread-10-year-research-coverage
title: Credit spread 10-year research coverage
summary: >-
  First-wave local 10-year research coverage for the strongest credit-spread
  families, including month-by-month results, gap-fill methodology, and the
  current leaders in regime, put-credit-spread, and call-credit-spread tests.
published_at: '2026-03-09'
updated_at: '2026-03-09'
author: I Hate Banks Editorial Team
tags:
  - article
  - backtesting
  - options
  - research
  - regime-analysis
level: intermediate
estimated_minutes: 18
references:
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Foundation for understanding vertical spread risk, assignment mechanics,
      and why high win-rate options systems still need drawdown context.
  - title: CME - Equity Index Volatility Basics
    url: 'https://www.cmegroup.com/education/courses/introduction-to-volatility.html'
    source: article
    why_it_matters: >-
      Useful background for understanding why premium-selling behavior changes
      across long regime shifts and volatility cycles.
  - title: Option Alpha channel
    url: 'https://www.youtube.com/@OptionAlpha'
    source: youtube
    why_it_matters: >-
      Practical context for comparing defined-risk premium-selling profiles
      rather than treating a single spread direction as universally correct.
disclaimer_required: true
thesis: >-
  The first-wave 10-year research sweep supports three credible local leaders:
  `regime_legacy_defensive` for regime routing, `legacy_replica` for put credit
  spreads, and `ccs_defensive` for call credit spreads, while keeping the full
  extension clearly separated from the official dashboard metrics.
related_strategies:
  - openclaw_regime_credit_spread|regime_legacy_defensive
  - openclaw_put_credit_spread|legacy_replica
  - openclaw_call_credit_spread|ccs_defensive
---
## What this first wave covers
This first wave adds local 10-year research coverage for the three
credit-spread families that can be extended most defensibly from underlying ETF
price history:

- `openclaw_regime_credit_spread`
- `openclaw_put_credit_spread`
- `openclaw_call_credit_spread`

Coverage is intentionally limited to the top three validated variants in each
family, not every experiment in the repo. That keeps the research layer focused
on strategies that already showed some evidence in the standard local
`2020-2025` dataset.

## Why only these families
These engines are the cleanest candidates for a longer extension because they
are built around SPY and QQQ regime and price behavior rather than needing a
fully continuous multi-year option-chain history for dozens of symbols.

That is not true for every family in the project. Stock replacement, wheel,
intraday, and other chain-sensitive strategies are more vulnerable to missing or
incomplete historical option detail, so they are excluded from this first
research wave.

## How the 10-year data was built
The local cache does not contain a continuous SPY and QQQ daily history for the
full `2016-01-01` through `2025-12-31` window. The research runner detected a
real gap from December 13, 2016 through January 1, 2020 and filled that span
with adjusted ETF closes from `yfinance`.

That makes the longer run reasonable for research because these covered
credit-spread families consume underlying price history rather than a full
observed option chain. It still does **not** make the result equivalent to the
official dashboard metrics. The site now shows this extension in research-only
panels, while the official strategy tables remain tied to the persisted project
dataset.

## Current family leaders
The current leaders from the first-wave `2016-2025` sweep are:

- Regime credit spread: `openclaw_regime_credit_spread|regime_legacy_defensive`
  with `+229.67%` total return, `3.68` Sharpe, `2.88%` max drawdown, `893`
  trades, and `5.65` average OOS Sharpe.
- Put credit spread: `openclaw_put_credit_spread|legacy_replica` with
  `+157.58%` total return, `2.24` Sharpe, `3.14%` max drawdown, `536` trades,
  and `3.01` average OOS Sharpe.
- Call credit spread: `openclaw_call_credit_spread|ccs_defensive` with
  `+147.64%` total return, `2.72` Sharpe, `1.08%` max drawdown, `647` trades,
  and `4.52` average OOS Sharpe.

Those are not just the raw-return winners. They are the leaders under the
OOS-first ranking rule used in the research runner.

## One important nuance in the call-spread family
`ccs_baseline` actually posted the higher full-period return at `+175.15%`, but
`ccs_defensive` still ranked first because it had the stronger OOS Sharpe and
the lower OOS drawdown. That is exactly the tradeoff the research layer is
meant to surface.

If you only sorted by total return, you would miss the fact that the defensive
profile is the cleaner longer-horizon candidate.

## Sparse-sample warning rule
Any variant with fewer than `100` total trades over the full 10-year run now
gets a visible warning in both the research data and the local site.

The regime family shows why that matters. `regime_defensive` still looks clean
in walk-forward averages, but it only took `10` trades over the entire
extension. That is too sparse to trust as a practical production winner, so it
is flagged even though it remains visible.

## How to read the new website panels
The site now separates the two layers:

1. The standard strategy and backtest metrics remain the official local view.
2. The new `10-Year Research` panels show the research-only extension.
3. The leaderboard uses a subtle `10Y Research` marker to show coverage without
   blending research figures into the main ranking columns.

That separation is deliberate. The research layer is meant to expand context,
not quietly replace the official dataset.
