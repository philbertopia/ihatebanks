---
slug: benchmarking-options-strategies-correctly
title: Benchmarking options strategies correctly
summary: >-
  A practical framework for comparing options systems without mixing unlike risk
  profiles, turnover, and capital constraints.
published_at: '2026-03-06'
updated_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - article
  - benchmarking
  - performance
  - options
  - portfolio-construction
level: intermediate
estimated_minutes: 12
references:
  - title: Aswath Damodaran - Risk and Return lectures
    url: 'https://www.youtube.com/@AswathDamodaranonValuation'
    source: youtube
    why_it_matters: >-
      Strong foundation on comparable risk-adjusted return measurement and
      pitfalls in cross-strategy comparison.
  - title: CFA Institute - Performance Measurement
    url: 'https://www.cfainstitute.org/en/membership/professional-development/refresher-readings/performance-evaluation'
    source: article
    why_it_matters: >-
      Institutional framing of return attribution, drawdown context, and
      consistency metrics.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Connects benchmark design to options-specific payoff asymmetry and risk
      structure.
disclaimer_required: true
thesis: >-
  Benchmarking is only valid when return, drawdown, turnover, and validation
  status are compared under consistent assumptions.
related_strategies:
  - openclaw_put_credit_spread|pcs_vix_optimal
  - stock_replacement|full_filter_iv_rank
  - openclaw_put_credit_spread|legacy_replica
---
## Why most strategy comparisons are wrong
Many dashboards compare strategies on a single column: total return. That is
useful for ranking excitement, not for ranking deployability. Options strategies
can have radically different tail risk, trade frequency, margin behavior, and
execution sensitivity. Comparing them on one number is statistically weak and
operationally dangerous.

A valid benchmark should answer: given similar assumptions and risk budgets,
which approach delivered better risk-adjusted and validation-consistent results?

## As-of snapshot and what it shows
As of 2026-03-06, based on `dashboard/public/data/strategies.json`:

- `openclaw_put_credit_spread|pcs_vix_optimal`: return 125.80%, Sharpe 3.48,
  max DD 2.20%, OOS Sharpe 3.23, pass.
- `stock_replacement|full_filter_iv_rank`: return 302.72%, Sharpe 0.70, max DD
  41.44%, OOS Sharpe -0.36, fail.
- `openclaw_put_credit_spread|legacy_replica`: return 299.52%, Sharpe 6.20, max
  DD 0.19%, OOS Sharpe 3.96, pass.

This is a good example of why ranking by return alone can reverse conclusions.

## A robust benchmark stack
Use a stack, not one metric:

1. **Validation layer**: OOS pass/fail and OOS Sharpe.
2. **Risk layer**: max drawdown and drawdown duration.
3. **Efficiency layer**: Sharpe and profit factor.
4. **Outcome layer**: total return and win rate.
5. **Operational layer**: turnover and execution assumptions.

A strategy that loses at layer 1 should not win the final benchmark no matter
how strong layer 5 appears.

## Strategy evidence and caveats
In the current dataset, stock replacement variants can produce high in-sample
returns, but several fail OOS and carry materially higher drawdown. That may be
acceptable for research exploration or specific mandates, but not for a mandate
that prioritizes robustness and lower path volatility.

Conversely, premium-selling variants with lower absolute return in some cases
may offer stronger consistency and lower drawdown burden. That can be more
valuable depending on investor objectives and behavior constraints.

No benchmark is universal. The benchmark must match the decision context.

## Failure modes in benchmarking practice
- **Mixing horizons**: comparing short-window and long-window runs as equals.
- **Ignoring assumptions mode**: comparing optimistic and realistic fills without
  normalization.
- **Cherry-picking periods**: selecting windows that flatter one strategy class.
- **Neglecting OOS data**: treating in-sample fit as sufficient evidence.

These errors make benchmark outcomes look precise while actually being unstable.

## Practical benchmarking checklist
1. Define objective: growth, smoothness, or robustness-first.
2. Normalize assumptions and date ranges.
3. Apply hard gating on OOS status.
4. Rank on a weighted scorecard, not one metric.
5. Re-run benchmark quarterly and document ranking drift.

Benchmarking is not about finding the highest number. It is about making
tradeoffs explicit so deployment decisions remain defensible.
