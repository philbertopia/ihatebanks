---
slug: lesson-01-options-foundations
title: Options foundations
summary: >-
  Options are not just derivatives -- they are a fundamentally different way
  to participate in markets. This lesson builds a complete mental model: what
  options are, how they work mechanically, who the participants are, what
  moves the price, and why selling premium is a structurally advantaged
  position. No jargon without explanation. No shortcuts.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - options-basics
level: beginner
estimated_minutes: 20
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      The most practical options education available online. tastylive teaches
      options from the seller perspective -- probability, premium, and
      systematic mechanics -- which is exactly the framework used on this site.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Comprehensive written reference for options vocabulary, contract
      mechanics, payoff diagrams, and market structure. Use it to look up any
      term from this lesson in more depth.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Cboe created standardized listed options in 1973. Their content is the
      authoritative source on contract mechanics, settlement, and exercise.
disclaimer_required: true
lesson_number: 1
learning_objectives:
  - Explain what an options contract is, who the two counterparties are, and what each one gives up.
  - Define strike price, expiration date, and premium using concrete numerical examples.
  - Calculate the intrinsic and extrinsic value of an option given a stock price, strike, and premium.
  - Explain why the seller of an option has a structural probability advantage and what risk they accept.
  - Identify the three forces that move an option price and the direction each force pushes for buyers and sellers.
key_takeaways:
  - An option is a contract -- a buyer pays for a right, a seller collects that payment and accepts an obligation.
  - One contract controls 100 shares. A quoted premium of $2.00 means $200 per contract -- always multiply by 100.
  - Options lose value as time passes. The seller earns this decay every day. The buyer fights it.
  - Implied volatility, time, and the stock price all move the premium. The seller benefits from stability on all three.
  - The volatility risk premium -- the gap between implied and realized vol -- is the structural edge that systematic premium sellers exploit.
---

## The problem options solve

Before learning what an option is, it helps to understand what problem it was invented to solve.

Imagine you own 1,000 shares of a company worth $50 each -- a $50,000 position. You believe the stock will keep rising, but you are worried about a market crash in the next few months. You do not want to sell and miss the upside. But you also cannot afford to lose 30% in a sudden decline.

One solution: pay for insurance. Specifically, pay someone to agree that if the stock falls below $45, they will buy your shares at $45 regardless of where the price actually is. You pay a small premium for this protection. The other party collects that premium and accepts the obligation.

That is a put option. The buyer of insurance is the option buyer. The person writing the policy -- collecting premium and accepting the obligation -- is the option seller.

Options exist because both sides benefit. The buyer gets protection or leveraged exposure. The seller collects premium in exchange for a defined, manageable risk. The options market prices this exchange millions of times per day across thousands of underlying assets.

---

## What an options contract actually is

An **options contract** is a legally binding agreement that gives the buyer the right -- but never the obligation -- to buy or sell 100 shares of an underlying asset at a specific price, on or before a specific date.

Three things define every options contract:

**1. The underlying asset**
The stock, ETF, or index the option is written on. SPY (S&P 500 ETF), AAPL (Apple), QQQ (Nasdaq ETF). The option's value is derived from this asset -- hence the term derivative.

**2. The strike price**
The fixed price at which the right can be exercised. If a call has a $150 strike, the buyer can purchase 100 shares for $150 each regardless of where the stock trades. If the stock is at $175, that right is extremely valuable. If the stock is at $120, that right is worthless.

**3. The expiration date**
Every option has a finite life. After the expiration date, the contract ceases to exist entirely. Standard monthly options expire on the third Friday of the month. Once an option expires, it cannot be recovered -- it is gone. This clock is the most fundamental difference between options and stocks.

---

## The 100-share multiplier

This is the detail that trips up almost every beginner: **option premiums are quoted per share, but each contract represents 100 shares.**

If an option has a quoted premium of $3.50, the cost of one contract is:

`$3.50 x 100 shares = $350 per contract`

This multiplier applies to everything -- premium paid, profit, loss, and every risk metric. When you see a strategy that collected $1.80 in premium per trade, that is $180 per contract in real money.

