import { notFound } from "next/navigation";
import Link from "next/link";
import EducationLayout from "@/components/education/EducationLayout";
import DisclaimerBox from "@/components/education/DisclaimerBox";
import ReferenceList from "@/components/education/ReferenceList";
import { getAllLessons, getLesson } from "@/lib/content";

export async function generateStaticParams() {
  const docs = await getAllLessons();
  return docs.map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = await getLesson(slug);
  if (!doc) return { title: "Lesson | I Hate Banks" };
  return {
    title: `Lesson ${doc.lesson_number}: ${doc.title} | I Hate Banks`,
    description: doc.summary,
  };
}

export default async function LessonPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = await getLesson(slug);
  if (!doc) notFound();

  return (
    <EducationLayout title={`Lesson ${doc.lesson_number}: ${doc.title}`} description={doc.summary} showFooterDisclaimer={false}>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <Link href="/education">Education</Link>
        <span>/</span>
        <Link href="/education/lessons">Lessons</Link>
        <span>/</span>
        <span className="text-gray-300">{doc.slug}</span>
      </div>

      <section className="rounded-xl border border-gray-700 bg-gray-900/50 p-5 space-y-3">
        <h2 className="text-lg font-semibold text-white">Learning Objectives</h2>
        <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
          {doc.learning_objectives.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <article className="markdown rounded-xl border border-gray-700 bg-gray-900/50 p-5" dangerouslySetInnerHTML={{ __html: doc.html }} />

      <section className="rounded-xl border border-gray-700 bg-gray-900/50 p-5 space-y-3">
        <h2 className="text-lg font-semibold text-white">Key Takeaways</h2>
        <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
          {doc.key_takeaways.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <ReferenceList references={doc.references} />
      <DisclaimerBox />
    </EducationLayout>
  );
}
