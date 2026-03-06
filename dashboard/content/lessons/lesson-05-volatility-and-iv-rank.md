---
slug: lesson-05-volatility-and-iv-rank
title: Volatility and IV rank
summary: >-
  Implied volatility drives option prices. IV rank tells you whether options
  are cheap or expensive relative to their history. Knowing when to sell
  premium and when to wait is largely a volatility timing question.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - options-basics
level: intermediate
estimated_minutes: 16
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      tastylive popularized the use of IV rank as a trade entry filter. Their
      content on selling premium in high-IV environments is central to the
      strategies on this site.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Explains the difference between historical and implied volatility, VIX
      mechanics, and why volatility is mean-reverting.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Cboe invented the VIX. Their documentation on volatility measurement and
      options pricing is the authoritative technical reference.
disclaimer_required: true
lesson_number: 5
learning_objectives:
  - Distinguish between historical volatility and implied volatility and explain what each measures.
  - Define IV rank and calculate it given a current IV and a 52-week range.
  - Explain why premium sellers prefer to enter trades when IV rank is elevated.
  - Describe what typically happens to implied volatility after a fear spike.
key_takeaways:
  - Historical volatility measures how much a stock actually moved in the past. Implied volatility measures how much the market expects it to move in the future.
  - Implied volatility is systematically overstated relative to actual moves — this is the structural edge for premium sellers.
  - IV rank compares today's implied volatility to its 52-week range. A rank of 70 means IV is higher than 70% of days in the past year.
  - High IV rank means options are expensive — more premium to collect, and vol is likely to revert lower (which profits short vega positions).
  - Low IV rank means options are cheap — less premium, and selling into low vol offers thin rewards for the risk taken.
---

## Two types of volatility

Volatility is the central variable in options pricing. But there are two very different things the word can mean.

### Historical volatility (HV)

Historical volatility — also called realized volatility — measures how much a stock actually moved over a past period. It is calculated from actual price data, typically the annualized standard deviation of daily returns over the past 20, 30, or 60 days.

HV tells you what happened. It is backward-looking.

### Implied volatility (IV)

Implied volatility is extracted from current option prices. It is the volatility number that, when plugged into an options pricing model, produces the market's current price for that option.

IV tells you what the market expects to happen. It is forward-looking.

**The critical insight:** Implied volatility is systematically higher than the historical volatility that actually occurs. The market consistently overpays for options — pricing in more movement than materializes. This persistent gap is the structural edge that systematic premium sellers exploit.

---

## The VIX

The VIX is the most widely followed measure of implied volatility. It represents the market's expected 30-day volatility for the S&P 500, derived from SPY and SPX option prices.

| VIX level | Market interpretation |
|---|---|
| Below 15 | Calm, low-fear environment |
| 15-20 | Normal range |
| 20-30 | Elevated uncertainty |
| 30+ | Fear and stress in the market |
| 50+ | Crisis conditions (2020 COVID spike hit 85) |

High VIX means options are expensive across the market. Low VIX means options are cheap. For individual stocks, each has its own implied volatility level — but VIX provides useful market-wide context.

---

## IV rank

The VIX tells you the current implied volatility, but it does not tell you whether it is high or low *relative to that asset's history*. A VIX of 25 might be extremely elevated for a calm utility stock but totally normal for a volatile tech name.

**IV rank (IVR)** solves this by comparing today's IV to the trailing 52-week range:

`IV rank = (current IV - 52-week IV low) / (52-week IV high - 52-week IV low) × 100`

**Example:**
- 52-week IV low: 18%
- 52-week IV high: 55%
- Current IV: 42%
- IV rank = (42 - 18) / (55 - 18) × 100 = **65**

An IV rank of 65 means implied volatility is currently higher than it was on 65% of days in the past year. Options are relatively expensive.

### How to use IV rank

| IV rank | Interpretation | Implication for sellers |
|---|---|---|
| 0-25 | IV is low relative to history | Options are cheap — thin premium, poor risk/reward for sellers |
| 25-50 | Moderate IV | Acceptable for entry depending on the strategy |
| 50-75 | Elevated IV | Good environment for selling premium |
| 75-100 | Very high IV | Options are very expensive — maximum premium, but high fear means risk is real |

Premium sellers want to sell when options are expensive. Selling into low IV is like selling insurance at rock-bottom rates — the premium is small relative to the actual risk.

---

## Mean reversion of volatility

Volatility is mean-reverting. After spikes — earnings, macro events, market crashes — implied volatility tends to fall back toward its historical average.

This creates a second layer of profit for short sellers: if IV is elevated when you sell and then falls, your short option position benefits from the IV compression even if the stock barely moves. This is the **vega component** of profit.

**The sequence:**
1. Market fear event → IV spikes → option prices rise
2. You sell premium at inflated prices
3. Fear subsides → IV falls → option prices fall
4. You buy back the position for less → profit from IV compression

The strategies on this site primarily profit from theta (time decay), but IV contraction after entry amplifies returns and reduces the time it takes to reach profit targets.

---

## What happens when you sell into low IV

When you sell options with low IV rank:
- The premium collected is thin
- The breakeven distance is narrow
- If any uncertainty arrives, IV spikes and your short position immediately loses value
- You are selling insurance cheaply, then being exposed to the very risk you underpriced

This is one of the most common mistakes new premium sellers make — selling options simply because they exist, regardless of whether the implied volatility environment justifies it.

---

## Apply it

The [Strategies](/strategies) page shows backtest results over 2020-2025 — a period that included the 2020 COVID crash (VIX 85), the 2022 bear market (elevated VIX), and the 2023-2024 bull run (low VIX). Look at the equity curve in any strategy detail page. Notice how different market volatility regimes affected the strategy's performance. The OOS validation tests whether the strategy's edge holds across these different environments.