The 100-share convention is a standardization decision made when listed options were created in 1973. It has not changed.

---

## Two types: calls and puts

### Call options

A **call option** gives the buyer the right to *purchase* 100 shares of the underlying at the strike price before expiration.

Calls benefit when the stock rises. If you own a call with a $150 strike and the stock rises to $180, you can exercise and buy 100 shares at $150 -- immediately worth $180 each. That is $3,000 of profit before subtracting what you paid for the call.

The seller of a call is obligated to sell 100 shares at the strike price if exercised. They collect the premium for accepting this obligation.

### Put options

A **put option** gives the buyer the right to *sell* 100 shares of the underlying at the strike price before expiration.

Puts benefit when the stock falls. If you own a put with a $150 strike and the stock falls to $110, you can exercise and sell 100 shares at $150 -- even though the market price is $110. That is $4,000 of value before subtracting what you paid.

The seller of a put is obligated to *buy* 100 shares at the strike price if exercised. They collect the premium for accepting this risk.

### A memory anchor

- **Call** = right to buy (you are calling in your order)
- **Put** = right to put your shares onto someone else (selling to them)

---

## What makes up the premium

When you see an option's market price (the premium), it is composed of two distinct components.

### Intrinsic value

Intrinsic value is the immediate, real-money value of exercising the option right now.

- For a call: `max(stock price - strike, 0)`
- For a put: `max(strike - stock price, 0)`

An option with positive intrinsic value is **in-the-money (ITM)**. An option with zero intrinsic value is **out-of-the-money (OTM)**. An option right at the strike is **at-the-money (ATM)**. Intrinsic value cannot be negative.

**Example:** Stock at $155, call strike at $140. Intrinsic value = $155 - $140 = $15 per share.

### Extrinsic value (time value)

Everything in the premium beyond intrinsic value is extrinsic value. It reflects:

1. **Time remaining** -- more time means more opportunity for the stock to move. Buyers pay for this optionality.
2. **Implied volatility** -- higher expected movement means more expensive options.

`extrinsic value = option premium - intrinsic value`

For an OTM option, the *entire premium is extrinsic value*. There is zero intrinsic value. When you sell an OTM option, you are selling pure time value. Every day that passes, that value erodes toward zero -- and the seller captures the decay.

**Worked example:**
- Stock at $148, put with $135 strike, trading at $2.10
- Intrinsic value: $0 (stock is above the strike -- the put is OTM)
- Extrinsic value: $2.10 (the full premium)
- If the stock stays above $135 until expiration, this entire $2.10 goes to the seller.

---

## The buyer and seller relationship

| | Option Buyer | Option Seller |
|---|---|---|
| Initial cash flow | Pays premium (money out) | Receives premium (money in) |
| Right or obligation? | Right -- can choose to exercise | Obligation -- must perform if exercised |
| Maximum gain | Unlimited (call) or substantial (put) | The premium collected |
| Maximum loss | The premium paid | Large or unlimited without a hedge |
| Needs stock to move to profit? | Yes -- needs a significant move | No -- profits from inaction and time |
| Benefits from time passing? | No -- time decay erodes their position | Yes -- time decay is daily income |
| Wants volatility to rise? | Yes -- higher vol raises their option value | No -- higher vol raises their obligation value |

The buyer is making a directional or volatility bet. They need something to happen -- a large price move, a volatility spike -- to profit. They are fighting time every day.

The seller has the opposite profile. They profit from nothing happening. Markets are calm on most days. Time passes on every day. This asymmetry is the structural foundation that makes systematic premium selling viable.

---

## Three forces that move an option price

An option's market price changes every minute. Three variables drive all of it:

**1. The stock price (delta exposure)**
When the stock rises, call options become more valuable and put options become less valuable, and vice versa. The sensitivity of an option to a $1 move in the underlying is called **delta**. An option with delta 0.30 gains or loses approximately $0.30 for every $1 the stock moves.

**2. Time passing (theta decay)**
Every calendar day that passes, the option loses extrinsic value. This is called theta decay. The decay is not linear -- it accelerates as expiration approaches. In the final 30 days before expiration, decay is fastest. For the seller, this is income accruing daily. For the buyer, it is a constant drain.

