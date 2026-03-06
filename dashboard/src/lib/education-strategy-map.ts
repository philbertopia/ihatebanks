export const VARIANT_TO_EDUCATION_SLUG: Record<string, string> = {
  legacy_replica: "pcs-legacy-replica",
  pcs_vix_optimal: "pcs-vix-optimal",
  ccs_baseline: "ccs-baseline",
  ccs_defensive: "ccs-defensive",
  wheel_d30_c30: "wheel-d30-c30",
  wheel_d20_c30: "wheel-d20-c30",
  wheel_d40_c30: "wheel-d40-c30",
  baseline: "intraday-baseline",
  conservative: "intraday-conservative",
  full_filter_20pos: "stock-replacement-full-filter-20pos",
};

export const STRATEGY_VARIANT_TO_EDUCATION_SLUG: Record<string, string> = {
  "openclaw_put_credit_spread|legacy_replica": "pcs-legacy-replica",
  "openclaw_put_credit_spread|pcs_vix_optimal": "pcs-vix-optimal",
  "openclaw_call_credit_spread|ccs_baseline": "ccs-baseline",
  "openclaw_call_credit_spread|ccs_defensive": "ccs-defensive",
  "stock_replacement|wheel_d30_c30": "wheel-d30-c30",
  "stock_replacement|wheel_d20_c30": "wheel-d20-c30",
  "stock_replacement|wheel_d40_c30": "wheel-d40-c30",
  "intraday_open_close_options|baseline": "intraday-baseline",
  "intraday_open_close_options|conservative": "intraday-conservative",
  "stock_replacement|full_filter_20pos":
    "stock-replacement-full-filter-20pos",
};

export function getEducationSlugForStrategy(
  strategyId: string | undefined,
  variant: string | undefined
): string | undefined {
  if (!strategyId || !variant) return undefined;
  return (
    STRATEGY_VARIANT_TO_EDUCATION_SLUG[`${strategyId}|${variant}`] ??
    VARIANT_TO_EDUCATION_SLUG[variant]
  );
}
