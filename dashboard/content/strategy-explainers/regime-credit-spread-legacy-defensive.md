---
slug: regime-credit-spread-legacy-defensive
title: Regime Credit Spread Legacy Defensive Explainer
summary: >-
  A local explainer for the current leading regime-switch credit spread profile,
  which combines the legacy bullish PCS leg with the defensive bearish and
  neutral CCS leg.
published_at: '2026-03-08'
updated_at: '2026-03-09'
author: I Hate Banks Editorial Team
tags:
  - strategy-explainer
  - options
  - regime-analysis
level: intermediate
estimated_minutes: 14
references:
  - title: Option Alpha channel
    url: 'https://www.youtube.com/@OptionAlpha'
    source: youtube
    why_it_matters: >-
      Useful practical context for comparing premium-selling profiles across
      changing market states rather than treating a single spread direction as
      universally correct.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Background on vertical spread structure, profit windows, assignment
      considerations, and the risk behavior of defined-risk credit spreads.
  - title: CME - Equity Index Volatility Basics
    url: 'https://www.cmegroup.com/education/courses/introduction-to-volatility.html'
    source: article
    why_it_matters: >-
      Helpful reference for understanding why bullish, bearish, and neutral
      regimes change premium quality and adverse-move behavior.
disclaimer_required: true
strategy_key: openclaw_regime_credit_spread|regime_legacy_defensive
setup_rules:
  - Restrict the universe to SPY and QQQ and wait until the moving-average and volatility lookbacks are populated.
  - Respect the one-position-per-symbol rule, macro-event blocks, and the trade-based kill switch before opening a new spread.
  - Route bullish regimes to the legacy PCS template and bearish or neutral regimes to the defensive CCS template.
entry_logic:
  - Classify bullish regimes when price is above the 200 day average and the 20 day average is above the 50 day average.
  - Classify bearish regimes when price is below the 200 day average and the 20 day average is below the 50 day average; all other known states are neutral.
  - Enter put credit spreads in bullish regimes through `legacy_replica` and call credit spreads in bearish or neutral regimes through `ccs_defensive`, while blocking call entries that are too extended above the 50 day average.
exit_logic:
  - Take profit only after the minimum hold period once the spread captures the configured share of initial credit.
  - Exit on stop loss, long-strike breach, force-close DTE, or expiry.
  - Mark open positions daily with intrinsic value plus time, volatility, and adverse-move penalties instead of assuming flat decay.
risk_profile:
  - The profile is still a premium-selling engine, so the high win rate does not eliminate convex tail risk.
  - Neutral markets still route to call spreads, which can be painful if a squeeze starts from a sideways tape.
  - The strong 10-year research result is informative, but it remains separate from the official dashboard metrics because the longer source uses a filled SPY and QQQ price history.
common_failure_modes:
  - Treating the high historical win rate as if drawdown risk has disappeared.
  - Forgetting that SPY and QQQ are correlated enough that two positions do not equal broad diversification.
  - Confusing the research-only 10-year extension with the official persisted 2020-2025 dataset shown on the dashboard pages.
---
## How it works
This profile is the most pragmatic version of the regime router so far. On the
bullish side it keeps the stronger `legacy_replica` put-credit-spread behavior,
which has historically produced the best upside inside the PCS family. On the
bearish and neutral side it swaps to `ccs_defensive`, which is slower and more
conservative than the baseline call-spread mode.

That combination matters. The goal is not to make both sides maximally
aggressive. The goal is to keep the stronger bullish engine while softening the
call-spread behavior that tends to be more fragile when the market is choppy or
already stretched.

## What to watch
- Neutral-state call entries are still part of the design, so this is not a
  pure bear-only call-spread engine.
- The profile leads the current local regime family, but that does not mean it
  is immune to correlated ETF shocks or volatility expansion.
- The 10-year research run is encouraging, yet it is still labeled
  research-only because the continuous `2016-2025` history required a filled
  SPY and QQQ cache gap.

## Pair research result
There is now a pair-research hub for this exact profile:
[Regime credit spread pair research hub](/education/articles/regime-credit-spread-universe-sweep).

That hub links three separate passes:

- the original six-pair sweep
- the second-wave ETF expansion
- the shorter crypto and single-name satellite cohort

The current baseline still won the long-history ETF comparisons:

- `SPY + QQQ`: strongest overall return and OOS profile
- `QQQ + IWM`: best non-baseline broad-beta candidate
- `QQQ + SMH`: strongest new aggressive ETF pair

The shorter satellite cohort did not have enough shared history for the normal
walk-forward schedule, but it still identified the next queue:

- `QQQ + MSFT`: best first single-name satellite
- `QQQ + NVDA`: second single-name satellite
- `QQQ + IBIT`: best crypto-beta pair so far

That matters for the strategy page because it says something specific about the
current core: the winning behavior is not just "any correlated pair with the
same engine." The original `SPY + QQQ` combination is still the benchmark to
beat.

## Best next pair tests
The next research queue should stay disciplined.

- Best broad-beta challenger: `QQQ + IWM`
- Best aggressive ETF pair: `QQQ + SMH`
- Best breadth pair: `SPY + RSP`
- Best first single-name satellite: `QQQ + MSFT`
- Best crypto-beta research pair: `QQQ + IBIT`

## Use with site data
As of March 9, 2026, the persisted local dashboard run for
`openclaw_regime_credit_spread|regime_legacy_defensive` covers January 1, 2020
through December 31, 2025 and still shows the strongest OOS profile inside the
local regime family. Pair this explainer with the strategy metrics, the
separate 10-year research note, and the pair-research hub so you can separate:

- the official local persisted dataset
- the 10-year research-only extension
- the research-only pair sweeps
