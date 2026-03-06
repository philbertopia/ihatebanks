type LegalDisclaimerProps = {
  compact?: boolean;
};

export default function LegalDisclaimer({ compact = false }: LegalDisclaimerProps) {
  return (
    <div className={`rounded-lg border border-gray-800 bg-gray-900/60 ${compact ? "p-3" : "p-4"}`}>
      <p className={`text-gray-300 ${compact ? "text-[11px]" : "text-xs sm:text-sm"} leading-relaxed`}>
        For research and educational purposes only. Nothing on this site is financial, investment, legal, or tax advice.
        Consult a licensed financial advisor or other qualified professional before making investment decisions.
        Backtest results are hypothetical and do not guarantee future performance.
        Options trading involves substantial risk, including the potential loss of principal.
      </p>
    </div>
  );
}

