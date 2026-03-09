---
slug: regime-credit-spread-timed-entry-sweep
title: Regime credit spread timed-entry sweep
summary: >-
  Local sweep of eight timed-entry variants around the current regime credit
  spread winner. Timing gates produced cleaner trade clustering and low
  drawdowns, but none of the variants improved on the current winner's
  out-of-sample profile, so the family leader stays unchanged.
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
estimated_minutes: 10
references:
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Useful baseline reference for why spread management and profit capture
      choices can materially change realized option outcomes.
  - title: tastylive channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      Practical context for the idea of timing premium-selling entries around
      pullbacks and rally fades rather than selling every day.
  - title: CME - Volatility Basics
    url: 'https://www.cmegroup.com/education/courses/introduction-to-volatility.html'
    source: article
    why_it_matters: >-
      Helps frame why timing filters can reduce opportunity count without
      necessarily improving risk-adjusted performance.
disclaimer_required: true
thesis: >-
  Timing the current regime credit spread winner improved selectivity and kept
  drawdowns very low, but it did not improve the strategy's out-of-sample edge.
  The best timed variants stayed well below the existing regime leader on OOS
  Sharpe, OOS return, and trade count, so `regime_legacy_defensive` remains the
  practical leader.
related_strategies:
  - openclaw_regime_credit_spread|timed_legacy_defensive_50_14_r125
  - openclaw_regime_credit_spread|timed_legacy_defensive_50_10_r100
  - openclaw_regime_credit_spread|regime_legacy_defensive
  - openclaw_call_credit_spread|ccs_defensive
  - openclaw_put_credit_spread|legacy_replica
---
## What changed
This sweep did not invent a new spread structure. It kept the same winning
router:

- bull regime: `legacy_replica` put credit spread
- bear and neutral regimes: `ccs_defensive`

The change was entry timing. Instead of opening a spread on any qualifying
regime day, the timed variants waited for:

- bull pullbacks before opening PCS
- bear rally fades before opening CCS
- neutral rally fades before opening CCS in the non-bear-only variants

Eight variants were tested, changing only three things:

- profit capture target: `40%`, `50%`, or `60%`
- forced exit: `7`, `10`, or `14` DTE
- risk scaling: `0.75x`, `1.00x`, or `1.25x`

## Best results
The best two timed variants were:

- `timed_legacy_defensive_50_10_r100`: `+29.98%` total return, Sharpe `-0.36`, max drawdown `0.60%`, `87` trades, OOS avg return `+2.97%`, OOS Sharpe `0.06`, OOS max drawdown `0.32%`
- `timed_legacy_defensive_50_14_r125`: `+29.88%` total return, Sharpe `-0.36`, max drawdown `0.60%`, `87` trades, OOS avg return `+2.97%`, OOS Sharpe `0.06`, OOS max drawdown `0.32%`

Those are respectable low-drawdown research results, but they do not beat the
current regime leader:

- `regime_legacy_defensive`: `+189.41%` total return, OOS avg return `+17.38%`, OOS Sharpe `7.29`, OOS max drawdown `1.14%`, `PASS`

So the timed sweep improved selectivity, but it did not improve the actual edge.

## What the sweep found
Three findings matter most.

First, the timed router did behave like a real multi-side spread engine. Unlike
the failed index swing hybrid family, these variants opened both put and call
spreads. The best non-bear-only profiles logged `44` put entries and `43` call
entries.

Second, the timed variants were too sparse to be serious leaders. The project
bar for naming a real candidate was at least `250` trades with meaningful usage
of both sides. The best timed variants only reached `87` trades.

Third, several variants were effectively duplicates in practice:

- `timed_legacy_defensive_40_7_r075` and `timed_legacy_defensive_40_10_r100` finished identically
- `timed_legacy_defensive_50_10_r100` and `timed_legacy_defensive_50_14_r125` finished almost identically
- `timed_legacy_defensive_bear_only_50_10_r100` and `timed_legacy_defensive_bear_only_50_7_r075` finished identically

That is useful. It means the timed-entry filter dominated the result, while the
management overrides were often not binding often enough to create a new edge.

## Why nothing was promoted
None of the eight timed variants passed walk-forward validation. All of them
had positive average OOS return, but their OOS Sharpe readings stayed far below
the regime family threshold.

That means:

- no new champion
- no update to the regime family's main winner
- no 10-year extension for these timed variants

The original `regime_legacy_defensive` profile remains the strategy to beat.

## What this means for the next step
This sweep answered an important question: timing alone is not enough. Waiting
for pullbacks and rally fades reduced activity and kept drawdowns low, but it
also stripped away too much opportunity.

The next useful move is simpler than another management sweep:

- keep the regime credit spread family
- keep the same underlying PCS and CCS templates
- test a price-only timing layer that is less restrictive than the current
  RSI-plus-return gates

That is a better next experiment than another long-premium strategy or another
debit-spread hybrid.
