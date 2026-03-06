type DisclaimerVariant = "banner" | "inline";

export default function DisclaimerBox({ variant = "inline" }: { variant?: DisclaimerVariant }) {
  const banner = variant === "banner";
  return (
    <div
      className={`rounded-xl border ${banner ? "border-amber-700 bg-amber-900/20" : "border-gray-700 bg-gray-900/60"} p-4`}
    >
      <h3 className={`${banner ? "text-amber-300" : "text-gray-300"} text-sm font-semibold mb-1`}>
        Important Educational Disclaimer
      </h3>
      <p className="text-xs sm:text-sm text-gray-300 leading-relaxed">
        This content is for research and educational purposes only. It is not financial, investment, legal, or tax advice.
        Consult a licensed financial advisor or other qualified professional before making investment decisions.
        Backtest results are hypothetical and are not guarantees of future performance.
        Options trading involves substantial risk and may not be suitable for all investors.
      </p>
    </div>
  );
}
