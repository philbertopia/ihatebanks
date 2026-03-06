---
slug: lesson-03-moneyness-dte-intrinsic-and-extrinsic
title: 'Moneyness, DTE, intrinsic and extrinsic'
summary: >-
  The four concepts that determine an option's price and how fast it decays.
  Understanding intrinsic vs. extrinsic value explains why premium sellers
  target out-of-the-money options in the 30-60 day window.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - options-basics
level: beginner
estimated_minutes: 15
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      Excellent explanations of time decay and why extrinsic value accelerates
      toward expiration — directly relevant to how credit spread strategies
      are managed and when to close.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Clear breakdown of intrinsic and extrinsic value with worked examples
      and a good reference for DTE concepts and their relationship to premium
      pricing.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Technical documentation on how options are priced and settled, including
      how moneyness determines exercise behavior at expiration.
disclaimer_required: true
lesson_number: 3
learning_objectives:
  - Define in-the-money, out-of-the-money, and at-the-money for both calls and puts.
  - Calculate the intrinsic value of an option given a stock price and strike price.
  - Explain why extrinsic value decays over time and why the decay accelerates near expiration.
  - Describe why the 30-60 DTE window is preferred for systematic premium selling.
key_takeaways:
  - Moneyness describes where the stock is relative to the strike — ITM options have intrinsic value, OTM options have only extrinsic value.
  - Intrinsic value is what you would gain by exercising the option right now. It cannot be negative.
  - Extrinsic value is everything else in the premium — time remaining plus the cost of implied volatility.
  - Extrinsic value decays to zero by expiration. This decay accelerates in the final 30 days.
  - Selling OTM options in the 30-60 DTE window captures the steepest part of the decay curve while avoiding the chaos of near-expiry gamma.
---

## Moneyness

**Moneyness** describes the relationship between the current stock price and the option's strike price. It tells you whether exercising the option right now would make money.

### For a call option

| Condition | Moneyness | Meaning |
|---|---|---|
| Stock price > Strike | In-the-money (ITM) | Exercising gives you shares cheaper than market price |
| Stock price = Strike | At-the-money (ATM) | Breakeven — exercising has no immediate gain |
| Stock price < Strike | Out-of-the-money (OTM) | Exercising makes no sense — you would pay more than market price |

**Example:** Stock is at $148. A $140 call is ITM. A $160 call is OTM.

### For a put option

The relationship is reversed — puts profit when the stock falls.

| Condition | Moneyness | Meaning |
|---|---|---|
| Stock price < Strike | In-the-money (ITM) | Exercising lets you sell shares above market price |
| Stock price = Strike | At-the-money (ATM) | Breakeven |
| Stock price > Strike | Out-of-the-money (OTM) | Exercising makes no sense — you would sell below market price |

**Example:** Stock is at $148. A $160 put is ITM. A $140 put is OTM.

---

## Intrinsic value

Intrinsic value is the amount you would lock in if you exercised the option right now. It is the concrete, real value of the contract independent of time.

**For a call:** `intrinsic value = max(stock price − strike, 0)`

**For a put:** `intrinsic value = max(strike − stock price, 0)`

Intrinsic value cannot be negative. An OTM option always has zero intrinsic value.

**Examples:**
- Stock at $155, call strike at $140 → intrinsic = $15.00
- Stock at $155, put strike at $170 → intrinsic = $15.00
- Stock at $155, call strike at $160 → intrinsic = $0 (OTM, no value)

---

## Extrinsic value (time value)

Extrinsic value is everything in the option's premium beyond its intrinsic value.

`extrinsic value = option premium − intrinsic value`

For an OTM option, the *entire premium is extrinsic value* — there is zero intrinsic value.

Extrinsic value reflects two things:
1. **Time remaining** — more time means more opportunity for the stock to move against you. The buyer pays for that optionality.
2. **Implied volatility** — how much the market expects the stock to move. Higher expected movement = higher extrinsic value.

**Why this matters for sellers:** Extrinsic value decays to exactly zero by expiration. This decay is called **theta decay**, and it is the seller's primary source of profit. Every day that passes, a portion of the extrinsic value evaporates — that value transfers from the option buyer to the option seller.

---

## DTE — Days to Expiration

DTE is how many calendar days remain until the option expires. It is one of the most important inputs in any options strategy because it determines how much extrinsic value exists and how fast it is decaying.

### The theta decay curve

Theta decay is not linear. Options lose value slowly when there is a lot of time remaining, then faster and faster as expiration approaches. The curve accelerates sharply in the final 30 days.

This creates two competing pressures:

- **Too much DTE (60+ days):** Ample extrinsic value, but decay is slow. You wait a long time for the edge to materialize.
- **Too little DTE (under 21 days):** Most decay has already occurred. The remaining extrinsic value is small — and **gamma risk** spikes, making small stock moves cause disproportionately large swings in the option's price.

### The 30-60 DTE sweet spot

Systematic premium sellers target **30-60 DTE** because:
- There is enough extrinsic value to make the trade worthwhile
- Theta decay is accelerating — you are entering the steepest part of the curve
- Gamma is still manageable — the position does not whipsaw day to day

The strategies on this site target monthly expirations (the third Friday of each month), which typically places entries in the 30-50 DTE range.

---

## Putting it together: why OTM options in the 30-60 DTE window

When you sell an OTM option at 45 DTE:
- The entire premium is extrinsic value — there is no intrinsic value working against you
- Theta decay is accelerating — you collect the steepest part of the curve
- The stock must move significantly in the wrong direction before you lose money
- The premium collected is your buffer — the breakeven distance

This is not coincidental. Every strategy on this site was designed around these structural features of options pricing. The backtests show what happens when this approach is applied systematically over hundreds of trades and multiple market regimes.

---

## Apply it

Open the [Backtest Explorer](/backtest) and look at a Put Credit Spread run. Find the average DTE at entry. Now look at the win rate — the percentage of trades where the short put expired out of the money. Notice that the strategy profits from the stock simply *not falling to the strike* — the intrinsic value stays at zero, and the full extrinsic value the seller collected at entry decays into profit.
