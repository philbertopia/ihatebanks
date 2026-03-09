---
slug: regime-credit-spread-pair-sweep-wave1-etf-expansion
title: Regime credit spread pair sweep wave 1 ETF expansion
summary: >-
  Research-only ETF cohort comparison for the current regime-credit core across
  SPY, QQQ, IWM, SMH, RSP, HYG, and XLE pairings over the full synthetic
  2020-2025 window.
published_at: '2026-03-09'
updated_at: '2026-03-09'
author: I Hate Banks Editorial Team
tags:
  - article
  - backtesting
  - regime-analysis
  - options
  - research
level: intermediate
estimated_minutes: 9
references:
  - title: Cash Settled FLEX ETFs | Cboe
    url: 'https://www.cboe.com/tradable_products/equity_indices/flex_options/cash_settled_etfs'
    source: docs
    why_it_matters: >-
      Useful current source for ETF option coverage across IWM, SMH, RSP, HYG,
      and XLE when expanding the pair-research queue.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Helpful background on defined-risk credit spreads and why pair selection
      changes return, trade density, and drawdown behavior even when the spread
      template stays the same.
  - title: Option Alpha channel
    url: 'https://www.youtube.com/@OptionAlpha'
    source: youtube
    why_it_matters: >-
      Useful practical context for comparing ETF credit-spread behavior across
      different correlated underlyings instead of assuming every pair should be
      managed the same way.
disclaimer_required: true
thesis: >-
  The first serious ETF expansion confirmed that the current SPY and QQQ
  baseline still leads, but it also made the next research queue clearer:
  QQQ plus IWM remains the best runner-up, and QQQ plus SMH is the strongest
  new aggressive ETF pair.
related_strategies:
  - openclaw_regime_credit_spread|regime_legacy_defensive
  - openclaw_regime_credit_spread|regime_balanced
---
## Test design
This pass did not change the core spread engine.

- bull regime -> `legacy_replica`
- bear or neutral regime -> `ccs_defensive`

It only changed the traded pair, using the same synthetic adjusted-close
research methodology across the full `2020-01-02` through `2025-12-31` window.

Pairs tested:

- `SPY + QQQ`
- `QQQ + IWM`
- `QQQ + SMH`
- `SPY + RSP`
- `SPY + HYG`
- `SPY + XLE`

## Ranked results
- `SPY + QQQ`: `+189.41%` total return, `5.32` Sharpe, `1.50%` max drawdown,
  `+17.38%` OOS return, `7.29` OOS Sharpe, `1.14%` OOS max drawdown, pass
- `QQQ + IWM`: `+166.99%` total return, `5.25` Sharpe, `1.79%` max drawdown,
  `+14.26%` OOS return, `6.83` OOS Sharpe, `1.26%` OOS max drawdown, pass
- `QQQ + SMH`: `+146.39%` total return, `4.23` Sharpe, `2.17%` max drawdown,
  `+12.75%` OOS return, `5.49` OOS Sharpe, `1.48%` OOS max drawdown, pass
- `SPY + RSP`: `+128.58%` total return, `4.33` Sharpe, `0.83%` max drawdown,
  `+10.75%` OOS return, `5.19` OOS Sharpe, `0.54%` OOS max drawdown, pass
- `SPY + XLE`: `+106.36%` total return, `3.88` Sharpe, `0.88%` max drawdown,
  `+9.99%` OOS return, `5.15` OOS Sharpe, `0.58%` OOS max drawdown, pass
- `SPY + HYG`: `+88.81%` total return, `3.18` Sharpe, `1.04%` max drawdown,
  `+8.48%` OOS return, `4.09` OOS Sharpe, `0.51%` OOS max drawdown, pass

## What matters
Three things matter from this cohort.

First, the current baseline still won. That means the existing `SPY + QQQ`
core is not winning by accident or only because it was tested first.

Second, `QQQ + IWM` remains the strongest runner-up. It lost return versus the
baseline, but not enough to dismiss it. If the goal is to keep searching for a
more profitable or more diversified second pair without abandoning broad-beta
behavior, this is still the first place to look.

Third, `QQQ + SMH` is now the best concentrated technology extension. It trails
`QQQ + IWM` on total return and OOS performance, but it is clearly stronger
than the credit-risk and commodity-cycle companions in pure profit terms.

## How to read the other ETF pairs
- `SPY + RSP` is the cleanest breadth-sensitive alternative. It did not beat
  the baseline, but it kept drawdown extremely low.
- `SPY + XLE` is the better inflation-cycle companion than `SPY + HYG` if the
  priority is total return.
- `SPY + HYG` is useful mostly as a stability reference. It is not a profit
  leader.

## Practical conclusion
If the research queue stays disciplined, the order after this wave should be:

1. keep `SPY + QQQ` as the production benchmark
2. keep `QQQ + IWM` as the top ETF challenger
3. keep `QQQ + SMH` as the next aggressive ETF research pair
4. use `SPY + RSP` as the main breadth-control comparison

That is a much narrower and more useful result than simply saying "test more
correlated ETFs."