**3. Implied volatility (vega exposure)**
Options become more expensive when the market expects large moves (high implied volatility) and cheaper when it expects calm (low implied volatility). When a company announces earnings, or the VIX spikes on macro news, implied volatility rises -- and all options become more expensive regardless of stock price direction. For sellers, a vol spike after entry hurts. A vol decline after entry helps.

Understanding which direction each force moves your specific position is the core skill that all other options knowledge builds on.

---

## Why premium sellers have a structural edge

Research across decades of options data consistently shows one pattern: **implied volatility is systematically higher than the volatility that actually occurs.**

The market prices options as if stocks will move more than they do. Option buyers collectively overpay for the protection and leverage options provide. Option sellers collect that overpayment. The gap between what the market implies and what actually happens is called the **volatility risk premium**.

This premium exists because:
- **Buyers pay for certainty.** Knowing your maximum loss has value even if the loss never occurs.
- **Institutional mandates force hedging.** Pension funds and asset managers must buy protective puts regardless of price -- they have regulatory and fiduciary obligations.
- **Fear is overpriced.** In stressed markets, implied volatility spikes far beyond what actual movement justifies. The market panics, and option sellers who stay rational collect excessive premium.

The strategies on this site are built to systematically collect this premium across hundreds of trades, in liquid large-cap equities, with defined risk controls to absorb the periods when the market does move dramatically.

---

## What happens when an option expires

At expiration, every option resolves into one of two outcomes:

**Expires worthless (OTM):** The option has no intrinsic value. The buyer loses the full premium paid. The seller keeps the full premium received. No shares change hands. This is a complete win for the seller.

**Expires in-the-money (ITM):** The option is exercised. The buyer exercises their right. The seller is obligated to deliver or purchase shares at the strike price.

The strategies on this site are designed so that the vast majority of options expire worthless. The **win rate** metric on each strategy page is exactly this percentage: how often the option expired on the right side of the strike, and the seller kept the premium.

---

## A complete worked example

Here is a realistic trade from entry to expiry showing all the concepts in one place:

**Setup:**
- Stock: XYZ at $148
- You sell 1 put contract with a $135 strike, expiring in 38 days
- Premium received: $1.80 per share -- $180 total (1 contract x 100 shares)
- The $135 put is OTM by $13. XYZ must fall more than 8.8% for this put to have any intrinsic value at expiration.

**What you are betting:** XYZ stays above $135 for 38 days. You do not need it to rise -- you just need it not to crash.

**What the buyer is betting:** XYZ falls below $133.20 (breakeven: $135 strike - $1.80 premium) within 38 days.

**Scenario A -- XYZ closes at $141 at expiration:**
The $135 put is OTM. It expires worthless. You keep $180. The buyer loses $180. Clean win.

**Scenario B -- XYZ closes at $129 at expiration:**
The $135 put is ITM by $6. It is exercised. You are obligated to buy 100 shares at $135. Your net cost: $135 - $1.80 collected = $133.20. XYZ is trading at $129, so you have a $4.20 per share loss -- $420 total. This is why spreads are used: buying a $125 put would cap this loss at a fixed maximum.

**Scenario C -- You close at 50% profit:**
After 21 days, significant theta has decayed. You buy back the put for $0.90 to close. Profit: $1.80 - $0.90 = $0.90 per share ($90 per contract). You free up capital for the next trade.

Most trades in a well-run system follow Scenario A or C. Risk management (covered in Lesson 7) determines how Scenario B losses are bounded.

---

## Apply it

Go to the [Strategies](/strategies) page and find the **Put Credit Spread** family. Look at its win rate. Every percentage point of win rate represents trades that followed Scenario A -- the option expired worthless and the seller kept the full premium. The remaining percentage represents Scenario B trades where the stock moved through the strike.

Now ask: if the win rate is ~75%, but the 25% of losing trades are bounded by a defined spread structure, how does the math work out? That question leads directly to Lessons 8 and 9. Come back to this page after those lessons and see if the strategy metrics tell a different story.
