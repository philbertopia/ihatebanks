---
slug: lesson-13-stock-replacement
title: Stock replacement strategy
summary: >-
  Why buy the stock when you can rent the upside for 20% of the cost? Learn
  how to use deep in-the-money call options to replicate stock ownership with
  defined risk and massive capital efficiency.
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
      Concepts on "Poor Man's Covered Call" and substituting stock with deep ITM
      options (LEAPS) are foundational to this strategy.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Explains the mechanics of delta, leverage, and the risk/reward profile of
      buying calls versus owning stock.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Documentation on LEAPS (Long-Term Equity Anticipation Securities) and
      how longer-dated options behave regarding theta and vega.
disclaimer_required: true
lesson_number: 13
learning_objectives:
  - Explain the concept of stock replacement and calculate the capital efficiency vs. owning shares.
  - 'Define the specific entry criteria: 0.80 delta, deep ITM, and DTE selection.'
  - 'Describe the "Plan M" management rules: profit targets, stop losses, and trend exits.'
  - Explain why deep ITM options have less time decay (theta) than at-the-money options.
key_takeaways:
  - Stock replacement uses deep ITM call options (0.80 delta) to mimic stock ownership with less capital.
  - You control 100 shares for typically 15-25% of the cost of buying them outright.
  - 'The leverage is inherent: a 2% move in the stock can generate an 8-10% return on the option.'
  - '"Plan M" rules are critical: take profits at 30%, stop loss at 20%, or exit if the trend reverses.'
  - Unlike stock, options expire. You cannot hold forever. You must manage the position or roll it.
---

## The capital efficiency problem

Owning high-quality stocks is the foundation of most portfolios. But it is capital intensive.

To buy 100 shares of a tech giant trading at $500, you need $50,000. If you have a $100,000 account, that single position consumes 50% of your buying power. This lack of capital efficiency limits diversification and lowers your overall return on capital.

**Stock Replacement** is a strategy that solves this by using deep in-the-money (ITM) call options as a surrogate for shares.

---

## How it works: The 80 Delta Call

Instead of buying 100 shares, you buy **one call option** with specific characteristics:

1.  **Deep In-The-Money:** The strike price is significantly below the current stock price.
2.  **High Delta:** Specifically targeting **0.80 delta**.
3.  **Expiration:** Either 30-90 days (active swing) or 6+ months (LEAPS/investing).

### Why 0.80 Delta?

Delta measures how much an option's price moves for every $1 move in the stock.
- A **0.50 delta** (At-The-Money) option captures only 50% of the move.
- A **0.80 delta** (Deep ITM) option captures 80% of the move.

At 0.80 delta, the option behaves very similarly to the stock itself. If the stock rises $10, your option rises ~$8. You get most of the upside, but you pay a fraction of the price.

---

## The Math: Stock vs. Replacement

**Scenario:** Stock XYZ is trading at $200. You want exposure to 100 shares.

**Option A: Buy Shares**
- Cost: $200 x 100 = **$20,000**
- Capital required: $20,000

**Option B: Stock Replacement**
- Buy the $160 Strike Call (Deep ITM)
- Premium: $45.00
- Cost: $45.00 x 100 = **$4,500**
- Capital required: $4,500

**Result:** You control the same 100 shares for **22.5% of the capital**. You have freed up $15,500 to use elsewhere or keep as cash reserves.

### The Leverage Effect

If XYZ rallies 10% to $220 (+$20 gain):

- **Stock Owner:** Gains $2,000 on $20,000 investment = **10% return**.
- **Option Owner:** The 0.80 delta option gains roughly $16 (0.80 x $20).
    - New Option Value: $45 + $16 = $61.
    - Profit: $1,600 on $4,500 investment = **35.5% return**.

You captured 80% of the dollar profit using only 22% of the capital, resulting in 3.5x leverage.

---

## The "Plan M" Rules

Leverage cuts both ways. If the stock falls, you lose percentage points faster than the stock owner. To manage this, the **Stock Replacement** strategy (specifically the "Authentic" variant on this site) uses a strict set of management rules known as **Plan M**.

### 1. The Entry Gate
Only enter if the stock is in a confirmed uptrend.
- **Price > 200-day Moving Average**
- **10-day EMA > 20-day EMA** (Bullish momentum)
- **Regime:** Avoid entries if the broad market (SPY) is in a downtrend.

### 2. Profit Target (+30%)
Close the position if the option premium increases by 30%.
- If you paid $10.00, sell at $13.00.
- This locks in gains quickly. Because of the leverage, a 30% option gain might only require a 4-5% move in the stock.

### 3. Stop Loss (-20%)
Close the position if the option premium decreases by 20%.
- If you paid $10.00, sell at $8.00.
- This prevents a small pullback from becoming a total loss.

### 4. Trend Exit
Close immediately if the trend reverses.
- **Signal:** 10-day EMA crosses below the 20-day EMA.
- Even if the stop loss hasn't been hit, a broken trend means the reason for the trade is gone. Exit and preserve capital.

---

## Intrinsic vs. Extrinsic Value

One fear beginners have is **time decay (theta)**. "If I buy an option, won't it lose value every day?"

Yes, but **Deep ITM options have very little time value.**

**Example:**
- Stock: $200
- Strike: $160
- Option Price: $45.00

**Intrinsic Value:** $200 - $160 = $40.00
**Extrinsic Value:** $45.00 - $40.00 = $5.00

Only $5.00 of the price is "at risk" to time decay. The vast majority ($40.00) is real, intrinsic equity. This is why 0.80 delta is the sweet spot — you are buying mostly equity, not time.

---

## LEAPS vs. Swing Trading

There are two ways to run this strategy, both tracked on the [Strategies](/strategies) page:

**1. Active Swing (Base / Authentic)**
- **Expiration:** 30-90 days.
- **Management:** Active monitoring of EMA crosses and targets.
- **Goal:** Capture short-to-medium term trends (weeks).

**2. LEAPS (Long-Term Equity Anticipation Securities)**
- **Expiration:** 6 months to 2 years.
- **Management:** More passive.
- **Goal:** Long-term investing substitute.
- **Benefit:** Theta decay is almost non-existent on options with 300+ days to expiration.

---

## Risks to understand

**1. 100% Loss Potential**
If you own the stock and it falls 20%, you still have 80% of your money. If you own the option and the stock falls 20% (below your strike), you could lose 100% of your investment. The stop loss is mandatory, not optional.

**2. Volatility Crush**
If you buy calls when Implied Volatility (IV) is very high (like before earnings), and then IV drops, your option will lose value even if the stock stays flat.
- **Rule:** Avoid buying calls when IV Rank is high (>50). Prefer buying when markets are calm.

---

## Apply it

Go to the [Strategies](/strategies) page and look at the **Stock Replacement** family. Compare the **"Authentic"** variant (which uses Plan M exits) with the **"Base"** variant (which just rolls). Notice how the profit targets and stop losses affect the **Max Drawdown**. The leverage of options requires the discipline of a machine to manage safely.
