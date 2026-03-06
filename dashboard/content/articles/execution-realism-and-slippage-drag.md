---
slug: execution-realism-and-slippage-drag
title: Execution realism and slippage drag
summary: >-
  How fill assumptions and microstructure friction reshape options strategy
  performance, often more than signal quality itself.
published_at: '2026-03-06'
updated_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - article
  - execution
  - slippage
  - microstructure
  - options
level: intermediate
estimated_minutes: 13
references:
  - title: SMB Capital - trading execution videos
    url: 'https://www.youtube.com/@smbcapital'
    source: youtube
    why_it_matters: >-
      Real desk-level discussion of order quality, liquidity context, and why
      execution edge matters as much as signal edge.
  - title: Alpaca Trading API documentation
    url: 'https://docs.alpaca.markets/docs/trading/orders/'
    source: docs
    why_it_matters: >-
      Concrete order handling semantics required to map backtest assumptions to
      live brokerage behavior.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Educational detail on spread behavior, liquidity conditions, and options
      execution mechanics.
disclaimer_required: true
thesis: >-
  A strategy without realistic execution assumptions is not conservative or
  aggressive; it is simply mismeasured.
related_strategies:
  - intraday_open_close_options|baseline
  - intraday_open_close_options|conservative
  - openclaw_put_credit_spread|legacy_replica
---
## Why execution realism is non-negotiable
Backtests are usually built from bars, but live PnL is built from fills. If
your model assumes fills near midpoint in conditions where you would actually
cross spread or get partial fills, expected edge can collapse quickly.

Options strategies are especially sensitive because slippage applies at entry
and exit, and many strategies trade frequently. Small per-trade friction can
dominate long-run outcomes.

## As-of snapshot from this project
As of 2026-03-06, based on `dashboard/public/data/strategies.json`:

- `intraday_open_close_options|baseline`: return 6496.89%, Sharpe 2.51, max DD
  21.55%, OOS Sharpe -1.56, fail.
- `intraday_open_close_options|conservative`: return 2127.02%, Sharpe 3.48, max
  DD 10.07%, OOS Sharpe -1.08, fail.
- `openclaw_put_credit_spread|legacy_replica`: return 299.52%, Sharpe 6.20, max
  DD 0.19%, OOS Sharpe 3.96, pass.

These numbers do not imply one profile is "real" and another is "fake." They
show that execution assumptions and trade cadence interact with robustness.

## Quant mechanics of slippage drag
A simple approximation:

`net_edge = gross_edge - (entry_slippage + exit_slippage + fees + spread_cost)`

For high-turnover strategies, this subtraction happens many times. For lower
turnover strategies, each trade carries larger directional risk and spread width
sensitivity. In both cases, execution matters.

Key sensitivity levers:

- spread width vs target profit size,
- trade frequency,
- fill probability assumptions,
- partial fill behavior,
- stop execution quality in fast markets.

## Failure modes in execution modeling
- **Midpoint fantasy**: systematic midpoint fills in names/times where that is
  not achievable.
- **No partial fills**: assuming binary fill outcomes while live routing often
  fills unevenly.
- **Static spread model**: ignoring spread expansion around event risk and open/close.
- **Stop certainty**: treating stops as deterministic instead of path-sensitive.

Each failure mode inflates backtest quality and creates false confidence.

## Strategy evidence and caveats
Intraday profiles frequently look strong in-sample because they exploit many
small opportunities. But those same profiles are most vulnerable to execution
error because each missed or poor-quality fill compounds across many trades.

Credit spread profiles can look more stable because they trade less frequently
and rely on broader distributional edge, but they still face tail risk and
pricing gaps in stress conditions.

The point is not that one class always wins. It is that execution realism must
be embedded before comparing strategies.

## Practical execution checklist
1. Use conservative fill assumptions by default.
2. Stress-test spread and slippage assumptions with scenario bands.
3. Simulate partial fills and stale quotes.
4. Add per-strategy execution KPIs: fill rate, average slippage, and spread
   paid as percent of expected edge.
5. Reconcile backtest assumptions with broker order semantics before deployment.

Execution realism is not a detail to add at the end. It is part of the core
model definition.
