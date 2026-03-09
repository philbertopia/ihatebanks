---
slug: regime-credit-spread-balanced
title: Regime Credit Spread Balanced Explainer
summary: >-
  A local explainer for the balanced regime-switch credit spread profile that
  rotates between bullish put spreads and bearish or neutral call spreads.
published_at: '2026-03-08'
updated_at: '2026-03-08'
author: I Hate Banks Editorial Team
tags:
  - strategy-explainer
  - options
  - regime-analysis
level: intermediate
estimated_minutes: 13
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      Practical context for structuring defined-risk credit spreads and managing
      premium-selling trades through changing market tone.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Exchange-level education on spread mechanics, assignment risk, and the
      payoff profile of vertical credit structures.
  - title: CME - Equity Index Volatility Basics
    url: 'https://www.cmegroup.com/education/courses/introduction-to-volatility.html'
    source: article
    why_it_matters: >-
      Useful background for understanding why regime filters and volatility
      conditions affect premium quality and stop behavior.
disclaimer_required: true
strategy_key: openclaw_regime_credit_spread|regime_balanced
setup_rules:
  - Restrict the universe to SPY and QQQ and wait until 20, 50, and 200 day moving averages are available.
  - Keep at most one open position per symbol and respect macro-event blocks plus the trade-based kill switch.
  - In bullish regimes use the legacy PCS template; in bearish or neutral regimes use the CCS baseline template.
entry_logic:
  - Classify bull when price is above the 200 day average and the 20 day average is above the 50 day average.
  - Classify bear when price is below the 200 day average and the 20 day average is below the 50 day average; all other known states are neutral.
  - Enter put credit spreads in bull regimes and call credit spreads in bear or neutral regimes, subject to the active profile's volatility band and call overextension guard.
exit_logic:
  - Take profit only after the minimum hold period once the spread has captured the target share of initial credit.
  - Exit on stop loss, long-strike breach, force-close DTE, or expiry.
  - Mark positions daily with intrinsic value plus time, volatility, and adverse-move penalties instead of using a flat decay rule.
risk_profile:
  - The profile reduces single-side exposure by rotating between short puts and short calls, but it still sells convexity.
  - Neutral markets default to call spreads, so sharp upside reversals during choppy periods can still hurt.
  - SPY and QQQ are highly correlated, so diversification is limited even when the direction changes.
common_failure_modes:
  - Regime flips arriving after the moving-average filter has already lagged the move.
  - Treating the high win rate as proof that tail loss risk has disappeared.
  - Assuming the published 2020-2025 cache is equivalent to a full multi-cycle history.
---
## How it works
This profile is a router, not a third spread template. It decides whether the
engine should behave like a bullish put-credit-spread system or a bearish
call-credit-spread system, then hands sizing and trade management to those
underlying profiles.

In the current implementation, bullish states route to
`openclaw_put_credit_spread|legacy_replica`. Bearish states route to
`openclaw_call_credit_spread|ccs_baseline`. Neutral states also route to the
baseline call-spread profile so the engine does not sit idle every time the
market loses a clean trend.

## What to watch
- Neutral-state call entries are intentional, but they make the strategy more
  active in sideways tape than a pure bear-only call spread engine.
- Call entries are blocked if the underlying is already too extended above the
  50 day average, which helps avoid selling calls after an overcooked squeeze.
- The mark model still uses daily underlying and volatility proxies, so results
  should be interpreted as research-grade spread simulation, not live fill
  evidence.

## Use with site data
As of March 8, 2026, the persisted local dashboard run for
`openclaw_regime_credit_spread|regime_balanced` covers January 2, 2020 through
December 31, 2025 and shows a passing walk-forward result. Use the Strategies,
Backtest, and Walk-Forward pages together: the explainer tells you what the
engine is trying to do, while the data pages show whether it actually held up.
