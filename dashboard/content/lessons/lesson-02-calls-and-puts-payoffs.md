---
slug: lesson-02-calls-and-puts-payoffs
title: Calls and puts payoffs
summary: >-
  Understand exactly how calls and puts make or lose money at expiration — and
  why the short side of these contracts is where systematic premium sellers live.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - options-basics
level: beginner
estimated_minutes: 14
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      Short, practical videos on option payoffs and probability — matches the
      premium-selling mindset used in every strategy on this site.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Clear diagrams and definitions for call and put payoff structures,
      breakeven math, and buyer vs. seller perspectives.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Exchange-level explanations of contract mechanics, settlement, and
      exercise — the authoritative source on how options actually work.
disclaimer_required: true
lesson_number: 2
learning_objectives:
  - Calculate the profit or loss of a long and short call at expiration given any stock price.
  - Calculate the profit or loss of a long and short put at expiration given any stock price.
  - Explain why short option sellers have a statistical edge and what their maximum risk is.
  - Connect put and call payoff profiles to the Put Credit Spread and Call Credit Spread strategies.
key_takeaways:
  - A call gives the buyer the right to buy shares at the strike — the seller keeps the premium if the stock stays below the strike at expiration.
  - A put gives the buyer the right to sell shares at the strike — the seller keeps the premium if the stock stays above the strike at expiration.
  - Short options have capped profit (the premium collected) and defined or unlimited risk — managing that risk is the whole job.
  - Credit spreads cap the risk of a short option by buying a further out-of-the-money option as a hedge.
  - Every strategy on this site is built from short puts, short calls, or combinations of both.
---

## What an option contract actually is

An option gives its buyer the **right, but not the obligation**, to buy or sell 100 shares of a stock at a specific price (the **strike price**) on or before a specific date (the **expiration date**).

The buyer pays a **premium** upfront for that right. The seller collects that premium and takes on the obligation.

There are two types:

- **Call option** — the right to *buy* shares at the strike price
- **Put option** — the right to *sell* shares at the strike price

---

## Call option payoffs

### Buying a call (long call)

You pay a premium. In return, you profit if the stock rises above your strike price before expiration.

**Payoff at expiration:**

- Stock closes **above** the strike → profit: `(stock price - strike) × 100 - premium paid`
- Stock closes **at or below** the strike → option expires worthless, you lose the full premium

**Example:** You buy a call with a $150 strike for $3.00 ($300 total). At expiration:

| Stock price | Outcome | P/L |
|---|---|---|
| $160 | In the money | +$700 |
| $153 | Breakeven | $0 |
| $150 | At the strike | -$300 |
| $140 | Out of the money | -$300 |

Breakeven is $153. Below that, you lose up to $300. Above that, profit is theoretically unlimited.

This is why viral stock-versus-call examples need to be read carefully. They are
useful for showing leverage, but they often overemphasize the upside and
understate how often a long call can still lose 100% of premium. See
[How long-call leverage really works](/education/articles/how-long-call-leverage-really-works)
for a corrected worked example and a comparison with this site's premium-selling
framework.

### Selling a call (short call)

You collect a premium upfront. In return, you're obligated to sell 100 shares at the strike if the buyer exercises.

**Payoff at expiration:**

- Stock closes **below** the strike → you keep the full premium. Max gain.
- Stock closes **above** the strike → loss: `(stock price - strike) × 100 - premium collected`

The short call seller's gain is capped at the premium collected. The loss is theoretically unlimited if the stock keeps rising — which is why spreads exist.

---

## Put option payoffs

### Buying a put (long put)

You pay a premium. In return, you profit if the stock drops below your strike price.

**Payoff at expiration:**

- Stock closes **below** the strike → profit: `(strike - stock price) × 100 - premium paid`
- Stock closes **at or above** the strike → option expires worthless, you lose the premium

**Example:** You buy a put with a $140 strike for $2.50 ($250 total). At expiration:

| Stock price | Outcome | P/L |
|---|---|---|
| $125 | In the money | +$1,250 |
| $137.50 | Breakeven | $0 |
| $140 | At the strike | -$250 |
| $150 | Out of the money | -$250 |

Long puts are used for downside protection or directional bets. On this site we don't use them as primary trades — we buy them as hedges inside spreads.

### Selling a put (short put)

You collect a premium. You're obligated to buy 100 shares at the strike if the stock drops below it and the buyer exercises.

**Payoff at expiration:**

- Stock closes **above** the strike → you keep the full premium. Max gain.
- Stock closes **below** the strike → loss: `(strike - stock price) × 100 - premium collected`

**Example:** You sell a put with a $140 strike and collect $2.50 ($250 total). At expiration:

| Stock price | Outcome | P/L |
|---|---|---|
| $150 | Above strike | +$250 (full premium) |
| $140 | At the strike | +$250 |
| $137.50 | Breakeven | $0 |
| $125 | In the money | -$1,250 |

The short put seller makes money if the stock stays flat or rises. Maximum loss is `(strike - premium) × 100` — which happens if the stock goes to zero.

---

## Why premium sellers have a statistical edge

Options are priced using **implied volatility** — the market's expectation of how much a stock will move. Research consistently shows that implied volatility tends to run *higher* than the realized volatility that actually occurs. The market systematically overpays for options.

This means sellers collect a premium that, on average, is slightly inflated. Over many trades, that edge compounds.

This is the entire premise behind every strategy on this site:

> **Sell options at strikes where the stock is unlikely to reach. Collect premium. Let time decay work in your favor. Repeat.**

That doesn't mean it's free money — the risk is real. Position sizing, drawdown management, and out-of-sample validation are how we make the edge durable over time.

---

## From payoffs to strategies

Once you understand the short put and short call payoff profiles, the strategies on this site follow directly:

**Put Credit Spread (PCS):**
Sell an out-of-the-money put, buy a further out-of-the-money put as protection. You collect a net credit. You profit if the stock stays above your short put strike. The long put caps your maximum loss at the width of the spread minus the credit received. This is a defined-risk short put.

**Call Credit Spread (CCS):**
Sell an out-of-the-money call, buy a further out-of-the-money call as protection. You profit if the stock stays below your short call strike. Same capped-risk structure, opposite market assumption.

**Wheel Strategy:**
Sell a cash-secured put. If assigned (stock falls below the strike at expiration), you now own 100 shares and begin selling covered calls against that position. The wheel cycles between short puts and covered calls, collecting premium continuously as long as the position is managed.

---

## Apply it

Then read [How long-call leverage really works](/education/articles/how-long-call-leverage-really-works) and compare the payoff shape of a speculative long call with the payoff shape of the site's defined-risk premium-selling strategies.

Open the [Strategies](/strategies) page and look at the **Put Credit Spread** family. Notice the **win rate** metric — this is the percentage of trades where the stock expired above the short put strike. Compare it to the **max drawdown**. That tension between high win rate and occasional large losses is the defining tradeoff every short-premium seller manages. The strategies on this site are designed to keep that drawdown bounded while letting the win rate compound over time.
