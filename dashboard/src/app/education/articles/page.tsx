import Link from "next/link";
import EducationLayout from "@/components/education/EducationLayout";
import ContentCard from "@/components/education/ContentCard";
import { getAllArticles } from "@/lib/content";

export const metadata = {
  title: "Education Articles | I Hate Banks",
  description: "Long-form educational articles about options strategy behavior and risk.",
};

type SearchParams = Promise<{ tag?: string; level?: string }>;

export default async function ArticlesPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const tag = params.tag ?? "all";
  const level = params.level ?? "all";

  const articles = await getAllArticles();
  const tags = Array.from(new Set(articles.flatMap((a) => a.tags))).sort();

  const filtered = articles.filter((article) => {
    const tagOk = tag === "all" || article.tags.includes(tag);
    const levelOk = level === "all" || article.level === level;
    return tagOk && levelOk;
  });

  return (
    <EducationLayout
      title="Articles"
      description="Published educational essays on options strategy design, risk, and performance interpretation."
    >
      <form className="flex flex-col sm:flex-row gap-3 rounded-xl border border-gray-700 bg-gray-900/50 p-4" method="get">
        <label className="text-xs text-gray-400">
          Tag
          <select name="tag" defaultValue={tag} className="mt-1 block bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100">
            <option value="all">all</option>
            {tags.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="text-xs text-gray-400">
          Level
          <select name="level" defaultValue={level} className="mt-1 block bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100">
            <option value="all">all</option>
            <option value="beginner">beginner</option>
            <option value="intermediate">intermediate</option>
            <option value="advanced">advanced</option>
          </select>
        </label>
        <div className="flex items-end gap-2">
          <button className="px-4 py-2 text-sm rounded bg-pink-600 hover:bg-pink-500 text-white" type="submit">Apply</button>
          <Link className="px-4 py-2 text-sm rounded border border-gray-700 text-gray-300" href="/education/articles">Reset</Link>
        </div>
      </form>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((article) => (
          <ContentCard
            key={article.slug}
            href={`/education/articles/${article.slug}`}
            title={article.title}
            summary={article.summary}
            meta={`${article.published_at} · ${article.estimated_minutes} min`}
            tags={article.tags}
          />
        ))}
      </div>
    </EducationLayout>
  );
}
