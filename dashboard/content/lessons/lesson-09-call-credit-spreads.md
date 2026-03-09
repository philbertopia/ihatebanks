---
slug: lesson-09-call-credit-spreads
title: Call credit spreads
summary: >-
  The call credit spread is the mirror image of the put credit spread — same
  structure, opposite market assumption. Learn how it is built, when to use
  it, and how it complements put spreads in a systematic portfolio.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - strategy
level: intermediate
estimated_minutes: 16
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      Comprehensive content on bear call spreads, when to use them relative to
      put spreads, and how to combine them into iron condors for
      market-neutral premium selling.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Step-by-step construction and payoff diagrams for call credit spreads
      with worked examples at different stock prices.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Technical reference for vertical call spreads, margin treatment, and
      how call assignment differs from put assignment at expiration.
disclaimer_required: true
lesson_number: 9
learning_objectives:
  - Construct a call credit spread and calculate net credit, max profit, max loss, and breakeven.
  - Explain the market assumption behind a call credit spread and when it is appropriate.
  - Compare a call credit spread to a put credit spread and identify the key differences.
  - Describe how the backtested call credit spread strategy differs from the put credit spread in entry and management.
key_takeaways:
  - A call credit spread is a short OTM call plus a long further OTM call — you profit when the stock stays below the short call strike.
  - The market assumption is bearish to neutral — the stock needs to stay flat or decline for the position to profit.
  - Structure and math are identical to the put credit spread, just inverted — same defined risk, same theta decay, opposite delta.
  - Call credit spreads pair naturally with put credit spreads to form iron condors — positions that profit when the stock stays in a range.
  - The backtested call credit spread strategy uses the same discipline as the put spread but with upside strikes and a bearish trend filter.
---

## What a call credit spread is

A **call credit spread** — also called a bear call spread — is a two-leg options position constructed by:

1. **Selling** (short) an out-of-the-money call at a lower strike
2. **Buying** (long) a further out-of-the-money call at a higher strike

Both legs use the same underlying and expiration. You collect a net credit because the call you sell is worth more than the call you buy. The position profits when the stock stays below the short call strike at expiration.

---

## Construction example

Stock: XYZ at $150
Expiration: 38 days away (monthly)

| Leg | Action | Strike | Premium |
|---|---|---|---|
| Short call | Sell | $160 | +$1.90 |
| Long call | Buy | $165 | -$0.65 |
| **Net credit** | | | **+$1.25** |

You collect $1.25 per share, or **$125 per contract**, when you open the position.

---

## Profit and loss at expiration

The spread width is $5 ($165 - $160). The credit received is $1.25.

| Stock price at expiration | What happens | P/L per contract |
|---|---|---|
| Below $160 | Both calls expire worthless | +$125 (max profit) |
| $160 | Short call at the money | +$125 (max profit) |
| $161.25 | Breakeven | $0 |
| $165 | Short call worth $5, long call worth $0 | -$375 (max loss) |
| Above $165 | Both calls in the money | -$375 (max loss) |

**Max profit:** $125
**Max loss:** ($5.00 - $1.25) × 100 = **$375**
**Breakeven:** $160 + $1.25 = **$161.25**

The stock can rise $11.25 (from $150 to $161.25) before the position starts losing money.

---

## The market assumption

The call credit spread profits from two conditions:
1. **The stock stays flat or falls** — the short call expires worthless and you keep the premium
2. **Implied volatility falls** — the short call loses value from IV compression, adding to profits

It loses when the stock rises significantly above the short call strike. Unlike short puts (which lose in a crash), short calls lose in a rapid rally — different risk profile, different regime sensitivity.

---

## Put spreads vs. call spreads: key differences

| | Put Credit Spread | Call Credit Spread |
|---|---|---|
| Short strike | Below current price (OTM put) | Above current price (OTM call) |
| Market assumption | Bullish to neutral — stock stays up | Bearish to neutral — stock stays down |
| Delta | Positive — benefits from rising stock | Negative — benefits from falling stock |
| Risk scenario | Rapid market crash | Rapid market rally |
| When to use | Uptrend or neutral market | Downtrend or overextended rally |

Both strategies profit from the same theta decay mechanism. The choice between them is primarily about directional bias and market regime.

---

## Iron condors: combining both spreads

When you combine a put credit spread with a call credit spread on the same underlying and expiration, you create an **iron condor** — a position that profits when the stock stays within a defined range.

**Example:**
- Short put at $140, long put at $135 → collect $1.35
- Short call at $160, long call at $165 → collect $1.25
- Total credit: $2.60 per share ($260 per contract)
- Stock must stay between $138.65 and $161.25 to keep full credit

Iron condors reduce directional exposure and collect premium from both sides. They require the market to stay calm, which makes them vulnerable to large moves in either direction.

That does not automatically make them a beginner small-account strategy. A same-day iron condor can look cheap in buying-power terms while concentrating most of the account into one gamma-sensitive session. [Small-account options: capital efficiency versus real risk](/education/articles/small-account-options-capital-efficiency-vs-risk) explains why that distinction matters.

---

## Entry criteria for the backtested call credit spread

The Call Credit Spread strategies on this site use:

**Strike selection:**
- Short call at approximately **0.20-0.30 delta** (above the current price)
- Long call 5 strikes further OTM

**Timing:**
- 30-45 DTE, monthly expirations only
- Trend filter: enter short-call (bearish) positions only when the underlying shows signs of extended rally or bearish trend

**Credit filter:**
- Same minimum credit-to-width ratio as put spreads
- Trades are skipped in strongly bullish trending markets where the short call strike is at high risk

**Management:**
- Same profit target (50% of max profit) and stop loss (2x premium received) as put spreads
- 21 DTE time stop applies identically

---

## When call spreads outperform put spreads

Call credit spreads tend to outperform in:
- Extended overbought markets where upside momentum is exhausted
- Periods of elevated call skew (calls are overpriced relative to puts)
- Bearish or sideways markets where put spreads carry more directional risk

Put credit spreads tend to outperform in:
- Uptrending markets with low volatility
- Post-crash recoveries where put skew is elevated (puts are expensive relative to calls)
- Periods of strong economic expansion

The strategies on this site are run independently — the put and call spread results can be compared directly to see which regime each favors.

## Apply it

Open the [Strategies](/strategies) page and compare the Put Credit Spread and Call Credit Spread families side by side. Look at their performance over the 5-year backtest period that included both bull and bear markets. Does one consistently outperform the other, or do they perform well in different periods? This comparison reveals how directional bias in each strategy's entry filter affects returns across different market regimes.
