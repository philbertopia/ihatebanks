---
slug: lesson-10-wheel-strategy-mechanics
title: Wheel strategy mechanics
summary: >-
  The wheel strategy cycles between selling cash-secured puts and covered calls,
  collecting premium continuously whether or not you own the stock. Learn the
  full mechanics, when each phase activates, and what the backtests reveal about
  its real-world performance.
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
      Clear explanations of the wheel strategy mechanics, including how to
      select strikes for cash-secured puts and covered calls, and the
      practical reality of what happens when you get assigned.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Step-by-step breakdown of the wheel strategy's three phases with P/L
      examples and discussion of the risks that promotional content often omits.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Technical reference on cash-secured puts, covered call mechanics, and
      assignment rules that determine how the wheel transitions between phases.
disclaimer_required: true
lesson_number: 10
learning_objectives:
  - Describe the three phases of the wheel strategy and what triggers each transition.
  - Calculate the effective purchase price of stock after assignment from a cash-secured put.
  - Explain what a covered call is and how the strike is selected relative to the cost basis.
  - Identify the market conditions where the wheel performs well and where it struggles.
key_takeaways:
  - Phase 1 — sell cash-secured puts. Phase 2 — get assigned and own 100 shares. Phase 3 — sell covered calls. Then repeat.
  - The wheel profits in flat to slowly rising markets. It underperforms in strong uptrends (you cap your upside with covered calls) and it suffers in sharp crashes (you are long 100 shares).
  - The effective cost basis after assignment is the strike price minus all premiums collected. The goal is to sell covered calls above that basis.
  - Delta selection matters — lower delta puts mean less premium but a safer distance from assignment; higher delta means more premium but more frequent stock ownership.
  - The Wheel is not market-neutral. It is net long the stock. Understand this before deploying it.
---

## The wheel: an overview

The wheel strategy is a systematic approach to collecting options premium while managing a potential stock position. It cycles through two main phases indefinitely, which is why it is called the wheel.

**Phase 1:** Sell a cash-secured put on a stock you are willing to own.
**Phase 2:** If assigned (stock drops below the strike), you own 100 shares. Immediately sell a covered call.
**Phase 3:** If the covered call is exercised (stock rises above that strike), your shares are called away. Return to Phase 1.

Each phase collects premium. The wheel profits from premium accumulation over time, not from predicting price direction.

---

## Phase 1: The cash-secured put

A **cash-secured put** is a short put where you hold enough cash to buy the shares if assigned. Unlike a naked put (which uses margin), the cash-secured put has a clear worst-case: you purchase 100 shares at the strike price.

**Entry criteria:**
- Select a stock you genuinely want to own at the strike price — this is critical
- Target a delta around 0.20-0.40 (OTM, but not so far that the premium is negligible)
- Use monthly expirations at 30-45 DTE
- Collect enough premium to make the trade worthwhile relative to the cash tied up

**Example:**
- Stock: XYZ at $150
- Sell the $140 put (0.30 delta) expiring in 38 days for $2.50
- Cash reserved: $14,000 (to purchase 100 shares at $140 if assigned)
- Premium collected: $250

If the stock stays above $140 at expiration, the put expires worthless and you keep $250. You are free to repeat the process.

---

## Phase 2: Assignment and the cost basis

If XYZ falls below $140 at expiration, the put is assigned — you buy 100 shares at $140 per share.

**Your effective cost basis is not $140.** It is reduced by every premium you collected in Phase 1:

`effective cost basis = strike price - total premiums collected`

If you have run Phase 1 twice before assignment, collecting $2.50 each time:

`effective cost basis = $140 - $2.50 - $2.50 = $135.00`

You own 100 shares with an effective basis of $135, even though XYZ might be trading at $132 at the time of assignment. You are still underwater — but the premiums collected buffer the loss.

---

## Phase 3: The covered call

A **covered call** is selling a call option against the 100 shares you own. You collect premium and agree to sell your shares at the strike price if exercised.

**Entry criteria:**
- Select a strike at or above your effective cost basis — ideally above it by a margin
- Target 0.30-0.40 delta (closer to the money than the put, since you want to exit the position)
- Use monthly expirations at 30-45 DTE

**Example:**
- You own XYZ at effective basis $135; current price is $132
- Sell the $137 call (0.35 delta) expiring in 38 days for $2.10
- Premium collected: $210

If XYZ stays below $137: the call expires worthless, you keep $210, and repeat Phase 3.
If XYZ rises above $137: your shares are called away at $137. Your total exit is $137 per share plus all premiums collected.

---

## What makes the wheel work (and when it doesn't)

### Favorable conditions

- **Flat to slowly rising market** — puts expire worthless, covered calls expire worthless, premium accumulates
- **High IV** — elevated implied volatility means more premium collected on both legs
- **Stable, dividend-paying stocks** — fewer gap-down risks, predictable behavior

### Unfavorable conditions

- **Sharp rapid crashes** — you are assigned at the strike, and the stock continues falling well below your cost basis. You are long 100 shares through the decline with no hedge. The covered calls you sell cannot fully offset a large move down.
- **Strong sustained uptrends** — in Phase 3, your covered calls cap your upside. If XYZ rallies from $132 to $160, you miss the gain above $137.

**The key distinction from credit spreads:** The wheel is not defined-risk. You own the stock. In a crash, your loss is theoretically from the strike price to zero.

---

## The delta variants tested

The backtests on this site test three delta settings for the short put entry:

- **d20 (0.20 delta)** — conservative, rarely assigned, lower premium, higher win rate
- **d30 (0.30 delta)** — balanced, moderate assignment frequency, standard premium
- **d40 (0.40 delta)** — aggressive, more frequent assignment, higher premium, lower win rate

The delta setting determines the tradeoff between income (premium collected) and how often you end up owning the stock. Higher delta = more income, more stock exposure.

---

## Apply it

Open the [Strategies](/strategies) page and compare the three Wheel variants (d20, d30, d40). Look at each one's total return, Sharpe ratio, and max drawdown. Notice how the more aggressive delta setting (d40) typically shows higher absolute returns but also higher drawdown — consistent with the tradeoff between income and stock exposure. The OOS validation results reveal whether each variant's edge held up on data it had never seen during strategy development.
