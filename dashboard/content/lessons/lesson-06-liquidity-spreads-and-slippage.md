---
slug: lesson-06-liquidity-spreads-and-slippage
title: 'Liquidity, spreads, and slippage'
summary: >-
  The bid/ask spread is a tax on every trade. Slippage is invisible in theory
  but very real in practice. Understanding execution costs explains why strategy
  selection and underlying choice matter as much as the strategy logic itself.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - execution
level: intermediate
estimated_minutes: 14
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      Practical guidance on reading options chains, selecting liquid strikes,
      and using limit orders to control execution costs on options trades.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Covers bid/ask mechanics, market makers, and how liquidity affects
      options pricing and the real cost of entry and exit.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Exchange-level documentation on market structure, how options quotes are
      generated, and why liquidity varies across expirations and strikes.
disclaimer_required: true
lesson_number: 6
learning_objectives:
  - Explain what the bid/ask spread is and calculate the cost of crossing it on an options trade.
  - Define slippage and explain why it affects systematic strategies more than one-off trades.
  - Identify the characteristics of a liquid option and explain why liquidity matters for strategy selection.
  - Describe how this site models execution costs in its backtests.
key_takeaways:
  - The bid/ask spread is the immediate cost of every trade — you buy at the ask and sell at the bid, giving up the difference to the market maker.
  - Slippage is the gap between the theoretical fill price and the actual fill. It compounds over hundreds of trades in a systematic strategy.
  - Liquid options have tight bid/ask spreads and high open interest. Illiquid options can have spreads that wipe out the entire premium collected.
  - This site models execution at the midpoint minus a slippage adjustment — a realistic assumption that accounts for the cost of trading.
  - Stick to high-volume underlyings with monthly expirations. This is where liquidity is deepest and execution costs are lowest.
---

## The bid/ask spread

When you look at an options quote, you see two prices:

- **Bid** — the highest price a buyer is currently willing to pay
- **Ask** — the lowest price a seller is currently willing to accept

The difference between them is the **bid/ask spread**.

**Example:**
- Bid: $1.85
- Ask: $2.15
- Spread: $0.30

If you buy this option at the ask ($2.15) and immediately want to sell it, you would only receive $1.85. You have already lost $0.30 per share ($30 per contract) before the market moves at all.

This spread goes to the **market maker** — the firm providing liquidity by standing ready to buy and sell at all times. It is the price of immediacy.

---

## Why the spread matters for options sellers

When you sell an option (a credit spread), you also cross the bid/ask:

- You want to sell at the bid for the short leg
- You want to buy at the ask for the long leg

A credit spread with two legs crosses two bid/ask spreads simultaneously. For a $5-wide spread collecting $1.50 in premium, a combined $0.40 in bid/ask costs represents 27% of the premium collected — before any market movement occurs.

On a single trade this might seem acceptable. Across 200 trades per year in a systematic strategy, the cumulative effect on returns is significant.

---

## Slippage

Slippage is the gap between the price you expect to get and the price you actually receive. It occurs because:

1. **Your order moves the market** — if you are large relative to the available liquidity, your order consumes bids or offers, pushing the price against you
2. **Quotes change between placing and filling** — in fast markets, the price can move before your order executes
3. **Market impact** — even a modest-sized order can affect the price of an illiquid option

Slippage is largely invisible in backtests that use mid-price fills. A strategy that looks profitable at mid-price may be marginal or unprofitable when realistic fills are applied.

---

## What makes an option liquid

| Characteristic | Liquid option | Illiquid option |
|---|---|---|
| Bid/ask spread | $0.05-$0.20 | $0.50-$2.00+ |
| Open interest | Thousands of contracts | Dozens of contracts |
| Volume | Active daily trading | Sporadic or zero |
| Underlying | SPY, QQQ, AAPL, TSLA | Small-cap stocks |
| Expiration | Monthly (3rd Friday) | Weekly, quarterly |

Liquid options are easier to enter and exit at a fair price. Illiquid options punish you on both sides — you give up a wide spread on entry and again on exit.

---

## The monthly expiration liquidity advantage

Not all expirations are equally liquid. Monthly expirations — the third Friday of each month — have been the standard expiration date since listed options were created. They carry the deepest liquidity and tightest spreads.

Weekly expirations exist for major underlyings, but they typically have wider spreads, especially at OTM strikes. Quarterly and LEAPS expirations have even lower liquidity.

The strategies on this site use **monthly expirations** for this reason. The liquidity advantage compounds over hundreds of trades.

---

## How execution costs are modeled on this site

The backtests on this site do not assume fills at the theoretical mid-price. Execution is modeled with a slippage adjustment calibrated to realistic bid/ask conditions for each underlying.

This is important for interpreting the results: the returns you see are not paper-trading numbers at perfect fills. They reflect what a systematic executor would realistically achieve when trading with discipline.

The distinction matters because many backtests you will find online use mid-price fills, which systematically overstate returns for premium-selling strategies. When comparing results from different sources, always ask: how was execution modeled?

---

## Practical rules for execution

1. **Only trade highly liquid underlyings** — SPY, QQQ, and the top 50-100 by options volume
2. **Use limit orders** — never use market orders on options; you will give up the entire spread
3. **Target the midpoint or better** — place your limit between the bid and ask, closer to the mid
4. **Check open interest at your specific strike** — even a liquid underlying can have illiquid OTM strikes
5. **Prefer monthly expirations** — the bid/ask is tightest and liquidity is most reliable

---

## Apply it

Open the [Backtest Explorer](/backtest) and look at the "universe" for any strategy. Notice it trades liquid large-cap equities and index ETFs. Now look at the total trades count over 5 years. Multiply the number of trades by an estimated $0.25 per contract in slippage cost. This gives you a rough sense of the execution drag the strategy's returns have already absorbed — and why liquid underlyings are non-negotiable for systematic strategies.
