---
slug: lesson-15-iron-condors
title: Iron condors
summary: >-
  Combine a put credit spread and a call credit spread to create a market-neutral
  income engine. Learn how iron condors profit from stagnation and how to manage
  a position that is attacked on two fronts.
published_at: '2026-03-08'
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
      tastylive popularized the iron condor as a core retail strategy. Their
      mechanics on wing width, delta selection, and management at 21 DTE are
      industry standard for systematic traders.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Clear diagrams of the iron condor payoff structure, showing the defined
      profit zone and the two breakeven points.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Technical details on margin requirements for iron condors (often lower
      than holding two separate spreads) and settlement mechanics.
disclaimer_required: true
lesson_number: 15
learning_objectives:
  - Construct an iron condor by combining a put credit spread and a call credit spread.
  - Calculate the max profit, max loss, and breakeven points for an iron condor.
  - Explain why the margin requirement for an iron condor is often the same as a single spread.
  - Describe the ideal market environment for iron condors versus directional spreads.
key_takeaways:
  - An iron condor is a short put spread and a short call spread on the same underlying and expiration.
  - It profits when the stock stays between the two short strikes. It is a neutral strategy.
  - You collect two premiums but usually only post collateral for one side, increasing capital efficiency.
  - The risk is that the stock moves too far in *either* direction. You are trading direction for a wider profit window.
  - Management is more complex — you must decide whether to close the whole trade or adjust the untested side when challenged.
---

## What an iron condor is

An **iron condor** is a four-leg options strategy constructed by combining:

1.  A **Put Credit Spread** (bullish/neutral)
2.  A **Call Credit Spread** (bearish/neutral)

Both spreads use the same underlying asset and the same expiration date.

The goal is to surround the current stock price with a "profit zone." If the stock stays between your short put and your short call, both spreads expire worthless, and you keep the total premium collected.

---

## Construction example

Stock: XYZ at $150
Expiration: 38 days away

**Leg 1: Put Credit Spread**
- Sell $140 Put
- Buy $135 Put
- Credit: $1.35

**Leg 2: Call Credit Spread**
- Sell $160 Call
- Buy $165 Call
- Credit: $1.25

**Total Net Credit:** $1.35 + $1.25 = **$2.60** ($260 per contract)

---

## Profit and loss

**Max Profit:** The total credit received ($2.60). This happens if XYZ stays between $140 and $160 at expiration.

**Max Loss:** The width of the spread minus the total credit.
- Spread width: $5.00 (both sides are $5 wide)
- Total credit: $2.60
- Max loss: $5.00 - $2.60 = **$2.40** ($240 per contract)

**Breakeven Points:**
- Downside: Short Put Strike - Total Credit = $140 - $2.60 = **$137.40**
- Upside: Short Call Strike + Total Credit = $160 + $2.60 = **$162.60**

As long as XYZ stays between $137.40 and $162.60 at expiration, the trade is profitable.

---

## The capital efficiency advantage

This is the "magic" of the iron condor.

If you traded these two spreads separately, you might expect to put up collateral for both ($500 for the put spread + $500 for the call spread).

But the stock cannot be below $140 and above $160 at the same time. You can only lose on one side.

Therefore, most brokers only require **collateral for one side** (the wider of the two spreads).
- Collateral required: $500 (width of the spread)
- Premium collected: $260
- Max risk: $240

You are collecting nearly double the premium (vs. a single spread) for the same capital requirement. This significantly boosts the potential return on capital — if the stock cooperates.

---

## When to use an iron condor

Iron condors are **neutral** strategies. They work best in:
- **Range-bound markets:** The stock is chopping sideways.
- **High Implied Volatility:** When IV is high, premiums are rich on both calls and puts. You can sell strikes further away from the current price and still collect good credit.
- **Post-earnings:** After a big move, stocks often consolidate. This "volatility crush" and price stagnation is perfect for condors.

They are dangerous in:
- **Trending markets:** If the stock is ripping higher or crashing lower, one side of your condor will be overrun.
- **Low IV environments:** Premiums are thin, forcing you to bring your strikes closer to the current price to get paid. This narrows your profit window and increases risk.

---

## Management mechanics

Managing an iron condor is harder than managing a single spread because you have two ways to lose.

**1. The "Do Nothing" Approach**
Set a profit target (e.g., 50% of total credit) and a stop loss (e.g., 2x total credit). If neither is hit, close at 21 DTE. This is the simplest systematic approach.

**2. The "Roll the Untested Side" Approach**
If the stock rallies toward your call spread, your put spread is becoming worthless quickly. You can close the put spread for a profit and "roll it up" (sell a new put spread closer to the current price) to collect more credit.
- *Pros:* Increases total credit, which widens breakeven points.
- *Cons:* Increases directional risk if the stock reverses (whipsaw).

**3. Closing Early**
Because you collected a large credit ($2.60 on a $5 width), your max profit is high, but your probability of profit is lower than a single spread (since you have two ways to lose). Taking profits early (at 35-50%) is crucial to avoid holding a winner until it becomes a loser.

---

## Relation to strategies on this site

While the [Strategies](/strategies) page lists Put Credit Spreads and Call Credit Spreads separately, you can simulate an iron condor portfolio by running both strategies simultaneously.

- If the **Put Credit Spread** strategy is active (bullish/neutral regime)...
- And the **Call Credit Spread** strategy is active (bearish/neutral regime)...
- You effectively have an iron condor or "strangle swap" portfolio.

However, the strategies here often filter for trend. In a strong uptrend, the Call Credit Spread strategy might sit in cash while the Put Credit Spread works. This "unbalanced condor" adapts to the market rather than forcing neutrality when the market is trending.

---

## Apply it

Go to the [Strategies](/strategies) page. Look at the equity curves for the Put Credit Spread and Call Credit Spread. Find a period where the market was flat (choppy). Notice how both strategies likely collected premium. Now find a strong trend (like 2022 bear or 2023 bull). Notice how one strategy likely sat out or took losses while the other performed. An iron condor forces you to be in both, all the time — which is why regime filters (separating the legs) often outperform rigid iron condors.