---
slug: wheel-d30-c30
title: Wheel D30 C30 Explainer
summary: >-
  Classic wheel on liquid stocks: sell a 30-delta cash-secured put, take
  assignment when it happens, then sell a 30-delta covered call until the
  shares are called away.
published_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - strategy-explainer
  - options
level: beginner
estimated_minutes: 12
references:
  - title: tastylive options education channel
    url: 'https://www.youtube.com/@tastylive'
    source: youtube
    why_it_matters: 'Practical, trade-focused context for Wheel D30 C30 Explainer.'
  - title: Investopedia options and derivatives hub
    url: 'https://www.investopedia.com/trading/options-and-derivatives-4689659'
    source: article
    why_it_matters: 'Baseline reference for definitions, payoff structure, and risk language.'
  - title: Cboe Options Institute
    url: 'https://www.cboe.com/optionsinstitute/'
    source: docs
    why_it_matters: Exchange-level educational material on options mechanics and risk.
disclaimer_required: true
strategy_key: stock_replacement|wheel_d30_c30
setup_rules:
  - Use the `top_50` liquid-stock universe with listed options.
  - Sell only monthly cash-secured puts with roughly 30-60 DTE.
  - Cap simultaneous CSP slots so the strategy does not over-concentrate on one regime.
entry_logic:
  - Open a new cash-secured put only when that symbol is not already in a wheel cycle.
  - Target puts near `-0.30` delta with acceptable spread and liquidity.
  - If assigned, switch the symbol into stock ownership and stop opening new puts there.
exit_logic:
  - Let the put expire; if it finishes ITM, accept assignment and own 100 shares.
  - Sell a covered call near `+0.30` delta with roughly 20-45 DTE against owned shares.
  - If the covered call expires ITM, shares are called away and the symbol returns to the CSP phase.
risk_profile:
  - Most drawdown comes from stock ownership after assignment, not from the initial put premium.
  - Upside is capped during the covered-call phase, so strong bull trends can create regret even when PnL stays positive.
  - Correlated assignments across multiple tech-heavy names can stack equity drawdown quickly.
common_failure_modes:
  - Selling too much downside in weak markets and becoming an involuntary bag-holder.
  - Re-entering fresh puts too aggressively after broad-market selloffs.
  - Mistaking premium collection for true downside protection; assignment is still long-stock risk.
---
## How it works
`wheel_d30_c30` is the clean, default wheel template in this repo. It sells a
roughly 30-delta cash-secured put, accepts assignment when the option expires
in the money, then sells a 30-delta covered call until the shares are called
away. The loop is mechanical by design: collect put premium, own stock when you
must, then collect call premium on the recovery or grind higher.

## What to watch
- Assignment clustering during broad selloffs
- Opportunity cost when strong winners are capped by covered calls
- Whether premium income is actually compensating for long-stock drawdown

## Use with site data
Use the strategy page to compare the default `wheel_d30_c30` run against the
other wheel variants. The most useful comparisons are:

- `wheel_d20_c30`: less aggressive put selling, lower assignment frequency
- `wheel_d40_c30`: more aggressive put selling, higher premium and higher assignment pressure
- `wheel_d30_c20`: same 30-delta put entry with a looser 20-delta covered call cap
