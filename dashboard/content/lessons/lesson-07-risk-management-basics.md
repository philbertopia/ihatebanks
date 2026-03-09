---
slug: lesson-07-risk-management-basics
title: Risk management basics
summary: >-
  Position sizing, portfolio heat, and knowing when to stop are what separate
  a durable systematic strategy from one that blows up in a bad month.
  Risk management is not a constraint on returns — it is how returns survive.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - lesson
  - education
  - risk
level: intermediate
estimated_minutes: 18
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: >-
      tastylive's portfolio heat, beta weighting, and position sizing
      frameworks are directly applicable to how the strategies on this site
      are sized and managed.
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: >-
      Clear explanations of position sizing, Kelly criterion concepts, and how
      drawdown relates to recovery time — the math behind risk limits.
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: >-
      Exchange-level documentation on margin requirements, risk management
      regulations, and how brokers assess portfolio risk.
disclaimer_required: true
lesson_number: 7
learning_objectives:
  - Explain position sizing and calculate a maximum trade size given a portfolio size and risk limit.
  - Define portfolio heat and explain why total exposure matters more than individual trade risk.
  - Describe when to take a loss and close a position early versus letting it run to expiration.
  - Explain what a kill switch is and why systematic strategies need one.
key_takeaways:
  - Position sizing is the single most important risk control. A strategy with good sizing survives bad runs. The same strategy with poor sizing can blow up on a single trade.
  - Portfolio heat is the total capital at risk across all open positions. Keeping it below 8-10% of portfolio value limits the damage from correlated crashes.
  - Credit spreads have defined max loss — use that number to size positions, not the premium collected.
  - Close losing positions at 2x the premium received (stop loss), not at max loss. Letting losers run to maximum damage destroys accounts.
  - A kill switch pauses the strategy when recent performance falls below a statistical threshold. It protects against regime changes where the strategy's edge has temporarily disappeared.
---

## Why risk management is the strategy

Most traders think about risk management as something that happens *after* they build a strategy — a set of rules to limit damage. The better mental model is that risk management *is the strategy*.

Options sellers have a structural edge: implied volatility overprices options, theta decays in their favor, and time is on their side. But that edge produces small, consistent wins interrupted by occasional large losses. Without risk management, the large losses erase the accumulated wins. With it, the wins compound over time.

---

## Position sizing

Position sizing determines how much of your account you risk on any single trade. For credit spreads, the maximum risk per trade is:

`max loss = (spread width - credit received) x 100`

**Example:** A $5-wide put credit spread that collects $1.50 in premium has a max loss of ($5.00 - $1.50) x 100 = **$350 per contract**.

To size this correctly, decide what percentage of your account you will risk per trade. A reasonable baseline is **1-2% of portfolio per position**.

**Example:** $50,000 account, 2% risk limit per trade = $1,000 max risk per position. You could trade 2 contracts of the above spread ($350 x 2 = $700 risk, under the $1,000 limit).

Small-account traders often misunderstand this when buying short-dated calls. The premium is capped, but the position can still be account-lethal if it is sized like a lottery ticket instead of a risk budget. [How long-call leverage really works](/education/articles/how-long-call-leverage-really-works) shows why "limited loss" does not mean "safe sizing."

The same logic applies to "small-account" spread examples. A trade that requires only `$700` of buying power in a `$1,000` account is not conservative; it is risking most of the account on one position. [Small-account options: capital efficiency versus real risk](/education/articles/small-account-options-capital-efficiency-vs-risk) reframes that distinction.

### Why sizing matters more than win rate

A strategy with a 75% win rate but terrible sizing can still go bankrupt. If you risk 20% of your account on each trade, a streak of 4 losses (which will happen in any high-win-rate strategy eventually) destroys 60%+ of your account. Recovery from a 60% drawdown requires a 150% gain just to break even.

Position sizing is not conservative thinking — it is the math of survival.

---

## Portfolio heat

**Portfolio heat** is the total maximum loss across all open positions simultaneously.

Even well-sized individual positions can create dangerous aggregate exposure when:
- Multiple positions are in correlated underlyings (if the S&P falls 10%, all long-delta positions lose at once)
- Multiple short puts in similar sectors assign simultaneously during a market dislocation
- Margin requirements expand in a volatility spike, creating liquidity pressure

A reasonable heat limit is **8-10% of total portfolio value**. If your open positions have a combined max loss of more than that, you are overexposed to a correlated crash.

The strategies on this site target a diversified universe of large-cap names precisely to reduce correlation — but correlation spikes during market stress regardless of underlying selection.

---

## When to close a losing position

**The worst risk management mistake is holding a losing credit spread to maximum loss.**

Credit spreads have a natural tendency: when the stock moves through your short strike, losses accelerate rapidly. The time decay that was working for you reverses — now gamma and negative delta are working against you.

The standard discipline:
- **Profit target:** Close at 50% of max profit (premium collected). This exits at the steepest part of the theta curve while avoiding gamma risk near expiry.
- **Loss limit:** Close at 2x the premium received. If you collected $1.50, close if the position price reaches $3.00 (a $1.50 net loss). This prevents small losers from becoming catastrophic ones.

**Example:** You collect $1.50 on a spread. Your profit target is $0.75 debit to close. Your stop loss is $3.00 debit to close. The asymmetry is intentional — most positions reach the profit target, and the stop loss caps the damage on the minority that go wrong.

---

## Correlation risk

During normal markets, a diversified portfolio of short puts across different sectors behaves roughly independently. During a crash or major macro event, correlation spikes — everything falls at once.

The 2020 COVID crash is the textbook example: virtually every stock fell simultaneously in February-March 2020. A portfolio of short puts in 20 different names all moved to max loss within days.

Mitigation strategies:
- Maintain portfolio heat limits (above) so simultaneous losses are bounded
- Include some defensive names or ETFs that are less correlated to growth stocks
- Be aware that the worst scenarios for short-put strategies are rapid, broad market declines — not slow, gradual ones

---

## The kill switch

A **kill switch** is a rule that pauses trading when recent performance falls below a threshold. It exists to protect against regime changes — periods where the market is behaving in a way that the strategy was not designed for.

An example kill switch rule: *if the last 30 trades have a negative expectancy (average loss), pause new entries until conditions normalize.*

Kill switches prevent a strategy from doubling down into a losing regime. The 2022 bear market, for example, was persistently hostile to short-put strategies — a kill switch would have limited exposure during the worst months.

The strategies on this site include kill switch parameters in their configuration. The backtest results show performance both with and without these protections applied.

---

## Apply it

Then read [How long-call leverage really works](/education/articles/how-long-call-leverage-really-works) and compare a defined-risk premium-selling position with a short-dated long call that can still lose 100% of premium.

Open any strategy's detail page in the [Strategies](/strategies) section and find the **max drawdown** metric. Now calculate: if you traded this strategy at 1% risk per trade with a portfolio heat cap of 8%, what is the worst-case dollar loss from the max drawdown period? Compare that to a scenario where you traded without sizing limits. The difference illustrates why position sizing is not optional — it is the feature that makes the strategy survivable.
