---
slug: lesson-17-small-account-ditm-calls-and-atr-rolling
title: Small-account DITM calls and ATR rolling
summary: >-
  A practical small-account framework: avoid low-payout spread structures when
  one loser resets weeks of progress, favor deep ITM calls with low extrinsic
  value, and use 1 ATR roll-for-credit checkpoints to reduce basis.
published_at: '2026-03-09'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - strategy
  - small-accounts
level: advanced
estimated_minutes: 20
references:
  - title: How To Trade Options With Just $1,000 (Real Examples Inside)
    url: 'https://www.youtube.com/watch?v=dF-HoG8aikc'
    source: youtube
    why_it_matters: >-
      This lesson is built from the video's small-account critique: avoid poor
      payoff geometry, target about 80 delta, and roll only when the next call
      can be opened for a credit after a 1 ATR move.
  - title: The Options Institute
    url: 'https://www.cboe.com/oi/'
    source: docs
    why_it_matters: >-
      Useful reference for listed-options mechanics, pricing, and the tradeoffs
      between long premium, stock replacement, and spread structures.
  - title: Measure Volatility With Average True Range
    url: 'https://www.investopedia.com/articles/trading/08/average-true-range.asp'
    source: article
    why_it_matters: >-
      ATR gives a concrete volatility unit for sizing moves, setting roll
      checkpoints, and understanding why a $1 move means different things on
      different symbols.
disclaimer_required: true
lesson_number: 17
learning_objectives:
  - Explain why small-account buying power and small-account risk are not the same thing.
  - Compare a low-payout bull put credit spread with a deep ITM long call using intrinsic and extrinsic math.
  - Calculate extrinsic percentage and explain why 80-delta calls behave more like stock than cheaper lower-delta calls.
  - Describe the 1 ATR roll-for-credit process and how repeated rolls reduce cost basis.
key_takeaways:
  - Uhl's critique is about tiny-account trade geometry, not a universal claim that all credit spreads are bad.
  - Deep ITM calls concentrate premium in intrinsic value, which reduces theta drag relative to cheaper ATM or OTM calls.
  - 'The 0.80 delta area is the practical sweet spot: high stock-like participation without paying for 100 shares outright.'
  - A 1 ATR move can be used as a mechanical checkpoint to sell the now-deeper ITM call and reopen a new about-0.80-delta call for a credit.
  - On a $1,000 account, position sizing is still the hard limit. Even a defined-risk long call can be oversized if one contract dominates the account.
---

## The real small-account problem

The useful question is not "Can my broker approve this trade?" The useful
question is "Can this account survive the trade?"

That distinction is the center of the video's critique. A trade that fits
inside a $1,000 account can still be a terrible small-account trade if:

- one losing position erases multiple winners,
- one contract consumes most of the account,
- the structure pays mostly time value instead of real directional exposure, or
- the underlying is so expensive that normal daily movement blows through the
  risk budget.

This lesson is about **trade geometry**. It is not a blanket statement that a
strategy is always good or always bad in every account size.

---

## Why the spread example breaks down

The video attacks a common small-account example: a **bull put credit spread**
that risks far more than it can make.

Example from the transcript:

- Spread width: `$2.00`
- Credit collected: `$0.32`
- Max profit: `$32`
- Max loss: `($2.00 - $0.32) x 100 = $168`

That creates a simple but brutal asymmetry:

- One full loser costs `$168`
- One full winner makes only `$32`
- It takes **more than five perfect winners** to recover one max-loss trade

That is the argument. If the account is tiny, there is no diversification
buffer. A trader can post a high win rate and still lose money because the
loss distribution is too ugly.

Important nuance: this does **not** mean every credit spread is invalid. It
means a tiny account should be suspicious of structures where dollar risk is
many times larger than dollar reward and the account is too small to spread the
risk across many independent trades.

---

## Why deep ITM calls are different

Uhl's preferred alternative is the **deep in-the-money long call**, usually in
the **0.80 delta** area.

The reason is not magic. It is just option composition.

### The SoFi comparison

The transcript walks through two calls on SoFi with the stock around `$30.95`.

**Deep ITM call**
- Strike: `$28.00`
- Ask: `$3.60`
- Intrinsic value: `$30.95 - $28.00 = $2.95`
- Extrinsic value: `$3.60 - $2.95 = $0.65`
- Extrinsic percentage: about `18%`

**Cheaper lower-delta call**
- Strike: `$30.50`
- Ask: `$1.96`
- Intrinsic value: `$30.95 - $30.50 = $0.45`
- Extrinsic value: `$1.96 - $0.45 = $1.51`
- Extrinsic percentage: about `77%`

