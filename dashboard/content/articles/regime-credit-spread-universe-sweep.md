---
slug: regime-credit-spread-universe-sweep
title: Regime credit spread pair research hub
summary: >-
  Research-only hub for the correlated-pair sweeps around the current regime
  credit spread champion, including the original six-pair baseline study, the
  second-wave ETF expansion, and the shorter crypto plus single-name satellite
  comparison.
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
estimated_minutes: 10
references:
  - title: Cash Settled FLEX ETFs | Cboe
    url: 'https://www.cboe.com/tradable_products/equity_indices/flex_options/cash_settled_etfs'
    source: docs
    why_it_matters: >-
      Useful current source for ETF option coverage across symbols such as GLD,
      HYG, IBIT, IWM, RSP, SMH, TLT, and XLE when building the next correlated
      pair queue.
  - title: Bitcoin U.S. ETF Index Options | Cboe
    url: 'https://www.cboe.com/tradable-products/cryptocurrency/bitcoin-etf-index-options/'
    source: docs
    why_it_matters: >-
      Helpful current reference for treating crypto beta through ETF or
      index-like structures instead of defaulting straight to high-gap single
      names.
  - title: Invesco QQQ Portfolio Plus Index Brochure
    url: 'https://www.invesco.com/content/dam/invesco/indexing/en/documents/Invesco-QQQ-Portfolio-Plus-Index-Brochure.pdf'
    source: docs
    why_it_matters: >-
      Useful reference for why QQQ-linked satellites like MSFT and NVDA are
      more coherent first single-name tests than lower-weight or more
      idiosyncratic names.
  - title: Option Alpha channel
    url: 'https://www.youtube.com/@OptionAlpha'
    source: youtube
    why_it_matters: >-
      Useful practical context for comparing ETF credit-spread behavior across
      different correlated underlyings instead of assuming every new pair
      should be promoted equally.
disclaimer_required: true
thesis: >-
  The pair sweeps say something narrower and more useful than "just add more
  correlated assets": the current SPY and QQQ baseline is still the pair to
  beat, the best ETF follow-up is QQQ plus IWM or QQQ plus SMH, and the newer
  crypto and single-name satellites are still exploratory because their shared
  history is too short for the normal walk-forward schedule.
related_strategies:
  - openclaw_regime_credit_spread|regime_legacy_defensive
  - openclaw_regime_credit_spread|regime_balanced
  - openclaw_regime_credit_spread|regime_defensive
---
## What this hub covers
This strategy page now points to one research hub instead of scattering pair
notes across unrelated articles.

All three pair sweeps kept the same spread logic:

- bull regime -> `legacy_replica`
- bear or neutral regime -> `ccs_defensive`

Only the traded pair changed.

## Reading order
If you want the clean sequence, use this order:

1. this hub article
2. [Wave 1 ETF expansion pair sweep](/education/articles/regime-credit-spread-pair-sweep-wave1-etf-expansion)
3. [Wave 2 crypto and satellite pair sweep](/education/articles/regime-credit-spread-pair-sweep-wave2-crypto-satellites)

## First sweep recap
The original six-pair sweep tested:

- `SPY + QQQ`
- `QQQ + IWM`
- `QQQ + GLD`
- `SPY + IWM`
- `SPY + GLD`
- `SPY + TLT`

The result was clear:

- `SPY + QQQ` stayed first
- `QQQ + IWM` became the strongest non-baseline candidate
- the gold and Treasury pairs behaved more like stabilizers than return leaders

That result is why the next queue stayed disciplined. Instead of jumping
straight to leveraged ETFs or highly idiosyncratic names, the second wave moved
first into a broader ETF cohort and then into a shorter-window crypto plus
single-name cohort.

## Second-wave ETF expansion
The long-history ETF expansion held the full synthetic `2020-01-02` to
`2025-12-31` window and tested:

- `SPY + QQQ`
- `QQQ + IWM`
- `QQQ + SMH`
- `SPY + RSP`
- `SPY + HYG`
- `SPY + XLE`

The ranking was:

- `SPY + QQQ`: `+189.41%` total return, `+17.38%` OOS return, `7.29` OOS
  Sharpe, `1.14%` OOS max drawdown
- `QQQ + IWM`: `+166.99%` total return, `+14.26%` OOS return, `6.83` OOS
  Sharpe, `1.26%` OOS max drawdown
- `QQQ + SMH`: `+146.39%` total return, `+12.75%` OOS return, `5.49` OOS
  Sharpe, `1.48%` OOS max drawdown
- `SPY + RSP`: `+128.58%` total return, `+10.75%` OOS return, `5.19` OOS
  Sharpe, `0.54%` OOS max drawdown
- `SPY + XLE`: `+106.36%` total return, `+9.99%` OOS return, `5.15` OOS
  Sharpe, `0.58%` OOS max drawdown
- `SPY + HYG`: `+88.81%` total return, `+8.48%` OOS return, `4.09` OOS
  Sharpe, `0.51%` OOS max drawdown

The important conclusion is not just that `SPY + QQQ` still won. It is that the
best next aggressive ETF pair is now clearer: `QQQ + IWM` remains the strongest
runner-up, and `QQQ + SMH` is now the next concentrated tech pair worth
keeping in the queue.

## Second-wave crypto and satellite cohort
The shorter crypto and satellite cohort used the first shared valid history
across all required symbols, which pushed the actual window to `2024-01-11`
through `2025-12-31`.

That cohort tested:

- `SPY + QQQ` short-window baseline
- `SPY + IBIT`
- `QQQ + IBIT`
- `GLD + IBIT`
- `QQQ + MSFT`
- `QQQ + NVDA`
- `QQQ + TSLA`

The top total-return rows were:

- `SPY + QQQ (Short Window)`: `+60.02%`
- `QQQ + MSFT`: `+58.18%`
- `QQQ + NVDA`: `+38.35%`
- `QQQ + IBIT`: `+36.95%`

Those numbers are informative, but they are not normal walk-forward evidence.
The shared history is too short for the standard `504 / 126 / 126` schedule, so
the cohort should be read as exploratory only.

That means the practical reading is:

- `QQQ + MSFT` is the best first single-name satellite to take seriously
- `QQQ + NVDA` remains worth testing
- `QQQ + IBIT` is the best crypto-beta pair in this shorter cohort
- `GLD + IBIT` did not justify moving gold-plus-bitcoin to the front of the
  queue

## What the full pair research says now
The current pair conclusions are:

- core baseline still best: `SPY + QQQ`
- best non-baseline broad-beta pair: `QQQ + IWM`
- best concentrated tech ETF pair: `QQQ + SMH`
- best breadth-sensitive pair: `SPY + RSP`
- best single-name satellite so far: `QQQ + MSFT`
- best crypto-beta pair so far: `QQQ + IBIT`

That is a much more useful result than simply saying "try more correlated
assets." The pair search now has structure.

## Recommended next queue
If the goal is still to find a more profitable regime-credit portfolio without
breaking the current discipline, the next order should be:

1. keep `SPY + QQQ` as the production benchmark
2. continue testing `QQQ + IWM`
3. keep `QQQ + SMH` in the top ETF queue
4. keep `SPY + RSP` as the breadth-control queue
5. revisit `QQQ + MSFT` first among single-name satellites
6. revisit `QQQ + NVDA` second among single-name satellites
7. keep `QQQ + IBIT` as the leading crypto-beta research pair

What still stays deferred:

- `QQQ + TQQQ`
- `SPY + TQQQ`
- `QQQ + PLTR`
- `QQQ + MSTR`

Those are still better treated as a later high-vol appendix than as the next
mainline research pass.
