---
slug: lesson-16-regime-switching
title: Regime switching
summary: >-
  Strategies are not universal. A bull market strategy will destroy you in a
  bear market. Learn how to identify market regimes and automatically switch
  gears to stop fighting the trend.
published_at: '2026-03-08'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - strategy
  - advanced
level: advanced
estimated_minutes: 22
references:
  - title: Trend Following (Michael Covel)
    url: 'https://www.trendfollowing.com/'
    source: article
    why_it_matters: >-
      The bible of regime-based trading. Explains why "the trend is your friend"
      is a mathematical reality, not just a rhyme.
  - title: Investopedia - Market Regimes
    url: 'https://www.investopedia.com/articles/trading/08/market-regimes.asp'
    source: article
    why_it_matters: >-
      Definitions of volatility regimes and trend regimes, and how correlation
      changes during market stress.
  - title: Cboe VIX Methodology
    url: 'https://www.cboe.com/tradable_products/vix/'
    source: docs
    why_it_matters: >-
      Understanding how volatility regimes are defined using the VIX is critical
      for knowing when to switch from short-premium to cash or long-volatility.
disclaimer_required: true
lesson_number: 16
learning_objectives:
  - Define a "market regime" using objective metrics like Moving Averages and VIX.
  - Explain why "all-weather" strategies often underperform regime-specific strategies.
  - Describe the logic of the Regime Credit Spread strategy (switching between Puts and Calls).
  - Identify the "Cash Gang" regime and why doing nothing is a valid active position.
key_takeaways:
  - Markets have distinct personalities (regimes). A strategy optimized for one personality often fails in another.
  - The 200-day Moving Average is the standard dividing line between Bull and Bear regimes.
  - Volatility (VIX) defines the "speed" of the market. High vol requires different tactics (wider stops, smaller size) than low vol.
  - Regime switching strategies automate the decision to flip from bullish (short puts) to bearish (short calls).
  - The hardest part of regime switching is the transition (whipsaw). You will often take a loss on the first trade of a new regime.
---

## The myth of the all-weather strategy

Beginners look for a strategy that works "all the time." They want a setup they can trade every Monday morning regardless of what the news says.

**This is the fastest way to blow up.**

- **Short Puts** print money in bull markets but get crushed in crashes.
- **Short Calls** profit in bear markets but get overrun in rallies.
- **Iron Condors** win in sideways markets but lose in trends.

Instead of trying to force one tool to do every job, systematic traders use **Regime Switching**. They identify the current market environment and deploy the specific weapon designed for that fight.

---

## Defining the regime

You cannot trade based on "vibes." You need objective rules to define the regime.

### 1. The Trend Regime (Direction)
The most common filter is the **200-day Moving Average (MA200)** of the S&P 500 (SPY).

- **Bullish Regime:** Price > MA200. The long-term trend is up. Dip buying works. Short puts work.
- **Bearish Regime:** Price < MA200. The long-term trend is down. Rallies are often traps. Short calls work. Cash works.

*Refinement:* Some traders use the "Golden Cross" (50-day MA crossing above 200-day MA) to confirm a regime change, as it lags less than price alone during choppy periods.

### 2. The Volatility Regime (Speed)
The **VIX** measures the speed and fear of the market.

- **Low Vol (VIX < 15):** Grind-up market. Option premiums are cheap. Long calls work well; short puts offer poor risk/reward.
- **Normal Vol (VIX 15-25):** Standard behavior. Credit spreads work best here.
- **High Vol (VIX > 30):** Panic. Correlations go to 1.0 (everything falls together). Premiums are huge, but price moves are violent.

---

## The "Regime Credit Spread" strategy

The **Regime Credit Spread** strategy on this site is a practical application of this concept. It is a meta-strategy that holds no loyalty to any direction. It simply asks:

> *"Is the SPY above the 200-day MA?"*

**IF YES (Bullish):**
- Deploy **Put Credit Spreads**.
- Sell downside protection.
- Bet that the market will not crash.

**IF NO (Bearish):**
- Deploy **Call Credit Spreads**.
- Sell upside resistance.
- Bet that the market will not rally to new highs.

This allows the portfolio to be "long" in 2021, "short" in 2022, and "long" again in 2023—automatically.

---

## The cost of switching: Whipsaw

Regime switching is not magic. Its weakness is the **transition zone**.

When the market moves from Bull to Bear, it doesn't send a memo. It usually crashes through the 200-day MA violently.
1. You are holding Bullish Put Spreads.
2. The market crashes below the MA200.
3. Your Put Spreads hit their stop loss (Max Loss).
4. The system switches to Bearish Call Spreads.

You *will* take a loss at the turning point. This is the "insurance premium" you pay to be on the right side of the major trend for the next 6-12 months.

**Whipsaw Risk:** If the market chops around the MA200 (crossing it every few days), the system will constantly switch sides and take losses on both. To prevent this, we use **hysteresis** or confirmation filters (e.g., "must be below MA200 for 3 consecutive days").

---

## The "Cash Gang" regime

Sometimes, the best position is no position.

In the **Stock Replacement** strategy (specifically the "Authentic" and "Defensive" variants), there is a rule:

> *"If SPY is in a downtrend, sit in cash."*

Why? Because buying calls (even deep ITM ones) in a bear market is fighting gravity. Even if a specific stock looks good, the tide is going out.

Sitting in cash during 2022 saved many portfolios. While the S&P 500 lost 19% and the Nasdaq lost 33%, the "Cash Gang" strategy lost 0% (minus inflation). Preserving capital during a storm is the only way to have chips to play with when the sun comes back out.

---

## What the local portfolio uses now

In this workspace, the current portfolio does not yet run every theoretical
regime sleeve people like to diagram on whiteboards.

The practical local architecture is:

- **Core sleeve:** `openclaw_regime_credit_spread|regime_legacy_defensive`
- **Supporting monitors:** `openclaw_put_credit_spread|legacy_replica` and `openclaw_call_credit_spread|ccs_defensive`
- **Benchmark variants:** `regime_balanced` and `regime_defensive`
- **Not added yet:** neutral iron-condor sleeve
- **Not added yet:** convex hedge sleeve

That restraint is intentional. The core regime-switch sleeve already adapts by
flipping spread direction. The first portfolio-overlay research pass did not
improve it, so adding more moving parts now would be complexity without a
better edge.

---

## Apply it

Go to the [Strategies](/strategies) page. Compare the **Put Credit Spread** (Bullish only) with the **Regime Credit Spread** (Switching).

Look at the year 2022.
- The Put Credit Spread strategy likely took losses or sat out.
- The Regime Credit Spread strategy switched to selling calls and likely profited from the downtrend.

This is the power of adaptability. You don't need to predict the future; you just need to align with the present.
