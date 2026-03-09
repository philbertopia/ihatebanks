---
slug: lesson-08-put-credit-spreads
title: Put credit spreads
summary: >-
  The put credit spread is the core strategy on this site. Learn exactly how
  it is constructed, why it works, how to calculate its profit and loss at
  any stock price, and what the backtest results actually represent.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - strategy
level: intermediate
estimated_minutes: 20
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      tastylive has produced more content on put credit spreads than any other
      educational source. Their strike selection, DTE targeting, and profit
      target discipline directly informed the design of this strategy.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Clear diagrams and step-by-step math for put credit spread construction,
      breakeven calculation, and payoff at expiration.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Technical documentation on vertical spread mechanics, margin
      requirements, and how assignment works on the short leg.
disclaimer_required: true
lesson_number: 8
learning_objectives:
  - Construct a put credit spread by selecting the correct legs and calculate the net credit received.
  - Calculate maximum profit, maximum loss, and breakeven price for any put credit spread.
  - Explain why the spread structure caps risk compared to a naked short put.
  - Describe the entry criteria — strike selection, DTE, and credit threshold — used in the backtested strategies.
key_takeaways:
  - A put credit spread is a short OTM put plus a long further OTM put on the same underlying and expiration.
  - Maximum profit is the net credit received. Maximum loss is the spread width minus the credit. Both are defined at entry.
  - The strategy profits when the stock stays above the short put strike at expiration — no movement required, just stability or upward drift.
  - Entry criteria target the 0.20-0.30 delta range for the short strike, 30-45 DTE, and a minimum credit-to-width ratio to ensure the trade is worth taking.
  - The long put is not a cost — it is a defined-risk guarantee. It transforms a position with theoretically large losses into one with a hard floor.
---

## What a put credit spread is

A **put credit spread** — also called a bull put spread — is a two-leg options position constructed by:

1. **Selling** (short) an out-of-the-money put at a higher strike
2. **Buying** (long) a further out-of-the-money put at a lower strike

Both legs are on the same underlying stock and have the same expiration date. You collect a net credit because the option you sell is worth more than the option you buy.

---

## Construction example

Stock: XYZ at $150
Expiration: 38 days away (monthly)

| Leg | Action | Strike | Premium |
|---|---|---|---|
| Short put | Sell | $140 | +$2.20 |
| Long put | Buy | $135 | -$0.85 |
| **Net credit** | | | **+$1.35** |

You collect $1.35 per share, or **$135 per contract** (100 shares), when you open the position.

---

## Profit and loss at expiration

The spread width is $5 ($140 - $135). The credit received is $1.35.

| Stock price at expiration | What happens | P/L per contract |
|---|---|---|
| Above $140 | Both puts expire worthless | +$135 (max profit) |
| $140 | Short put at the money, long put worthless | +$135 (max profit) |
| $138.65 | Breakeven | $0 |
| $135 | Short put worth $5, long put worth $0 | -$365 (max loss) |
| Below $135 | Both puts in the money | -$365 (max loss) |

**Max profit:** $135 (the credit received)
**Max loss:** ($5.00 - $1.35) × 100 = **$365**
**Breakeven:** $140 - $1.35 = **$138.65**

The stock can fall $11.35 (from $150 to $138.65) before the position starts losing money. That buffer is the safety margin.

---

## Why this beats a naked short put

A naked short put (selling the $140 put without the $135 put hedge) collects more premium but has a much larger maximum loss: $(strike - premium) × 100 = roughly $13,765 if the stock goes to zero.

The long put transforms this into a **defined-risk trade**:
- Maximum loss is $365, regardless of how far the stock falls
- Margin requirements are far lower (brokers charge based on the defined max loss)
- You can sleep at night knowing the worst possible outcome

The tradeoff: you give up $85 per contract for that guarantee. Most systematic traders consider this a good deal.

---

## Entry criteria used in the backtested strategies

The Put Credit Spread strategies on this site use these entry filters:

**Strike selection:**
- Short put at approximately **0.20-0.30 delta** (roughly 70-80% probability OTM at expiration)
- Long put 5 strikes further OTM (creates a $5-wide spread)

**Timing:**
- Enter at **30-45 DTE** — captures the steepest part of theta decay while avoiding near-expiry gamma risk
- Monthly expirations only (3rd Friday) for maximum liquidity

**Credit filter:**
- Minimum credit-to-width ratio of approximately 25-30% — if the spread pays less than $1.25-$1.50 on a $5-wide spread, the trade is skipped
- This filter prevents entering trades where the premium doesn't justify the risk

**Universe:**
- Top 50 liquid equities and ETFs by options volume
- Trend filter applied: only enter long-delta positions (short puts) when the underlying is in an uptrend

---

## Management rules

**Profit target:** Close the spread when it reaches 50% of maximum profit ($67.50 on the example above). This exits at the steepest part of the decay curve and frees capital for the next trade.

**Stop loss:** Close if the spread price reaches 2x the premium received ($270 debit, resulting in a $135 loss). This prevents a routine losing trade from becoming a catastrophic one.

**Time stop:** If neither target is hit by 21 DTE, consider closing regardless. The final 3 weeks carry elevated gamma risk.

---

## What the backtest results represent

When you look at the [Put Credit Spread](/strategies) strategy metrics:

- **Win rate** — the percentage of trades that closed at the profit target or expired profitable
- **Total return** — cumulative P/L across all trades over 5 years, expressed as a percentage
- **Sharpe ratio** — return per unit of risk; higher values mean smoother equity curves
- **Max drawdown** — the worst peak-to-trough loss in the equity curve
- **OOS validation** — whether the strategy maintained its edge on data it had never seen (walk-forward test)

The 5-year backtest period (2020-2025) includes the 2020 crash, the 2022 bear market, and the 2023-2024 bull run — a realistic range of market conditions that tests the strategy's resilience.

## Apply it

Open the [Put Credit Spread](/strategies) strategy page. Find the variant with the highest Sharpe ratio. Look at its win rate alongside its max drawdown. Using the example math above, estimate what the average premium collected per trade might have been. Does the win rate justify the max drawdown risk? This is the core question every systematic trader needs to answer before deploying capital.
