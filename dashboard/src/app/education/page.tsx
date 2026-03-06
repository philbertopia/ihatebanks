import Link from "next/link";
import EducationLayout from "@/components/education/EducationLayout";
import ContentCard from "@/components/education/ContentCard";
import {
  getAllArticles,
  getAllGlossaryEntries,
  getAllLessons,
  getAllStrategyExplainers,
} from "@/lib/content";

export default async function EducationHubPage() {
  const [glossary, lessons, articles, explainers] = await Promise.all([
    getAllGlossaryEntries(),
    getAllLessons(),
    getAllArticles(),
    getAllStrategyExplainers(),
  ]);

  return (
    <EducationLayout
      title="Education Hub"
      description="Learn options trading fundamentals, understand how Alpaca execution works, and study how each strategy behaves in different market regimes."
      showGlobalDisclaimer
      showExploreLinks={false}
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-4">
          <p className="text-xs text-gray-500">Glossary Terms</p>
          <p className="text-2xl font-bold text-white mt-1">{glossary.length}</p>
        </div>
        <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-4">
          <p className="text-xs text-gray-500">Lessons</p>
          <p className="text-2xl font-bold text-white mt-1">{lessons.length}</p>
        </div>
        <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-4">
          <p className="text-xs text-gray-500">Articles</p>
          <p className="text-2xl font-bold text-white mt-1">{articles.length}</p>
        </div>
        <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-4">
          <p className="text-xs text-gray-500">Strategy Explainers</p>
          <p className="text-2xl font-bold text-white mt-1">{explainers.length}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link href="/education/glossary" className="rounded-xl border border-gray-700 bg-gray-900/70 p-5 hover:border-pink-600 transition-colors">
          <h2 className="text-xl font-semibold text-white">Glossary</h2>
          <p className="text-sm text-gray-400 mt-2">A-Z options terminology, Greeks, volatility concepts, risk metrics, and backtesting terms.</p>
        </Link>

        <Link href="/education/lessons" className="rounded-xl border border-gray-700 bg-gray-900/70 p-5 hover:border-pink-600 transition-colors">
          <h2 className="text-xl font-semibold text-white">Lessons</h2>
          <p className="text-sm text-gray-400 mt-2">Structured lessons from beginner to advanced topics, with practical examples and references.</p>
        </Link>

        <Link href="/education/articles" className="rounded-xl border border-gray-700 bg-gray-900/70 p-5 hover:border-pink-600 transition-colors">
          <h2 className="text-xl font-semibold text-white">Articles</h2>
          <p className="text-sm text-gray-400 mt-2">Long-form explainers on strategy performance, risk behavior, and execution realities.</p>
        </Link>

        <Link href="/education/strategies" className="rounded-xl border border-gray-700 bg-gray-900/70 p-5 hover:border-pink-600 transition-colors">
          <h2 className="text-xl font-semibold text-white">Strategy Explainers</h2>
          <p className="text-sm text-gray-400 mt-2">Plain-English breakdowns of entry logic, exits, risks, and failure modes for each strategy.</p>
        </Link>
      </div>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">Start Here</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {lessons.slice(0, 4).map((lesson) => (
            <ContentCard
              key={lesson.slug}
              href={`/education/lessons/${lesson.slug}`}
              title={`Lesson ${lesson.lesson_number}: ${lesson.title}`}
              summary={lesson.summary}
              meta={`${lesson.level} · ${lesson.estimated_minutes} min`}
              tags={lesson.tags}
            />
          ))}
        </div>
      </section>

      <div className="rounded-xl border border-pink-900/40 bg-pink-950/20 p-4 text-sm text-gray-300">
        Want to compare educational concepts with real strategy stats? Visit{" "}
        <Link href="/strategies" className="text-pink-300 underline">
          Strategies
        </Link>{" "}
        and{" "}
        <Link href="/backtest" className="text-pink-300 underline">
          Backtest Explorer
        </Link>
        .
      </div>
    </EducationLayout>
  );
}
