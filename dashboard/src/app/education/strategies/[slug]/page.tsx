import Link from "next/link";
import { notFound } from "next/navigation";

import DisclaimerBox from "@/components/education/DisclaimerBox";
import EducationLayout from "@/components/education/EducationLayout";
import ReferenceList from "@/components/education/ReferenceList";
import { getAllStrategyExplainers, getStrategyExplainer } from "@/lib/content";

export async function generateStaticParams() {
  const docs = await getAllStrategyExplainers();
  return docs.map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const doc = await getStrategyExplainer(slug);
  if (!doc) {
    return {
      title: "Strategy Explainer | I Hate Banks",
      description: "Educational strategy explainer.",
    };
  }
  return {
    title: `${doc.title} | Strategy Explainer | I Hate Banks`,
    description: doc.summary,
  };
}

export default async function StrategyExplainerPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const doc = await getStrategyExplainer(slug);
  if (!doc) notFound();

  return (
    <EducationLayout
      title={doc.title}
      description={doc.summary}
      showFooterDisclaimer={false}
    >
      <div className="flex items-center gap-2 text-xs text-gray-500 flex-wrap">
        <Link href="/education" className="hover:text-gray-300">
          Education
        </Link>
        <span>/</span>
        <Link href="/education/strategies" className="hover:text-gray-300">
          Strategy Explainers
        </Link>
        <span>/</span>
        <span className="text-gray-300">{doc.slug}</span>
      </div>

      <div className="rounded-xl border border-gray-700 bg-gray-900/60 p-4 flex flex-wrap gap-2 text-xs">
        <span className="px-2 py-0.5 rounded border border-gray-700 text-gray-300">
          {doc.level}
        </span>
        <span className="px-2 py-0.5 rounded border border-gray-700 text-gray-300 font-mono">
          {doc.strategy_key}
        </span>
        <span className="px-2 py-0.5 rounded border border-gray-700 text-gray-300">
          {doc.estimated_minutes} min read
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="rounded-xl border border-gray-700 bg-gray-900/50 p-5">
          <h2 className="text-lg font-semibold text-white mb-3">Setup Rules</h2>
          <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
            {doc.setup_rules.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section className="rounded-xl border border-gray-700 bg-gray-900/50 p-5">
          <h2 className="text-lg font-semibold text-white mb-3">Entry Logic</h2>
          <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
            {doc.entry_logic.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="rounded-xl border border-gray-700 bg-gray-900/50 p-5">
          <h2 className="text-lg font-semibold text-white mb-3">Exit Logic</h2>
          <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
            {doc.exit_logic.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section className="rounded-xl border border-gray-700 bg-gray-900/50 p-5">
          <h2 className="text-lg font-semibold text-white mb-3">Risk Profile</h2>
          <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
            {doc.risk_profile.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="rounded-xl border border-gray-700 bg-gray-900/50 p-5">
        <h2 className="text-lg font-semibold text-white mb-3">
          Common Failure Modes
        </h2>
        <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
          {doc.common_failure_modes.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <article
        className="markdown rounded-xl border border-gray-700 bg-gray-900/50 p-5"
        dangerouslySetInnerHTML={{ __html: doc.html }}
      />

      <ReferenceList references={doc.references} />

      <DisclaimerBox />
    </EducationLayout>
  );
}
