---
slug: qqq-falling-knife-pcs
title: QQQ Falling Knife PCS Explainer
summary: >-
  A local explainer for the QQQ-only falling-knife put credit spread profile,
  built as a daily-rule proxy of a high-probability income trade idea.
published_at: '2026-03-08'
updated_at: '2026-03-08'
author: I Hate Banks Editorial Team
tags:
  - strategy-explainer
  - options
  - qqq
  - premium-selling
level: intermediate
estimated_minutes: 12
references:
  - title: tastylive QQQ falling knife trade example
    url: 'https://www.youtube.com/watch?v=eKhFqFsIVww'
    source: youtube
    why_it_matters: >-
      This is the trade idea being approximated locally as a rules-based,
      backtestable research variant.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Background on vertical spread mechanics, defined-risk structures, and
      management tradeoffs for short premium strategies.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Useful definitions for probability-style income trades, strike selection,
      and vertical spread risk language.
disclaimer_required: true
strategy_key: openclaw_put_credit_spread|qqq_falling_knife
setup_rules:
  - Restrict the engine to QQQ and treat the dashboard universe profile as irrelevant for actual trade selection.
  - Require price above the 200 day average, but do not require the 20 day average to stay above the 50 day average.
  - Use elevated but non-panic volatility and only allow entries after an objective downside shock.
entry_logic:
  - Require RSI(14) <= 45.
  - Require either a 1 day return of -1.0% or worse, or a 3 day return of -2.0% or worse.
  - Require QQQ to sit at least 2.0% below its prior 20 day high before opening the spread.
  - Sell the short put about 6.0% OTM, buy the long put 4.0% of price lower, and target credit near 18% of spread width.
exit_logic:
  - Take profit at 50% of initial credit after at least 2 holding days.
  - Exit on a 1.9x credit stop, a long-strike breach, or a 7 DTE time exit.
  - Mark the spread daily with intrinsic value plus time, volatility, and adverse-move penalties.
risk_profile:
  - This is intentionally low throughput and defined risk, so absolute return is capped unless the engine is allowed to layer positions.
  - QQQ concentration means the strategy is highly exposed to one index and one style of selloff behavior.
  - The 90% POP idea is approximated here by fixed OTM distance and spread width, not by live option-chain delta.
common_failure_modes:
  - Mistaking a video-inspired proxy for an exact reconstruction of the original trade.
  - Overreading the 100% win rate when the sample size is only a few dozen trades.
  - Ignoring the negative out-of-sample Sharpe just because drawdown stayed small.
---
## How it works
This profile is a local research proxy of a specific trade idea, not a
tick-accurate replay of the original video. The engine waits for QQQ to remain
above its 200 day average, then looks for a short-term downside shock: weak
RSI, a sharp 1 day or 3 day drop, and a measurable pullback from the recent
high.

When those conditions line up, the strategy sells a far-OTM put credit spread
intended to resemble a high-probability income trade that is trying to monetize
panic premium without taking undefined downside risk.

## What to watch
- The traded universe is `QQQ` only, even if the dashboard run was launched
  with a broader profile selected elsewhere.
- The local 2020-2025 persisted run produced only 24 closed trades, so this is
  a sparse strategy by design.
- As of March 8, 2026, the local dashboard data shows positive return and very
  low drawdown, but walk-forward validation still fails because average OOS
  Sharpe is strongly negative.

## Use with site data
Pair this explainer with the Strategies and Walk-Forward pages. In the local
persisted dataset, `openclaw_put_credit_spread|qqq_falling_knife` shows:

- Total return: 3.63%
- Max drawdown: 0.14%
- Total trades: 24
- OOS average return: 0.40%
- OOS average Sharpe: -6.40
- Validation status: fail
