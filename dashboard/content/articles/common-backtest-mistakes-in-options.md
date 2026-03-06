---
slug: common-backtest-mistakes-in-options
title: Common backtest mistakes in options
summary: >-
  A field guide to the most frequent modeling errors in options backtests and
  concrete controls that reduce false confidence.
published_at: '2026-03-06'
updated_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - article
  - backtesting
  - model-risk
  - options
  - data-quality
level: intermediate
estimated_minutes: 14
references:
  - title: Quantopian lecture series - backtesting pitfalls
    url: 'https://www.youtube.com/results?search_query=backtesting+pitfalls+quant'
    source: youtube
    why_it_matters: >-
      Practical overview of lookahead bias, survivorship bias, and slippage
      underestimation.
  - title: SEC Investor Bulletin - Trading Risks
    url: 'https://www.sec.gov/oiea/investor-alerts-and-bulletins'
    source: article
    why_it_matters: >-
      Investor-protection framing for why model error can translate quickly into
      real capital loss.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Options-specific context for moneyness, assignment, and spread behavior
      that is frequently simplified away in naive models.
disclaimer_required: true
thesis: >-
  Most poor live outcomes come from modeling shortcuts, not from a lack of
  strategy ideas; rigorous backtest hygiene is the first risk control.
related_strategies:
  - stock_replacement|full_filter_20pos
  - intraday_open_close_options|baseline
  - stock_replacement|full_filter_iv_rs
---
## Why options backtests are easy to break
Options research has more moving parts than spot-equity backtests: strike and
expiry selection, implied volatility assumptions, spread behavior, assignment,
and liquidity filters. Every simplification can bias results if not documented
and stress-tested.

The danger is subtle. A model can look mathematically clean, produce elegant
charts, and still be operationally invalid because one hidden assumption was
too optimistic.

## As-of data context from this project
As of 2026-03-06, based on `dashboard/public/data/strategies.json`:

- `stock_replacement|full_filter_20pos`: return 323.82%, Sharpe 0.65, max DD
  56.38%, OOS Sharpe -0.43, fail.
- `stock_replacement|full_filter_iv_rs`: return 320.51%, Sharpe 0.68, max DD
  40.77%, OOS Sharpe -0.46, fail.
- `intraday_open_close_options|baseline`: return 6496.89%, Sharpe 2.51, max DD
  21.55%, OOS Sharpe -1.56, fail.

These results are valuable for research but also show why validation and model
quality checks must be central, not optional.

## The seven highest-impact mistakes
1. **Lookahead leakage**: using information not available at decision time.
2. **Survivorship bias**: excluding delisted or failed names.
3. **Liquidity fantasy**: assuming fills where open interest/spread quality is
   insufficient.
4. **Midpoint overuse**: treating midpoint as executable during stress.
5. **No assignment modeling**: ignoring early assignment or expiry assignment
   path implications.
6. **Parameter overfit**: optimizing until noise looks like signal.
7. **Static volatility assumptions**: not adapting pricing assumptions to regime.

Any one of these can materially inflate expected returns.

## How to convert mistakes into controls
For each risk, define a control:

- Leakage -> strict feature timestamping and audit logs.
- Survivorship -> universe reconstruction with historical membership.
- Liquidity fantasy -> minimum open interest and spread filters.
- Midpoint bias -> conservative fill model + scenario slippage.
- Assignment blind spots -> explicit assignment state transitions.
- Overfit -> walk-forward validation and parameter simplicity.
- Volatility mismatch -> regime-aware assumptions and rejection counts.

A backtest should read like a controlled experiment, not a story.

## Failure modes after deployment
Poor backtest hygiene usually appears live as:

- lower win rates than expected,
- stop losses hit more often than model implied,
- larger realized drawdowns than historical profile,
- unstable behavior around event windows.

When these appear, the right response is not immediate parameter tuning. First
audit assumptions and data paths.

## Practical audit checklist
Before promoting any strategy:

1. Reproduce the same result from raw inputs twice.
2. Run ablation tests: remove one key filter at a time and inspect stability.
3. Compare optimistic vs conservative execution assumptions.
4. Enforce OOS gate before any production notional.
5. Document all assumptions as explicit constraints.

Research quality is not measured by how impressive the chart looks. It is
measured by how well the model survives contact with live conditions.
