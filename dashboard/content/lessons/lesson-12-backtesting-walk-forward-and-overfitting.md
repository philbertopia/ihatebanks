---
slug: lesson-12-backtesting-walk-forward-and-overfitting
title: 'Backtesting, walk-forward, and overfitting'
summary: >-
  A backtest that looks great is not enough. Learn how to read backtest results
  honestly, what overfitting is and why it destroys real-world performance,
  and how walk-forward out-of-sample validation is used on this site to test
  whether a strategy's edge is real.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - backtesting
level: advanced
estimated_minutes: 22
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      Practical content on testing options strategies historically and the
      limits of backtests — honest perspective on what simulated results
      can and cannot tell you about live trading.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Explains backtesting methodology, look-ahead bias, survivorship bias,
      and why many published backtests are systematically overstated.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Technical documentation on historical options data quality and the
      specific challenges of backtesting options strategies accurately.
disclaimer_required: true
lesson_number: 12
learning_objectives:
  - Explain what a backtest is and list three specific ways it can overstate real-world performance.
  - Define in-sample and out-of-sample data and explain why the distinction matters.
  - Describe what overfitting is and how walk-forward validation tests whether a strategy is overfit.
  - Interpret the OOS pass/fail validation displayed on each strategy page on this site.
key_takeaways:
  - A backtest simulates how a strategy would have performed on historical data. It is a necessary first step, not proof that the strategy works.
  - Overfitting occurs when a strategy is tuned to perform well on historical data but fails to generalize to new data. It is the most common source of false confidence in systematic trading.
  - Walk-forward out-of-sample (OOS) validation splits the data into training windows (where the strategy is tested) and testing windows (never seen during development).
  - An OOS pass means the strategy maintained its edge on data it had never seen. An OOS fail means the in-sample performance was likely at least partly due to overfitting.
  - No backtest, however rigorous, guarantees future performance. OOS validation reduces the probability of curve-fitting — it does not eliminate the risk.
---

## What a backtest is

A **backtest** applies a trading strategy's rules to historical data to see how it would have performed if it had been run in the past.

The appeal is obvious: instead of risking real money to test whether a strategy works, you can simulate thousands of trades across years of market history in minutes. If the backtest shows strong performance, you have evidence the strategy might be viable.

The danger is equally obvious: historical data is fixed and knowable. It is easy — accidentally or intentionally — to build a strategy that looks great on past data but fails on any new data.

---

## Why backtests overstate real-world performance

### 1. Overfitting (curve fitting)

Overfitting is the most important problem in systematic trading research. It occurs when a strategy's parameters are tuned — consciously or not — to fit the historical data rather than capture a genuine market dynamic.

**Simple example:** Suppose you test 100 different parameter combinations for a strategy. Purely by chance, several will produce impressive backtests. If you select the best-looking one and deploy it, you are likely deploying luck, not skill. The parameters that worked historically have no reason to continue working going forward.

The more parameters a strategy has, the easier it is to overfit. A strategy with 2-3 rules and simple parameters is harder to fit to noise than one with 10-15 rules and many tunable inputs.

### 2. Look-ahead bias

Look-ahead bias occurs when the backtest uses information that would not have been available at the time of the trade. Common examples:
- Using the day's closing price to make a decision "at the open"
- Using implied volatility data that was calculated after the fact
- Filtering out stocks that had already crashed (so the strategy never "touches" them)

Even subtle look-ahead bias can produce dramatically inflated backtest results.

### 3. Execution assumptions

Most simple backtests fill orders at the theoretical midpoint of the bid/ask spread or at the closing price. In reality:
- Market orders fill at the ask (for buys) or bid (for sells)
- Large orders move the market against you (slippage)
- Liquidity is not always available at the theoretical price

The strategies on this site model execution with a slippage adjustment — but imperfect execution modeling remains a source of gap between backtest and live performance.

### 4. Survivorship bias

Historical data sets often include only stocks that survived — companies that went bankrupt or were delisted are missing. A strategy that avoided all delisted companies in backtests may have only appeared to work because it was tested on survivable companies.

