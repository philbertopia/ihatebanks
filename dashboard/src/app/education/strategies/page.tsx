import Link from "next/link";
import EducationLayout from "@/components/education/EducationLayout";
import ContentCard from "@/components/education/ContentCard";
import { getAllStrategyExplainers } from "@/lib/content";

function familyFromKey(strategyKey: string) {
  if (strategyKey.startsWith("pcs") || strategyKey.includes("put_credit")) return "pcs";
  if (strategyKey.startsWith("ccs") || strategyKey.includes("call_credit")) return "ccs";
  if (strategyKey.startsWith("wheel")) return "wheel";
  if (strategyKey.startsWith("intraday")) return "intraday";
  if (strategyKey.startsWith("stock")) return "stock-replacement";
  return "other";
}

export const metadata = {
  title: "Strategy Explainers | I Hate Banks",
  description: "How each strategy works, including setup, entries, exits, and risk behavior.",
};

type SearchParams = Promise<{ family?: string }>;

export default async function StrategyExplainersPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const family = params.family ?? "all";

  const explainers = await getAllStrategyExplainers();
  const filtered = explainers.filter((doc) => family === "all" || familyFromKey(doc.strategy_key) === family);

  return (
    <EducationLayout
      title="Strategy Explainers"
      description="Detailed walkthroughs of each strategy's setup, entries, exits, risk profile, and failure modes."
    >
      <form
        method="get"
        className="flex flex-col sm:flex-row sm:items-end gap-3 rounded-xl border border-gray-700 bg-gray-900/50 p-4"
      >
        <label className="text-xs text-gray-400">
          Family
          <select name="family" defaultValue={family} className="mt-1 block bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100">
            <option value="all">all</option>
            <option value="pcs">pcs</option>
            <option value="ccs">ccs</option>
            <option value="wheel">wheel</option>
            <option value="intraday">intraday</option>
            <option value="stock-replacement">stock-replacement</option>
          </select>
        </label>
        <button className="px-4 py-2 text-sm rounded bg-pink-600 hover:bg-pink-500 text-white" type="submit">Apply</button>
        <Link className="px-4 py-2 text-sm rounded border border-gray-700 text-gray-300" href="/education/strategies">Reset</Link>
      </form>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((doc) => (
          <ContentCard
            key={doc.slug}
            href={`/education/strategies/${doc.slug}`}
            title={doc.title}
            summary={doc.summary}
            meta={`${doc.level} · ${doc.strategy_key}`}
            tags={doc.tags}
          />
        ))}
      </div>
    </EducationLayout>
  );
}
