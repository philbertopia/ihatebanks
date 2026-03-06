---
slug: lesson-04-greeks-in-practice
title: Greeks in practice
summary: >-
  Delta, theta, gamma, and vega tell you how an option's price responds to
  everything that changes in the market. Learn what each one means for a
  short-premium strategy and which Greeks work for you versus against you.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - options-basics
level: intermediate
estimated_minutes: 18
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      tastylive built their entire framework around managing Greeks in live
      trades. Their videos on theta management and delta-neutral positioning
      are directly applicable to credit spread strategies.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Clear definitions of all four major Greeks with visual examples of how
      option price sensitivity changes as market conditions shift.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Technical reference for how Greeks are calculated and used in risk
      management at an institutional level.
disclaimer_required: true
lesson_number: 4
learning_objectives:
  - Interpret a delta value and estimate how an option will move when the stock moves $1.
  - Explain theta as daily premium decay and calculate approximately what a position earns per day.
  - Describe why gamma risk increases near expiration and near the strike price.
  - Explain what vega means and why credit spread sellers prefer lower vega exposure.
key_takeaways:
  - Delta measures how much the option price moves for a $1 stock move. Short OTM options have low delta — small moves hurt them only a little.
  - Theta is your daily income as a short seller. An option with theta of -0.05 loses $5 per day — that value flows to the seller.
  - Gamma is the risk that accelerates near expiration. It makes winning positions dangerous to hold too long.
  - Vega is exposure to implied volatility. A vol spike hurts short sellers even when the stock barely moves.
  - Managing a credit spread means balancing positive theta against negative gamma and vega.
---

## What the Greeks are

The Greeks are sensitivity measurements. Each one answers: *if this one thing changes, how much does the option's price change?*

They isolate a single variable — price, time, speed of price change, or volatility. Together they give you a complete picture of an option's risk profile under any market condition.

---

## Delta (Δ)

**Delta measures how much the option price changes for every $1 move in the stock.**

- A call option has delta between 0 and +1
- A put option has delta between -1 and 0
- A delta of 0.30 means: if the stock rises $1, the option price rises approximately $0.30

**Example:** You are short a put with delta -0.25. The stock rises $2. Your short put loses approximately $0.50 in value — which is a gain for you, since you are the seller.

### Delta as probability

Delta also serves as a rough estimate of the probability the option expires in-the-money. A 0.25 delta option is roughly 25% likely to be ITM at expiration — meaning there is approximately a 75% chance it expires worthless and you keep the full premium.

This is why the strategies here target short strikes in the **0.20-0.30 delta range** — that provides roughly a 70-80% probability of the option expiring worthless.

### Delta for spreads

A credit spread has a net delta that is the sum of the short and long legs. Because the long option partially offsets the short, the net delta is lower than a naked short option — which means the position is less sensitive to directional moves.

---

## Theta (Θ)

**Theta measures how much the option price decreases each calendar day due to time passing.**

Theta is always negative for option buyers (they lose time value each day) and positive for sellers (they gain as the contract decays toward zero).

**Example:** A short put position with theta of -0.04 means the option loses $4 of value per day (per 1-contract position covering 100 shares). That $4 accrues to the seller each day the position is open.

Theta decay is not uniform:
- Far-dated options (90+ DTE) decay slowly — small daily theta
- Near-dated options (30 DTE and under) decay much faster — large daily theta
- The final 2-3 weeks before expiration see the most aggressive decay

**For systematic credit sellers, theta is the primary income source.** Every day the market stays stable, you collect. This is why high win rates are possible — the strategy doesn't need the stock to do anything in particular, just not do something extreme.

---

## Gamma (Γ)

**Gamma measures how fast delta changes as the stock price moves.**

High gamma means the option's delta (and therefore its price) changes rapidly with stock movement. Low gamma means the relationship is more stable.

Gamma is highest when:
- The option is at-the-money (ATM) — right at the strike
- Expiration is close — low DTE

This creates the core tension in short-premium trading: as the option approaches expiration, theta decay accelerates (good for sellers), but gamma also increases (bad for sellers). A short option that was safely OTM three weeks ago can become a serious problem in its final days if the stock drifts toward the strike.

**Practical consequence:** Many credit spread strategies close positions at **50% of max profit** rather than holding to expiration. This captures the bulk of theta decay while exiting before the dangerous gamma zone in the final two weeks.

---

## Vega (ν)

**Vega measures how much the option price changes for a 1% change in implied volatility.**

Options become more expensive when implied volatility (IV) rises, because the market is pricing in larger potential moves. This benefits buyers and hurts sellers.

- **When IV drops after you sell:** The option loses value → you profit (even if the stock barely moved)
- **When IV spikes after you sell:** The option gains value → you lose (even if the stock barely moved)

This is why many sellers prefer to enter when implied volatility is elevated — you collect more premium upfront, and any subsequent IV decline (which often follows market fear spikes) adds additional profit to the position beyond normal theta decay.

---

## The Greek profile of a credit spread

A standard put credit spread (short OTM put + long further OTM put) has this profile:

| Greek | Sign | What it means for you |
|---|---|---|
| Delta | Positive | You benefit when the stock rises or holds flat |
| Theta | Positive | You earn decay every day the position is open |
| Gamma | Negative | You are hurt when the stock moves sharply toward the strike |
| Vega | Negative | You are hurt when implied volatility spikes |

**The core tension:** theta works for you every day, but gamma and vega work against you when markets get volatile. Managing this means keeping position sizes reasonable, having defined strikes on both legs (so losses are bounded), and not holding into the high-gamma zone near expiration.

---

## Apply it

Open the [Strategies](/strategies) page and look at the Sharpe ratio for any Put Credit Spread variant. Sharpe measures return per unit of risk — a high Sharpe means consistent returns relative to volatility. The Greeks explain why: when theta is the primary income source and gamma is bounded by the long put leg, the return stream is smoother than strategies that require big directional moves to profit.
