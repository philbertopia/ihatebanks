---
slug: research-index-swing-options-initial-sweep
title: Research index swing options initial sweep
summary: >-
  First two local sweeps of the new SPY/QQQ swing-hybrid family. A broader
  second pass improved raw return a bit, but the router still failed to produce
  meaningful PCS or CCS participation, so the family remains research-only and
  does not get a 10-year extension.
published_at: '2026-03-09'
updated_at: '2026-03-09'
author: I Hate Banks Editorial Team
tags:
  - article
  - backtesting
  - options
  - swing-trading
  - research
level: intermediate
estimated_minutes: 12
references:
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Useful background for understanding why debit spreads and credit spreads
      behave differently across volatility regimes.
  - title: tastylive channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      Practical context for comparing premium-buying and premium-selling
      structures across different implied-volatility environments.
  - title: CME - Volatility Basics
    url: 'https://www.cmegroup.com/education/courses/introduction-to-volatility.html'
    source: article
    why_it_matters: >-
      Helps frame why the same bullish swing thesis can favor premium buying in
      low IV and premium selling in high IV.
disclaimer_required: true
thesis: >-
  The SPY/QQQ swing-hybrid idea is still not investable after two sweeps:
  the broader second pass raised raw return, but none of the eight tested
  variants passed walk-forward validation, and both sweeps still realized
  trades almost entirely through the low-IV debit-spread branch instead of a
  true multi-structure router.
related_strategies:
  - research_index_swing_options|pullback_baseline_45_60_v2
  - research_index_swing_options|pullback_baseline_45_60
  - research_index_swing_options|pullback_baseline_30_45
  - openclaw_tqqq_swing|legacy_replica
  - openclaw_regime_credit_spread|regime_legacy_defensive
---
## What was tested
This sweep introduced a new local research family named
`research_index_swing_options`. The family trades only `SPY` and `QQQ` and was
designed to stop forcing one options structure into every environment.

The routing idea was straightforward:

- bullish pullback plus low IV: buy a bull call debit spread
- bullish pullback plus higher IV: sell a put credit spread
- neutral or bearish rally-fade plus high IV: sell a call credit spread
- otherwise: stay in cash

The first pass used four variants:

- `pullback_baseline_30_45`
- `pullback_defensive_30_45`
- `pullback_baseline_45_60`
- `pullback_defensive_45_60`

The second pass added four broader `v2` variants to make the higher-IV routing
more permissive:

- `pullback_baseline_30_45_v2`
- `pullback_defensive_30_45_v2`
- `pullback_baseline_45_60_v2`
- `pullback_defensive_45_60_v2`

## Results
The raw `2020-01-02` through `2025-12-31` backtest results were:

- `pullback_baseline_30_45`: `+3.13%` total return, Sharpe `-4.65`, max drawdown `0.60%`, `5` trades
- `pullback_defensive_30_45`: `+2.19%` total return, Sharpe `-7.18`, max drawdown `0.61%`, `4` trades
- `pullback_baseline_45_60`: `+4.96%` total return, Sharpe `-4.26`, max drawdown `0.35%`, `6` trades
- `pullback_defensive_45_60`: `+2.28%` total return, Sharpe `-6.28`, max drawdown `0.75%`, `6` trades

The walk-forward results were more important:

- `pullback_baseline_30_45`: OOS avg return `+0.03%`, OOS Sharpe `-0.49`, OOS max drawdown `0.08%`, `FAIL`
- `pullback_defensive_30_45`: OOS avg return `+0.03%`, OOS Sharpe `-0.49`, OOS max drawdown `0.08%`, `FAIL`
- `pullback_baseline_45_60`: OOS avg return `+0.38%`, OOS Sharpe `0.02`, OOS max drawdown `0.05%`, `FAIL`
- `pullback_defensive_45_60`: OOS avg return `+0.20%`, OOS Sharpe `-0.16`, OOS max drawdown `0.04%`, `FAIL`

The `45-60` baseline version was the least bad of the four, but that is still
not close to a convincing OOS pass.

