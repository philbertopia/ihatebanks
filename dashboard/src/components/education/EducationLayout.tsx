import type { ReactNode } from "react";
import Link from "next/link";

import DisclaimerBox from "@/components/education/DisclaimerBox";

type EducationLayoutProps = {
  title: string;
  description?: string;
  children: ReactNode;
  showGlobalDisclaimer?: boolean;
  showFooterDisclaimer?: boolean;
  showExploreLinks?: boolean;
};

export default function EducationLayout({
  title,
  description,
  children,
  showGlobalDisclaimer = false,
  showFooterDisclaimer = true,
  showExploreLinks = true,
}: EducationLayoutProps) {
  return (
    <section className="max-w-5xl mx-auto py-8 sm:py-10 px-4 sm:px-6 space-y-6">
      <header>
        <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
          {title}
        </h1>
        {description && (
          <p className="text-gray-400 mt-2 max-w-3xl">{description}</p>
        )}
      </header>

      {showGlobalDisclaimer && <DisclaimerBox variant="banner" />}

      {children}

      {showExploreLinks && (
        <div className="rounded-xl border border-pink-900/40 bg-pink-950/20 p-4 text-sm text-gray-300">
          Explore real strategy metrics in{" "}
          <Link href="/strategies" className="text-pink-300 underline">
            Strategies
          </Link>{" "}
          and{" "}
          <Link href="/backtest" className="text-pink-300 underline">
            Backtest Explorer
          </Link>
          .
        </div>
      )}

      {showFooterDisclaimer && (
        <div className="text-xs text-gray-500 border-t border-gray-800 pt-4">
          For research and educational purposes only. Not financial, investment,
          legal, or tax advice. Consult a licensed financial advisor before
          making investment decisions. Backtest results are hypothetical and do
          not guarantee future performance.
        </div>
      )}
    </section>
  );
}
