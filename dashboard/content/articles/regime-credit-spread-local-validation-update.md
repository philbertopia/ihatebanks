---
slug: regime-credit-spread-local-validation-update
title: Regime credit spread local validation update
summary: >-
  Local workspace documentation for the regime-switch credit spread family,
  including the current persisted 2020-2025 leaders and the link to the
  separate 10-year research comparison.
published_at: '2026-03-08'
updated_at: '2026-03-09'
author: I Hate Banks Editorial Team
tags:
  - article
  - backtesting
  - regime-analysis
  - validation
  - options
level: intermediate
estimated_minutes: 15
references:
  - title: Option Alpha channel
    url: 'https://www.youtube.com/@OptionAlpha'
    source: youtube
    why_it_matters: >-
      Practical trade examples for comparing premium-selling profiles across
      changing trend states and volatility environments.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Foundation for understanding defined-risk spread structures and why
      execution assumptions matter when evaluating backtests.
  - title: CME - Equity Index Volatility Basics
    url: 'https://www.cmegroup.com/education/courses/introduction-to-volatility.html'
    source: article
    why_it_matters: >-
      Useful primer for thinking about volatility gating, trend state, and why
      premium quality changes across market regimes.
disclaimer_required: true
thesis: >-
  The regime-switch credit spread family is locally ready for review because
  multiple variants now pass the persisted 2020-2025 walk-forward process, but
  the 10-year extension should stay in a separate research track until the
  longer data source is integrated into the main pipeline.
related_strategies:
  - openclaw_regime_credit_spread|regime_legacy_defensive
  - openclaw_regime_credit_spread|regime_balanced
  - openclaw_regime_credit_spread|regime_defensive
  - openclaw_regime_credit_spread|regime_vix_baseline
---
## What was added locally
As of March 8, 2026, the local workspace includes a new strategy family:
`openclaw_regime_credit_spread`.

It no longer has just the original two variants. The family now includes six
locally documented modes, with `regime_legacy_defensive` currently acting as
the strongest local candidate in both the persisted `2020-2025` dataset and the
separate 10-year research sweep.

- `regime_legacy_defensive`
- `regime_balanced`
- `regime_defensive`
- `regime_vix_baseline`
- `regime_legacy_defensive_bear_only`
- `regime_vix_baseline_bear_only`

This is a regime router built on top of profiles that already existed in the
project. That matters because the question is not whether a brand-new idea can
be curve fit into one good result. The question is whether combining already
credible spread templates produces a more robust multi-state engine.

## Persisted dashboard results: January 2, 2020 to December 31, 2025
These are the local persisted results exported into the dashboard data files:

- `openclaw_regime_credit_spread|regime_legacy_defensive`: total return
  189.41%, Sharpe 5.32, max drawdown 1.50%, OOS average return 17.38%, OOS
  Sharpe 7.29, OOS max drawdown 1.14%, walk-forward pass.
- `openclaw_regime_credit_spread|regime_balanced`: total return 182.58%, Sharpe
  4.61, max drawdown 1.51%, OOS average return 16.58%, OOS Sharpe 5.93, OOS max
  drawdown 1.50%, walk-forward pass.
- `openclaw_regime_credit_spread|regime_defensive`: total return 175.08%,
  Sharpe 4.93, max drawdown 1.56%, OOS average return 15.94%, OOS Sharpe 6.55,
  OOS max drawdown 1.17%, walk-forward pass.

Those are strong local results. They are also the numbers that now back the
dashboard dataset in this workspace, so the strategy pages and validation views
are internally consistent.

## Research-only 10-year extension
The longer `2016-2025` comparison now lives in the separate local research
layer. Start with the broader
[Credit spread 10-year research coverage](/education/articles/credit-spread-10-year-research-coverage)
note, then drill into the
[Regime credit spread 10-year comparison](/education/articles/regime-credit-spread-10-year-comparison)
if you want the family-specific breakdown.

That split is intentional. The scripted 10-year run fills the real SPY and QQQ
price-history gap in the cache and is therefore useful for research, but it is
not the same as promoting that longer source into the official dashboard
pipeline.

## Portfolio architecture update
There is now a separate research comparison for portfolio overlays around the
current winner:
[Regime portfolio upgrade comparison](/education/articles/regime-portfolio-upgrade-comparison).

That overlay pass did not replace the current core. The plain
`regime_legacy_defensive` sleeve remained the preferred local portfolio setup.
The drawdown throttle never engaged in the tested window, and the volatility
kill-switch gave up more return than the tiny drawdown improvement justified.

## Pair sweep update
There is now a pair-research hub for this same core template:
[Regime credit spread pair research hub](/education/articles/regime-credit-spread-universe-sweep).

That hub now links three related passes:

1. the original six-pair sweep
2. the [Wave 1 ETF expansion pair sweep](/education/articles/regime-credit-spread-pair-sweep-wave1-etf-expansion)
3. the [Wave 2 crypto and satellite pair sweep](/education/articles/regime-credit-spread-pair-sweep-wave2-crypto-satellites)

The long-history ETF result stayed consistent with the earlier finding: `SPY +
QQQ` remained the best pair, while `QQQ + IWM` stayed the strongest
non-baseline challenger and `QQQ + SMH` became the strongest new aggressive ETF
pair. The shorter satellite cohort was useful for queue-shaping, but it did not
have enough shared history to support normal walk-forward validation.

## What this means for review
The current local leader is `regime_legacy_defensive`. It now has the best
persisted `2020-2025` OOS return and OOS Sharpe inside the family, while the
separate 10-year comparison also keeps it on top.

`regime_balanced` is still a credible comparison point. `regime_defensive` is
still useful diagnostically, but it should no longer be read as the main
headline candidate because its 10-year trade density is too low to trust as a
production-style winner.

## Recommended local review sequence
If you want to inspect the workspace before anything goes to GitHub, use this
order:

1. Review the Strategies page and Walk-Forward page for the persisted `2020-2025`
   results that are now exported into local dashboard data.
2. Open the strategy explainer for `regime_legacy_defensive` to confirm the
   routing logic matches the engine implementation.
3. Read the pair-research hub and the ETF follow-up article to see which
   correlated pairs are closest to the current baseline.
4. Read the separate 10-year comparison note as supporting research, not as a
   replacement for the official local dataset.

That separation keeps the local site honest: official dashboard metrics come
from the normal project dataset, while the longer-history experiment remains
visible but clearly labeled as exploratory.
