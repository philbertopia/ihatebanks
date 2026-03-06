"use client";
import Link from "next/link";
import Image from "next/image";
import { useBacktestStrategyComparison, useStrategyCatalog } from "@/lib/api";

const FEATURED_FAMILIES = [
  {
    key: "openclaw_put_credit_spread",
    label: "Put Credit Spread",
    tagline: "Sell OTM puts. Collect premium. Profit when markets stay flat or rise.",
    color: "border-purple-700 bg-purple-900/20",
    badge: "bg-purple-900/50 text-purple-300",
    variants: ["legacy_replica"],
  },
  {
    key: "openclaw_call_credit_spread",
    label: "Call Credit Spread",
    tagline: "Sell OTM calls. Collect premium. Profit when markets stay flat or fall.",
    color: "border-rose-700 bg-rose-900/20",
    badge: "bg-rose-900/50 text-rose-300",
    variants: ["ccs_baseline"],
  },
  {
    key: "intraday_open_close_options",
    label: "Intraday Open-Close Options",
    tagline: "Open after the bell, close same day. High-turnover directional options engine.",
    color: "border-cyan-700 bg-cyan-900/20",
    badge: "bg-cyan-900/50 text-cyan-300",
    variants: ["baseline"],
  },
];

export default function HomePage() {
  const { data: strategies } = useBacktestStrategyComparison();
  const { data: catalog } = useStrategyCatalog();

  const byStrategyVariant = Object.fromEntries(
    (strategies ?? []).map((s) => [`${s.strategy_id}|${s.variant}`, s])
  );
  const catalogByStrategyVariant = Object.fromEntries(
    (catalog ?? []).map((c) => [`${c.strategy_id}|${c.variant}`, c])
  );

  const familyStats = FEATURED_FAMILIES.map((f) => {
    const rows = (strategies ?? []).filter((s) => s.strategy_id === f.key);
    const best = rows.reduce<typeof rows[0] | null>((acc, r) => {
      if (!acc) return r;
      return (r.latest_total_return_pct ?? 0) > (acc.latest_total_return_pct ?? 0) ? r : acc;
    }, null);
    const topVariant = f.variants[0];
    const strategyVariantKey = `${f.key}|${topVariant}`;
    const featured = byStrategyVariant[strategyVariantKey] ?? best;
    const catalogEntry = catalogByStrategyVariant[strategyVariantKey];
    return { ...f, featured, catalogEntry };
  });

  const totalStrategies = strategies?.length ?? 0;
  const passCount = strategies?.filter((s) => s.oos_pass_validation).length ?? 0;

  return (
    <div className="max-w-4xl mx-auto py-10 sm:py-16 px-4 sm:px-6">
      <div className="mb-12 sm:mb-16 text-center">
        <div className="mb-5 flex justify-center">
          <Image
            src="/images/ihatebanks-v2.png"
            alt="I Hate Banks artwork"
            width={1200}
            height={1200}
            priority
            className="w-full max-w-[11rem] sm:max-w-[13rem] md:max-w-[15rem] h-auto rounded-xl"
          />
        </div>
        <div className="inline-block bg-blue-900/30 border border-pink-500/60 text-pink-200 text-xs font-semibold px-3 py-1 rounded-full mb-4 shadow-[0_0_0_1px_rgba(236,72,153,0.2)]">
          Systematic · Backtested · Transparent
        </div>
        <p className="text-base sm:text-xl text-gray-300 max-w-2xl mx-auto mb-8">
          Open Research in Algorithmic Options Strategies
        </p>
        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
          <Link
            href="/strategies"
            className="w-full sm:w-auto px-6 py-3 bg-gradient-to-r from-blue-600 to-pink-600 hover:from-blue-500 hover:to-pink-500 text-white font-semibold rounded-lg transition-colors text-center shadow-[0_0_0_1px_rgba(236,72,153,0.3)]"
          >
            Explore All Strategies
          </Link>
          <Link
            href="/backtest"
            className="w-full sm:w-auto px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-pink-200 font-semibold rounded-lg border border-pink-500/30 hover:border-pink-400/50 transition-colors text-center"
          >
            Backtest Explorer
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-12 sm:mb-16">
        {[
          { label: "Strategies Tested", value: totalStrategies > 0 ? `${totalStrategies}+` : "15+" },
          { label: "Years of Data", value: "5 years" },
          { label: "OOS Validated", value: passCount > 0 ? `${passCount} strategies` : "—" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-5 text-center">
            <div className="text-2xl font-bold text-white mb-1">{value}</div>
            <div className="text-xs text-gray-500">{label}</div>
            <div className="mt-2 h-[2px] w-12 mx-auto rounded-full bg-gradient-to-r from-blue-500/0 via-pink-400/80 to-blue-500/0" />
          </div>
        ))}
      </div>

      <div className="mb-12 sm:mb-16">
        <h2 className="text-lg font-semibold text-gray-300 mb-6">Strategy Families</h2>
        <div className="grid grid-cols-1 gap-4">
          {familyStats.map(({ label, tagline, color, badge, featured, catalogEntry }) => {
            const ret = featured?.latest_total_return_pct;
            const sharpe = featured?.latest_sharpe_ratio;
            const dd = featured?.latest_max_drawdown_pct;
            const validated = featured?.oos_pass_validation;
            return (
              <div key={label} className={`border rounded-xl p-5 sm:p-6 ${color}`}>
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${badge} border-current`}>
                        {label}
                      </span>
                      {validated && <span className="text-xs text-green-400 font-semibold">OOS Validated</span>}
                    </div>
                    <p className="text-sm text-gray-400 mt-2">{tagline}</p>
                    {catalogEntry?.description && (
                      <p className="text-xs text-gray-500 mt-1 max-w-lg">{catalogEntry.description}</p>
                    )}
                  </div>
                  <div className="text-left sm:text-right shrink-0 sm:ml-6">
                    {ret != null && (
                      <div className={`text-2xl font-bold ${ret >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {ret >= 0 ? "+" : ""}
                        {ret.toFixed(1)}%
                      </div>
                    )}
                    <div className="text-xs text-gray-500 mt-0.5">5-year return</div>
                    {sharpe != null && <div className="text-sm text-gray-400 mt-1">SR {sharpe.toFixed(2)}</div>}
                    {dd != null && <div className="text-xs text-gray-600">Max DD {dd.toFixed(1)}%</div>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 sm:p-8 mb-12 sm:mb-16">
        <h2 className="text-lg font-semibold text-white mb-3">What is I Hate Banks?</h2>
        <p className="text-gray-400 text-sm leading-relaxed mb-4">
          I Hate Banks is an open research initiative dedicated to the transparent study, development, and evaluation of systematic options trading strategies. This project was founded on the belief that much of modern quantitative finance, despite being built on publicly available mathematics, statistics, and computing, remains unnecessarily opaque and institutionally gated.
        </p>
        <p className="text-gray-400 text-sm leading-relaxed mb-4">
          For decades, advanced research in derivatives trading and algorithmic strategy design has mostly been confined to hedge funds, proprietary trading firms, and large financial institutions. While the tools of quantitative finance have become increasingly accessible through modern computing and open data, practical knowledge around implementation often stays hidden behind institutional barriers.
        </p>
        <p className="text-gray-400 text-sm leading-relaxed mb-4">
          This project exists to challenge that model. I built this as an artist who felt marginalized and bullied by the banking and finance industry. I became a quant to learn how to stop depending on institutions that gatekeep knowledge and abuse information asymmetry.
        </p>
        <p className="text-gray-400 text-sm leading-relaxed mb-4">
          I Hate Banks documents systematic trading strategies with a focus on transparency, reproducibility, and empirical evaluation. Each strategy is published with explicit methodology, documented assumptions, and reproducible backtests. Performance is evaluated using standardized quantitative metrics including Sharpe ratio, maximum drawdown, profit factor, and out-of-sample validation.
        </p>
        <p className="text-gray-400 text-sm leading-relaxed mb-4">
          Rather than presenting strategies as opaque black boxes, this project treats them as research artifacts: systems that can be studied, tested, critiqued, and improved through open collaboration.
        </p>
        <p className="text-gray-400 text-sm leading-relaxed mb-4">
          All materials, including research notes, strategy logic, backtesting frameworks, and documentation, are released under open-source licenses. Anyone is encouraged to study the work, replicate the experiments, fork the repository, and contribute improvements.
        </p>
        <p className="text-gray-300 text-sm leading-relaxed font-medium">
          Markets reward discipline, evidence, and experimentation. Those principles should be open to everyone.
        </p>
      </div>

      <div className="text-center">
        <h2 className="text-xl sm:text-2xl font-bold text-white mb-3">Ready to explore?</h2>
        <p className="text-gray-500 text-sm mb-6">View every strategy variant, compare metrics, and drill into equity curves.</p>
        <Link
          href="/strategies"
          className="inline-block px-8 py-3 bg-gradient-to-r from-blue-600 to-pink-600 hover:from-blue-500 hover:to-pink-500 text-white font-semibold rounded-lg transition-colors shadow-[0_0_0_1px_rgba(236,72,153,0.3)]"
        >
          View All Strategies
        </Link>
      </div>
    </div>
  );
}