The cheaper option has a lower cash outlay, but most of what you are buying is
time value. The deep ITM option costs more upfront, yet much more of that price
is actual intrinsic exposure.

That is why the lesson matters:

- the deep ITM call behaves more like stock,
- the theta drag is smaller relative to price paid,
- and a large share of the premium is not just "rent."

At roughly 0.80 delta, a `$1` move in the stock translates to about `$0.80` of
option movement. You get most of the stock's move without paying for 100 shares
outright.

---

## The 80-delta framework

This small-account version of stock replacement uses a stricter filter than
"buy any bullish call that looks affordable."

The transcript's framework is:

1. Target **delta at or above 0.80**
2. Keep **extrinsic value below about 20%** of premium
3. Prefer liquid contracts where the spread is not eating the edge
4. Favor **lower-priced underlyings**, roughly the `$20-$50` zone, so one
   contract does not consume the full account

This is why the video explicitly pushes back on trading something like QQQ in a
`$1,000` account. A high-priced underlying can make even a "good" option
structure impossible to size correctly.

On this site, that logic overlaps with the
[Stock replacement strategy](/education/lessons/lesson-13-stock-replacement):
high-delta calls, low extrinsic value, and trend discipline. The difference is
that the small-account version is even more obsessed with contract cost and
concentration.

---

## The 1 ATR roll-for-credit workflow

The most distinctive part of the transcript is the management rule.

Instead of simply holding the original call until expiration, Uhl uses
**Average True Range (ATR)** as a mechanical checkpoint.

### The rule

When the underlying advances by **1 ATR** from the last entry or roll point:

1. Sell the current call
2. Buy a new call closer to the money with delta reset back near `0.80`
3. Only do the roll if the package produces a **net credit**

The intuition is straightforward:

- your original 0.80-delta call often becomes a 0.90-plus-delta call after a
  strong move,
- that deeper ITM contract has less remaining gamma expansion,
- resetting back toward 0.80 delta lets you take cash out while keeping the
  bullish position alive.

If the roll takes in a credit, that credit lowers the effective basis of the
trade. Repeat that process enough times and the original capital at risk can
shrink materially.

The transcript treats this as a hard rule: **if the roll is a debit, you did it
wrong**. The purpose of the roll is not to pay more money for the same idea. It
is to harvest part of the move and keep the remaining exposure capital
efficient.

---

## The hard limit: position sizing

The video is not romantic about the constraints of a `$1,000` account.

If the risk rule is **5% of account per trade**, the maximum loss budget is
only `$50`.

That sounds clean on paper, but the reality is ugly:

- an 80-delta option on a `$200` stock can lose `$50` on a very small
  underlying move,
- one contract can still dominate the account,
- and there is little room for diversification or error.

That is why the transcript repeatedly comes back to lower-priced names and why
it argues that "professional" position sizing only becomes practical at a much
larger account size.

So the correct reading is not "deep ITM calls solve small-account risk." The
correct reading is:

- they may solve the **payoff-shape** problem better than a tiny low-credit
  spread,
- but they do **not** solve the **capital base** problem.

For that, read [Risk management basics](/education/lessons/lesson-07-risk-management-basics)
and [Small-account options: capital efficiency versus real risk](/education/articles/small-account-options-capital-efficiency-vs-risk).

---

## Relation to strategies on this site

The transcript maps most directly to the **Stock Replacement** family and the
small-account DITM variants in the strategy catalog.

Use this lesson to understand three layers:

- **Entry logic:** high delta, low extrinsic, cheaper underlyings
- **Management logic:** 1 ATR roll checkpoints for credit
- **Reality filter:** avoid pretending a one-contract account is "well sized"

One important implementation note: the current public stock-replacement
variants on the site reflect the **entry-side** DITM logic well, but the
transcript's **1 ATR roll-for-credit** technique is best understood as a
management overlay rather than a separately isolated performance stat in the
dashboard.

---

## Apply it

Open the [Strategies](/strategies) page and compare the stock-replacement
variants with the small-account DITM notes in this lesson.

Then ask four blunt questions before taking any trade:

1. Is the option mostly intrinsic or mostly rent?
2. If I lose once, how many winners do I need to recover?
3. Can this underlying move 1 ATR without blowing through my account risk?
4. If the trade works, do I have a mechanical roll-for-credit plan?

That checklist is the real lesson. Small accounts do not need more clever
structures. They need cleaner math.
