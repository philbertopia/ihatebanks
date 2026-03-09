---
slug: intraday-conservative-regime-fix
title: "How we fixed the conservative intraday strategy: regime filtering and a 10-year backtest"
summary: >-
  The conservative intraday variant showed +2127% over 5 years but failed
  out-of-sample validation with a -1.08 Sharpe. A 10-year backtest revealed
  why — and a single regime filter fixed it.
published_at: '2026-03-09'
author: I Hate Banks Research Team
tags:
  - research
  - intraday
  - regime
  - walk-forward
  - oos-validation
---

## The problem: a 5-year result that doesn't survive 10 years

The `conservative` variant of the Intraday Open-Close strategy looked exceptional on a 5-year backtest:

- **+2127% return** (2020–2025)
- **Sharpe 3.48**
- **Max drawdown 10.1%**
- **1630 trades**

But the OOS walk-forward test told a different story: **-1.08 Sharpe, -1.5% average return per window**. The strategy was failing on data it had never seen.

The hypothesis: the 2020–2025 window was a cherry-picked era of exceptional conditions — COVID volatility spike, the 2021 meme bull run, and then renewed vol in 2025. Extending the backtest to 10 years (2015–2026) would expose whether the edge was real or just regime luck.

## What the 10-year backtest revealed

Running the conservative variant from 2015 to 2026 across the full 2479-day cache:

| Metric | 5-year (2020–2025) | 10-year (2015–2026) |
|---|---|---|
| Total Return | +2127% | +594% |
| Sharpe | 3.48 | 0.67 |
| Max Drawdown | 10.1% | 39.1% |
| Total Trades | ~1630 | 2742 |

The Sharpe collapsed from 3.48 to 0.67 when 2015–2019 was included. The max drawdown exploded from 10% to 39%. The pre-2020 period was a graveyard for this strategy.

Looking at the monthly returns confirmed it: 2015–2019 had long flat or negative stretches. 2024 — another low-vol year — produced only +7% despite being in the 5-year window. The edge **only exists when implied volatility is elevated and intraday ranges are wide**.

## The diagnosis: regime dependence

The intraday strategy works by:
1. Identifying unusual options flow (vol/OI ratio above 30-day median)
2. Confirming the setup with ATR (intraday movement potential)
3. Entering directional long calls or puts at 09:35
4. Exiting with a 25% profit target or 15% stop by 15:55

In **high-vol regimes** (VIX elevated, wide daily ranges), step 2 produces genuine movement — small options positions capture meaningful intraday moves. In **low-vol regimes** (VIX compressed, narrow ranges), the same signals fire but the underlying doesn't move enough to overcome execution costs. The strategy pays spread, slippage, and commissions for a setup that goes nowhere.

This is regime dependence: the signal is real, but only in the right environment.

## The fix: a regime alignment gate

The solution is explicit. Before entering any trade, require that the current market regime matches the conditions where the strategy has historically worked. The `regime_filtered` variant adds:

1. **`require_regime_alignment=True`** — blocks entries when the intraday regime classifier doesn't confirm favorable conditions
2. **Raised `min_unusual_factor` to 1.28x** — requires stronger-than-normal flow signals
3. **Higher `min_liquidity_score` (0.55 vs 0.45)** — ensures fills are realistic
4. **Reduced `allocation_per_trade` (1.5% vs 2%)** — smaller per-trade risk given the gating

## The result

Running `regime_filtered` over the same 10-year period:

| Metric | conservative (10yr) | regime_filtered (10yr) |
|---|---|---|
| Total Return | +594% | **+909%** |
| Sharpe | 0.67 | **1.80** |
| Max Drawdown | 39.1% | **8.1%** |
| Total Trades | 2742 | **1109** |
| Win Rate | ~55% | **68.7%** |

The regime gate rejected 1,008,078 candidate option entries over 10 years. Only 24,711 qualified. Of those, 1109 became actual trades. The selectivity is dramatic — but the quality improvement is equally dramatic.

## Walk-forward validation: 15-window OOS test

The real proof is out-of-sample. The walk-forward test splits 10 years into 15 non-overlapping windows (504 days train, 126 days test, 126 days step) and evaluates each test window on data the strategy has never seen:

| OOS Metric | conservative | regime_filtered |
|---|---|---|
| Avg Return per Window | -1.5% | **+36.7%** |
| Avg Sharpe | -1.08 | **+1.56** |
| Avg Max DD | 11.0% | **6.4%** |
| Passes Validation | ❌ | **✅** |

The regime filter **flipped a failing strategy into a validated one** — without changing the core trade logic, only changing when to engage it.

## What this means for strategy development

This discovery illustrates a critical principle: **a large in-sample return is not evidence of edge — it may just be evidence of being in the right regime at the right time**.

The correct workflow is:
1. Run the longest backtest available (10+ years, not 5)
2. Check performance in multiple market regimes, not just recent ones
3. Apply walk-forward OOS validation — anything below Sharpe 0.70 or above 30% max DD on OOS windows fails
4. If a strategy fails OOS, diagnose *why* before tweaking parameters
5. Add explicit regime conditioning rather than re-fitting parameters to historical noise

The `regime_filtered` variant is now the recommended version of this strategy. The `conservative` variant remains available for comparison — but it should be understood as an in-sample artifact of 2020–2025, not a robust standalone edge.

---

*All results are from synthetic backtesting using modeled Black-Scholes option pricing. Past backtest performance does not guarantee future results. See the [disclaimer](/disclaimer) for full risk disclosures.*
