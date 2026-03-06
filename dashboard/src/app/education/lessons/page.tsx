import Link from "next/link";
import EducationLayout from "@/components/education/EducationLayout";
import ContentCard from "@/components/education/ContentCard";
import { getAllLessons } from "@/lib/content";

export const metadata = {
  title: "Education Lessons | I Hate Banks",
  description: "Structured options lessons from beginner to advanced.",
};

type SearchParams = Promise<{ level?: string; tag?: string }>;

export default async function LessonsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const level = params.level ?? "all";
  const tag = params.tag ?? "all";

  const lessons = await getAllLessons();
  const tags = Array.from(new Set(lessons.flatMap((l) => l.tags))).sort();

  const filtered = lessons.filter((lesson) => {
    const levelOk = level === "all" || lesson.level === level;
    const tagOk = tag === "all" || lesson.tags.includes(tag);
    return levelOk && tagOk;
  });

  return (
    <EducationLayout
      title="Lessons"
      description="Step-by-step lessons that explain options mechanics, execution, and strategy design."
    >
      <form className="flex flex-col sm:flex-row gap-3 rounded-xl border border-gray-700 bg-gray-900/50 p-4" method="get">
        <label className="text-xs text-gray-400">
          Level
          <select name="level" defaultValue={level} className="mt-1 block bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100">
            <option value="all">all</option>
            <option value="beginner">beginner</option>
            <option value="intermediate">intermediate</option>
            <option value="advanced">advanced</option>
          </select>
        </label>
        <label className="text-xs text-gray-400">
          Tag
          <select name="tag" defaultValue={tag} className="mt-1 block bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100">
            <option value="all">all</option>
            {tags.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
        <div className="flex items-end gap-2">
          <button className="px-4 py-2 text-sm rounded bg-pink-600 hover:bg-pink-500 text-white" type="submit">Apply</button>
          <Link className="px-4 py-2 text-sm rounded border border-gray-700 text-gray-300" href="/education/lessons">Reset</Link>
        </div>
      </form>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((lesson) => (
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
    </EducationLayout>
  );
}
