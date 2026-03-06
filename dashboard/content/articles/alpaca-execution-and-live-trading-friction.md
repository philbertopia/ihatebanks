---
slug: alpaca-execution-and-live-trading-friction
title: Alpaca execution and live trading friction
summary: >-
  A practical guide for translating paper strategy logic into broker reality:
  orders, fills, assignment, and operational controls.
published_at: '2026-03-06'
updated_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - article
  - alpaca
  - execution
  - live-trading
  - operations
level: intermediate
estimated_minutes: 12
references:
  - title: Alpaca YouTube channel
    url: 'https://www.youtube.com/@alpaca-markets'
    source: youtube
    why_it_matters: >-
      Platform-specific examples and product behavior that help bridge docs and
      practical implementation.
  - title: Alpaca Trading API - Orders
    url: 'https://docs.alpaca.markets/docs/trading/orders/'
    source: docs
    why_it_matters: >-
      Source of truth for order lifecycle, replacement semantics, and rejection
      behavior in production code.
  - title: OCC - Characteristics and Risks of Standardized Options
    url: 'https://www.theocc.com/company-information/documents-and-archives/publications'
    source: docs
    why_it_matters: >-
      Canonical assignment/exercise and risk disclosure background for live
      options operations.
disclaimer_required: true
thesis: >-
  Broker integration is not a thin transport layer; it is part of the strategy
  itself because order semantics and fill behavior alter realized edge.
related_strategies:
  - stock_replacement|wheel_d30_c30
  - stock_replacement|wheel_d20_c30
  - openclaw_put_credit_spread|legacy_replica
---
## Why broker behavior belongs in research
Many strategy failures happen at the boundary between model and execution. A
backtest may assume clean entry/exit events, but a live broker environment
introduces partial fills, order state transitions, latency, exchange routing
differences, and assignment flows.

If those realities are not encoded into the operating process, your strategy is
under-specified. In production, under-specified systems become discretionary
systems under stress.

## As-of strategy context
As of 2026-03-06, based on `dashboard/public/data/strategies.json`:

- `stock_replacement|wheel_d30_c30`: return 164.93%, Sharpe 0.69, max DD 26.31%,
  OOS Sharpe 0.70, pass.
- `stock_replacement|wheel_d20_c30`: return 103.66%, Sharpe 0.44, max DD 31.63%,
  OOS Sharpe 0.60, fail.
- `openclaw_put_credit_spread|legacy_replica`: return 299.52%, Sharpe 6.20, max
  DD 0.19%, OOS Sharpe 3.96, pass.

These are strategy metrics, not execution guarantees. Live quality depends on
broker interactions.

## Core friction points with live options execution
1. **Order lifecycle complexity**: new, accepted, partially filled, replaced,
   canceled, rejected.
2. **Partial fill handling**: execution state can differ from intended position.
3. **Assignment events**: wheel and short premium systems must handle transitions
   between option and stock inventory.
4. **Session constraints**: open/close periods and event windows affect spread
   width and fill probability.
5. **Reconciliation lag**: account state and expected state can diverge briefly.

Operational robustness means handling each state transition explicitly.

## Failure modes in Alpaca-integrated systems
- Sending duplicate orders during transient API errors.
- Assuming full fills before confirmation and over-sizing unintentionally.
- Ignoring assignment notifications until the next session.
- Treating rejected orders as "no-op" instead of strategy-state events.
- Missing risk reduction because cancel/replace logic is not atomic.

Every one of these can convert a valid strategy into an avoidable loss process.

## Design controls for production readiness
Use a minimum live-control set:

1. **Idempotent order submission** keyed by strategy intent.
2. **State-machine position tracking** for options and underlying shares.
3. **Assignment-aware transitions** for wheel phases.
4. **Hard risk limits** independent of signal quality.
5. **Daily reconciliation report** for expected vs actual positions.

These controls should be built before scaling, not after a live incident.

## Practical deployment checklist
- Paper trade each strategy mode with production order paths.
- Log order round-trip latency and fill quality by symbol/time bucket.
- Validate cancel/replace logic under simulated intermittent failures.
- Create runbooks for assignment, partial fill, and rejection scenarios.
- Keep manual override procedures documented and audited.

A strategy is live-ready only when its operational envelope is as well-defined
as its alpha thesis.
