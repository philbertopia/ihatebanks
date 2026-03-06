---
slug: from-research-to-production-playbook
title: From research to production playbook
summary: >-
  A staged operating framework for moving options strategies from idea to
  controlled deployment without skipping validation and risk governance.
published_at: '2026-03-06'
updated_at: '2026-03-06'
author: I Hate Banks Editorial Team
tags:
  - article
  - production
  - workflow
  - risk-governance
  - systematic-trading
level: advanced
estimated_minutes: 15
references:
  - title: Meb Faber - systematic investing discussions
    url: 'https://www.youtube.com/@MebFaber'
    source: youtube
    why_it_matters: >-
      Practical perspective on turning quant ideas into repeatable investment
      process and governance.
  - title: NIST Risk Management Framework overview
    url: 'https://csrc.nist.gov/projects/risk-management/about-rmf'
    source: docs
    why_it_matters: >-
      Transferable governance concepts for staged controls, monitoring, and
      response that map well to strategy operations.
  - title: Alpaca Trading API docs
    url: 'https://docs.alpaca.markets/docs/trading/orders/'
    source: docs
    why_it_matters: >-
      Concrete operational reference for implementation details in production.
disclaimer_required: true
thesis: >-
  Research alpha and production alpha are different products; only a staged
  promotion process with hard gates can bridge them safely.
related_strategies:
  - openclaw_put_credit_spread|legacy_replica
  - openclaw_call_credit_spread|ccs_baseline
  - stock_replacement|wheel_d30_c30
  - intraday_open_close_options|baseline
---
## The core mistake: shipping a backtest, not a system
Most strategy failures are process failures. Teams validate signal logic, but
they do not validate operations, risk controls, or failure handling with the
same rigor. The result is predictable: impressive research that underperforms in
live use.

A production strategy is not only a model. It is model + execution + controls +
monitoring + incident response.

## As-of evidence for staged promotion logic
As of 2026-03-06, based on `dashboard/public/data/strategies.json`:

- `openclaw_put_credit_spread|legacy_replica`: return 299.52%, OOS pass.
- `openclaw_call_credit_spread|ccs_baseline`: return 142.29%, OOS pass.
- `stock_replacement|wheel_d30_c30`: return 164.93%, OOS pass.
- `intraday_open_close_options|baseline`: return 6496.89%, OOS fail.

This mix is exactly why promotion policy must be explicit. High in-sample
results do not bypass validation gates.

## Staged promotion framework
### Stage 0 - Research
- Hypothesis documented.
- Data lineage documented.
- Baseline backtest reproducible.

### Stage 1 - Validation
- Walk-forward OOS evaluation complete.
- Sensitivity tests for execution assumptions complete.
- Parameter stability reviewed.

### Stage 2 - Shadow/Paper
- Production-like order paths.
- Monitoring dashboards active.
- No-risk dry runs for incident response.

### Stage 3 - Limited Live
- Low risk budget.
- Hard kill switches.
- Weekly review cadence.

### Stage 4 - Scaled Live
- Stable behavior over pre-defined windows.
- No unresolved control incidents.
- Governance sign-off.

## Kill-switch and rollback design
Every stage needs objective stop conditions:

- drawdown threshold breach,
- fill-rate deterioration,
- slippage drift beyond expected bounds,
- validation drift in rolling windows,
- data quality anomaly detection.

Kill switches should reduce risk automatically before humans debate causes.
Rollback should be scripted and reversible.

## Failure modes in production transition
- **Promotion by enthusiasm** instead of policy.
- **No ownership mapping** for operational incidents.
- **Alert fatigue** from noisy monitoring design.
- **Configuration drift** between backtest and live deployment.

A good playbook is specific about who acts, when, and with what authority.

## Practical implementation checklist
1. Write a promotion matrix with mandatory criteria.
2. Tag every strategy with stage and max risk budget.
3. Keep deployment config in version control.
4. Run monthly postmortems for both incidents and near-misses.
5. Demote strategies automatically when stability criteria are breached.

Production quality is less about predicting markets and more about controlling
the error surface when markets surprise you.
