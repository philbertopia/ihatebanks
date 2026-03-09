---
slug: regime-portfolio-upgrade-comparison
title: Regime portfolio upgrade comparison
summary: >-
  Research-only comparison of portfolio overlays around the current regime
  credit spread core. The plain core still wins. Drawdown throttling never
  engaged in the tested window, while the volatility kill-switch reduced return
  more than it reduced drawdown.
published_at: '2026-03-09'
updated_at: '2026-03-09'
author: I Hate Banks Editorial Team
tags:
  - article
  - backtesting
  - portfolio-construction
  - options
  - research
level: intermediate
estimated_minutes: 10
references:
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Good reference for understanding why defined-risk spread systems can be
      managed at the portfolio level without changing the spread template
      itself.
  - title: CME - Volatility Basics
    url: 'https://www.cmegroup.com/education/courses/introduction-to-volatility.html'
    source: article
    why_it_matters: >-
      Useful framing for why volatility pauses can reduce tail risk but also
      suppress premium-selling opportunity.
  - title: tastylive channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      Useful source for thinking about portfolio-level options risk management
      and why reducing entries during stressed volatility regimes can lower risk
      but also reduce opportunity.
disclaimer_required: true
thesis: >-
  The current regime-switch champion is already resilient enough that the first
  portfolio overlays did not improve it. In the tested 2020-2025 window,
  drawdown throttling was inert and the volatility kill-switch modestly reduced
  drawdown but gave up too much return, so the plain regime core remains the
  preferred local portfolio configuration.
related_strategies:
  - openclaw_regime_credit_spread|regime_legacy_defensive
  - openclaw_regime_credit_spread|regime_balanced
  - openclaw_regime_credit_spread|regime_defensive
  - openclaw_put_credit_spread|legacy_replica
  - openclaw_call_credit_spread|ccs_defensive
---
## What was tested
This research pass did not change the spread engine itself. The core strategy
stayed:

- bullish regime -> `legacy_replica` put credit spreads
- bearish or neutral regime -> `ccs_defensive`

The only change was portfolio-level overlays around that core:

- `regime_core_base`
- `regime_core_drawdown`
- `regime_core_killswitch`
- `regime_core_overlay`

These overlays were tested over `2020-01-02` through `2025-12-31` with the same
walk-forward window used elsewhere in the repo: `504 / 126 / 126`.

## Result
The plain core still wins.

- `regime_core_base`: `+185.95%` total return, Sharpe `6.04`, max drawdown
  `1.52%`, OOS return `+17.42%`, OOS Sharpe `8.39`, OOS max drawdown `1.04%`,
  walk-forward pass
- `regime_core_drawdown`: identical to base in this window
- `regime_core_killswitch`: `+173.90%` total return, OOS return `+16.09%`, OOS
  Sharpe `7.86`, OOS max drawdown `0.96%`, walk-forward pass
- `regime_core_overlay`: identical to the kill-switch profile in practice

That means no overlay beat the plain core on the OOS-first ranking.

## Why the overlays did not help
Two findings matter.

First, the drawdown throttle never activated. The tested core never breached the
`5%` portfolio drawdown trigger, so the drawdown-only profile finished
identically to the base.

Second, the volatility kill-switch did activate, but not profitably enough.
It blocked new entries on `108` days and slightly reduced OOS max drawdown from
`1.04%` to `0.96%`. That is real but small. The cost was lower total return and
lower OOS return.

The practical interpretation is simple: this core is already conservative
enough that heavy defensive overlays can become a tax rather than an upgrade.

## What this means for the portfolio
The local portfolio architecture should now be read as:

- core sleeve: `openclaw_regime_credit_spread|regime_legacy_defensive`
- supporting sleeves for monitoring: `legacy_replica` PCS and `ccs_defensive`
- benchmark sleeves: `regime_balanced` and `regime_defensive`
- no neutral iron condor sleeve yet
- no convex hedge sleeve yet

That is a stronger position than adding more moving parts without evidence.

## Next step
The next portfolio improvement should not be another overlay sweep unless the
underlying core changes. The better next move is to keep the current regime core
as the portfolio anchor and only test a hedge sleeve if that hedge can first
pass its own standalone walk-forward bar.
