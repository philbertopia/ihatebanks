---
slug: qqq-falling-knife-pcs-research-note
title: QQQ falling knife PCS research note
summary: >-
  Local research note comparing the new QQQ-only falling-knife put credit
  spread proxy against the existing PCS variants already published in the
  dashboard dataset.
published_at: '2026-03-08'
updated_at: '2026-03-08'
author: I Hate Banks Editorial Team
tags:
  - article
  - backtesting
  - options
  - qqq
  - validation
level: intermediate
estimated_minutes: 14
references:
  - title: tastylive QQQ falling knife trade example
    url: 'https://www.youtube.com/watch?v=eKhFqFsIVww'
    source: youtube
    why_it_matters: >-
      This is the source trade concept that motivated the local strategy proxy
      added to the PCS family.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Useful context for why defined-risk credit spreads can be attractive in
      volatile tape but still require careful validation.
  - title: CME - Equity Index Volatility Basics
    url: 'https://www.cmegroup.com/education/courses/introduction-to-volatility.html'
    source: article
    why_it_matters: >-
      Background for understanding why volatility spikes may improve premium
      collection while also changing tail-risk behavior.
disclaimer_required: true
thesis: >-
  The video-inspired QQQ falling-knife PCS can be translated into a local,
  backtestable ruleset, but in this repo it behaves as a niche low-turnover
  research profile rather than a replacement for the existing PCS leaders.
related_strategies:
  - openclaw_put_credit_spread|qqq_falling_knife
  - openclaw_put_credit_spread|legacy_replica
  - openclaw_put_credit_spread|pcs_vix_optimal
---
## What was implemented
The new local variant is `openclaw_put_credit_spread|qqq_falling_knife`. It is
not an exact replay of the original video trade. Instead, it is a daily-rule
proxy designed to preserve the core idea:

- QQQ only
- long-term support via price above the 200 day average
- short-term downside shock via RSI, selloff, and pullback filters
- far-OTM, defined-risk put credit spread sizing intended to reflect a
  high-probability income trade

That distinction matters. A faithful backtest requires rules that can be
repeated mechanically. The video provides the idea; the engine needs explicit
gates.

## Local persisted comparison snapshot
As of March 8, 2026, based on the local dashboard data in
`dashboard/public/data/strategies.json`:

- `openclaw_put_credit_spread|legacy_replica`: total return 299.52%, Sharpe
  6.20, max drawdown 0.19%, OOS return 10.94%, OOS Sharpe 3.96, pass.
- `openclaw_put_credit_spread|pcs_vix_optimal`: total return 125.80%, Sharpe
  3.48, max drawdown 2.20%, OOS return 9.51%, OOS Sharpe 3.23, pass.
- `openclaw_put_credit_spread|qqq_falling_knife`: total return 3.63%, Sharpe
  -10.52, max drawdown 0.14%, OOS return 0.40%, OOS Sharpe -6.40, fail.

The comparison is blunt: the new variant is much more selective and much less
productive than the established PCS profiles in this project.

## What the new variant does well
It is not useless. The local run shows three things that are still valuable:

1. It translates the trade idea into a reproducible rule set.
2. It keeps drawdown extremely small.
3. It avoids forcing trades when the setup does not appear.

Those are meaningful research traits. They just are not enough to make the
variant competitive with the current PCS leaders.

## Why it underperformed
Several constraints stack in the same direction:

- QQQ only instead of SPY plus QQQ
- one narrow setup type instead of a broader bullish regime engine
- far-OTM spread geometry, which limits per-trade payout
- sparse event frequency, which limits compounding

There is also an important measurement caveat. The realized trade set is all
winners in the current 2020-2025 run, yet the daily-equity Sharpe is strongly
negative. That likely reflects the engine's mark-to-market path between entry
and exit on a sparse, step-like equity curve rather than a contradiction in the
closed-trade tally. Even so, the OOS failure still stands. The correct response
is caution, not metric shopping.

## Practical conclusion
The local evidence says this profile is best treated as a documented research
case, not a production candidate. It shows how a compelling discretionary trade
idea can survive translation into code while still losing to simpler, broader
systematic PCS profiles.

If this strategy is worth extending, the next sensible experiments are:

1. Allow layered entries across multi-day selloffs instead of a single active
   spread.
2. Replace the fixed OTM proxy with actual option-chain delta or POP selection.
3. Add a bounce-confirmation branch so the engine can compare "catch the knife"
   versus "wait for stabilization" directly.
