---
slug: regime-credit-spread-pair-sweep-wave2-crypto-satellites
title: Regime credit spread pair sweep wave 2 crypto and satellites
summary: >-
  Research-only short-window comparison for bitcoin ETF and QQQ-linked
  single-name satellite pairs around the current regime-credit core.
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
  - title: Bitcoin U.S. ETF Index Options | Cboe
    url: 'https://www.cboe.com/tradable-products/cryptocurrency/bitcoin-etf-index-options/'
    source: docs
    why_it_matters: >-
      Useful current reference for crypto-beta research through ETF-style
      structures rather than defaulting immediately to single high-gap names.
  - title: Invesco QQQ Portfolio Plus Index Brochure
    url: 'https://www.invesco.com/content/dam/invesco/indexing/en/documents/Invesco-QQQ-Portfolio-Plus-Index-Brochure.pdf'
    source: docs
    why_it_matters: >-
      Useful reference for why QQQ-linked satellites like MSFT and NVDA are the
      most coherent first single-name pair tests.
  - title: Option Alpha channel
    url: 'https://www.youtube.com/@OptionAlpha'
    source: youtube
    why_it_matters: >-
      Useful practical context for comparing ETF and single-name spread
      behavior across different correlated underlyings without assuming the
      shorter satellite window proves more than it does.
disclaimer_required: true
thesis: >-
  The shorter crypto and single-name satellite cohort produced useful ranking
  hints but not normal validation evidence, because the shared history only
  starts in January 2024 and is too short for the standard walk-forward
  schedule.
related_strategies:
  - openclaw_regime_credit_spread|regime_legacy_defensive
  - openclaw_regime_credit_spread|regime_balanced
---
## Test design
This cohort kept the same regime-credit routing but changed the traded pair:

- bull regime -> `legacy_replica`
- bear or neutral regime -> `ccs_defensive`

Pairs tested:

- `SPY + QQQ` short-window baseline
- `SPY + IBIT`
- `QQQ + IBIT`
- `GLD + IBIT`
- `QQQ + MSFT`
- `QQQ + NVDA`
- `QQQ + TSLA`

The requested range was `2020-01-02` through `2025-12-31`, but the first shared
valid date across all required symbols was `2024-01-11`. That pushed the actual
comparison window to `2024-01-11` through `2025-12-31`.

## Ranked total-return results
- `SPY + QQQ (Short Window)`: `+60.02%`, Sharpe `4.56`, max drawdown `3.13%`
- `QQQ + MSFT`: `+58.18%`, Sharpe `4.39`, max drawdown `2.35%`
- `QQQ + NVDA`: `+38.35%`, Sharpe `3.60`, max drawdown `2.25%`
- `QQQ + IBIT`: `+36.95%`, Sharpe `3.34`, max drawdown `2.80%`
- `QQQ + TSLA`: `+36.61%`, Sharpe `2.39`, max drawdown `2.84%`
- `SPY + IBIT`: `+30.99%`, Sharpe `2.93`, max drawdown `1.56%`
- `GLD + IBIT`: `+24.68%`, Sharpe `2.77`, max drawdown `1.39%`

## Why every row shows walk-forward fail
This is a real data limitation, not a hidden strategy bug.

The standard research schedule for this project is `504 / 126 / 126`. The
shared window in this cohort is not long enough to produce a meaningful set of
normal walk-forward windows, so the OOS summary fields stay effectively empty
and every row reads as validation fail.

That means this cohort is exploratory. It is useful for ranking satellites and
crypto-beta ideas, but it is not yet a basis for promotion.

## What still matters from the short window
Even without normal walk-forward validation, the cohort still taught three
useful things.

First, `QQQ + MSFT` is the best single-name satellite so far. It nearly matched
the short-window `SPY + QQQ` baseline and materially outperformed the other
single-name tests.

Second, `QQQ + NVDA` is the second single-name satellite worth keeping in the
queue. It did not beat `QQQ + MSFT`, but it stayed ahead of the crypto-beta
pairings.

Third, `QQQ + IBIT` is the best crypto-beta pair in this cohort. It outperformed
`SPY + IBIT` and `GLD + IBIT`, which makes it the logical crypto follow-up if
the research stays with ETF-style structures.

## What not to conclude
Do not read this cohort as saying:

- `QQQ + MSFT` is already a validated replacement for `SPY + QQQ`
- `IBIT` pairings are production-ready
- `GLD + IBIT` is a stable hedge-like pair

The history is too short for that. This wave is a queue-shaping exercise, not a
promotion exercise.

## Practical conclusion
The correct next interpretation is:

1. `QQQ + MSFT` is the first single-name satellite worth deeper follow-up
2. `QQQ + NVDA` is second
3. `QQQ + IBIT` is the best crypto-beta pair so far
4. `SPY + IBIT` and `GLD + IBIT` stay in the research pool but not at the front

That is enough to guide the next experiments without pretending this shorter
window proved more than it did.