The strategies here trade large-cap liquid equities with monthly options — a universe that minimizes but does not eliminate survivorship bias.

---

## In-sample vs. out-of-sample data

**In-sample (IS) data** is the historical data used to develop and test the strategy. If you build a strategy, tweak its parameters, and check how it performs on the same data you used to build it — that is in-sample testing.

**Out-of-sample (OOS) data** is data the strategy has never seen during development. If you develop a strategy on 2015-2020 data and test it on 2021-2025 data — the 2021-2025 performance is OOS.

A strong in-sample backtest with weak OOS performance is a clear sign of overfitting. A strategy that performs consistently both in-sample and out-of-sample is far more credible.

---

## Walk-forward validation

**Walk-forward validation** is a rigorous method for generating OOS results that uses all available data, not just a single held-out period.

The approach:
1. Divide the total historical period into overlapping windows
2. For each window: use the first portion for in-sample development, use the remaining portion for OOS testing
3. Roll the window forward by a fixed amount and repeat
4. Aggregate all OOS periods into a single OOS return stream

The result: a strategy tested on data it has never seen, across multiple market conditions, without any single test period being too short to be statistically meaningful.

---

## How walk-forward validation works on this site

The strategies here use the following walk-forward setup:

- **Training window:** 504 trading days (~2 years)
- **Testing window:** 126 trading days (~6 months)
- **Total windows:** 7 non-overlapping periods across the 5-year history

For each window, the strategy runs exactly as configured — no parameter changes, no look-ahead. The OOS results from all 7 windows are aggregated.

**Validation criteria** (family-adjusted):
- **Credit spread strategies (PCS/CCS):** OOS Sharpe ≥ 0.70, max drawdown ≤ 30%
- **Wheel strategies:** OOS Sharpe ≥ 0.40, max drawdown ≤ 35%
- **Stock replacement:** OOS Sharpe ≥ 0.30, max drawdown ≤ 35%

Different strategy families use different thresholds because their expected Sharpe ratios differ structurally. Applying a single threshold across all strategy types would systematically fail lower-Sharpe strategies that are nonetheless viable.

---

## How to interpret OOS pass/fail on this site

When you see **OOS Validated** on a strategy page, it means:
- The strategy passed the walk-forward test across 7 non-overlapping OOS windows
- Its average OOS Sharpe ratio exceeded the family threshold
- Its average OOS max drawdown stayed within the family limit
- The in-sample performance was not obviously due to overfitting

When you see **Not Validated**:
- The strategy's OOS performance fell below one or both thresholds
- The in-sample results may not generalize to new data
- Further development or parameter review is needed before deployment

**Important:** An OOS pass is a necessary condition for confidence, not a sufficient one. The thresholds are calibrated conservatively, and past OOS performance is still historical. No test can guarantee future results.

---

## What OOS validation cannot tell you

- **Regime change:** The walk-forward tests cover 2020-2025. A fundamental change in market structure — new regulatory frameworks, new market participants, structural shifts in volatility — can break strategies that passed OOS validation.
- **Transaction cost changes:** If bid/ask spreads widen significantly or commissions change, strategies with thin margins may stop working.
- **Correlation spikes:** OOS tests show how the strategy handled the regimes it saw. An unprecedented market event (a regime not represented in the test period) is outside the OOS evidence.

The honest statement is: OOS validation makes a backtest *more credible*, not *reliable*. It significantly reduces the probability that you are deploying a curve-fitted strategy. It does not eliminate the risk.

---

## Apply it

Open the [Strategies](/strategies) page and find two strategies — one that shows OOS Validated and one that does not. Look at their in-sample (full period) metrics and compare them to the OOS metrics shown on the detail page. Notice how the OOS performance typically differs from the full-period performance. A large gap between in-sample and OOS results is a warning sign of overfitting, even for strategies that technically pass. A small gap suggests the strategy's edge is more robust and consistent.