## Second sweep
The second sweep widened the pullback and rally-fade envelopes, lowered the
IV threshold needed to route into credit-spread branches, and added a limited
bullish-overextension path for CCS entries.

That produced slightly better raw returns:

- `pullback_baseline_30_45_v2`: `+2.23%` total return, Sharpe `-5.97`, max drawdown `1.37%`, `6` trades
- `pullback_defensive_30_45_v2`: `+1.30%` total return, Sharpe `-7.46`, max drawdown `1.22%`, `8` trades
- `pullback_baseline_45_60_v2`: `+6.97%` total return, Sharpe `-3.33`, max drawdown `0.32%`, `7` trades
- `pullback_defensive_45_60_v2`: `+4.12%` total return, Sharpe `-5.17`, max drawdown `0.37%`, `7` trades

But the walk-forward picture still failed the bar:

- `pullback_baseline_30_45_v2`: OOS avg return `+0.15%`, OOS Sharpe `-19.46`, OOS max drawdown `0.11%`, `FAIL`
- `pullback_defensive_30_45_v2`: OOS avg return `+0.14%`, OOS Sharpe `-19.47`, OOS max drawdown `0.11%`, `FAIL`
- `pullback_baseline_45_60_v2`: OOS avg return `+0.53%`, OOS Sharpe `0.12`, OOS max drawdown `0.05%`, `FAIL`
- `pullback_defensive_45_60_v2`: OOS avg return `+0.29%`, OOS Sharpe `-0.07`, OOS max drawdown `0.04%`, `FAIL`

`pullback_baseline_45_60_v2` is now the least bad profile in the family on raw
return, but it still does not clear the project OOS gate.

## What actually happened inside the engine
The most important diagnostic is simple: the realized trades in both sweeps
still came from the low-IV bull call debit-spread branch.

That means the routing idea did not fail because the debit spread branch was
catastrophic. It failed because the trigger stack almost never
produced qualifying high-IV put-credit-spread or call-credit-spread entries.

So the current result is not really a balanced hybrid yet. It is still a sparse
index debit-spread strategy wearing a hybrid wrapper.

## How it compares to existing swing candidates
This is still worth documenting because it did improve on the older
stock-replacement swing-call variants in one narrow sense.

The older local swing-call variants were all weak:

- `swing_rsi_bounce`: about `+0.25%`
- `swing_momentum_breakout`: about `-1.34%`
- `swing_aggressive`: about `-2.44%`
- `swing_conservative`: about `-0.78%`

So the new family did beat that older cluster on raw return. But that is not a
high bar, and those older variants did not have the same level of walk-forward
coverage.

Against better benchmark ideas, the gap is still large:

- `openclaw_tqqq_swing|legacy_replica`: about `+13.67%`, but still weak on risk-adjusted quality
- `openclaw_regime_credit_spread|regime_legacy_defensive`: about `+189.41%`, OOS return `+17.38%`, OOS Sharpe `7.29`, clear pass

That comparison matters because the real goal is not just to beat the weakest
old swing ideas. The goal is to find something that deserves more research than
the existing regime credit-spread winner.

The second sweep narrowed that gap slightly, but this family is still nowhere
near the current regime-credit-spread leader.

## Why there is no 10-year extension
The project rule for extending a new family into a research-only `2016-2025`
test was:

- at least one variant passes walk-forward
- total trades `>= 120`
- max drawdown `<= 25%`

None of the eight tested variants passed the first condition, and all eight
were far too sparse on trade count anyway.

So the family stops here for now. There is no 10-year research JSON, no
research heatmap, and no strategy explainer promotion for this sweep.

## What to improve before the next sweep
The next iteration should focus on making the router real instead of just
refining the debit-spread leg again.

The highest-value changes are:

- add an explicit high-IV branch test harness so PCS and CCS routing can be verified before full backtests
- consider a simpler or less sparse IV proxy for SPY and QQQ so the hybrid can actually switch structures
- decide whether this family should be reworked around daily price-only signals instead of option-chain-derived IV percentile
- only revisit 10-year research if a future sweep produces a real OOS pass with enough trades

That is the right bar. Until then, this remains a useful failed experiment, not
the next flagship swing strategy.
