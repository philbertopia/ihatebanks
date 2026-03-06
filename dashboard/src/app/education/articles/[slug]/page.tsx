import { notFound } from "next/navigation";
import Link from "next/link";
import EducationLayout from "@/components/education/EducationLayout";
import DisclaimerBox from "@/components/education/DisclaimerBox";
import ReferenceList from "@/components/education/ReferenceList";
import { getAllArticles, getArticle } from "@/lib/content";

export async function generateStaticParams() {
  const docs = await getAllArticles();
  return docs.map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = await getArticle(slug);
  if (!doc) return { title: "Article | I Hate Banks" };
  return {
    title: `${doc.title} | I Hate Banks`,
    description: doc.summary,
  };
}

export default async function ArticlePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = await getArticle(slug);
  if (!doc) notFound();

  return (
    <EducationLayout title={doc.title} description={doc.summary} showFooterDisclaimer={false}>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <Link href="/education">Education</Link>
        <span>/</span>
        <Link href="/education/articles">Articles</Link>
        <span>/</span>
        <span className="text-gray-300">{doc.slug}</span>
      </div>

      <div className="rounded-xl border border-gray-700 bg-gray-900/60 p-4 text-xs text-gray-300 space-y-1">
        <p><span className="text-gray-500">Published:</span> {doc.published_at}</p>
        <p><span className="text-gray-500">Author:</span> {doc.author}</p>
        <p><span className="text-gray-500">Level:</span> {doc.level} · {doc.estimated_minutes} min read</p>
      </div>

      <section className="rounded-xl border border-gray-700 bg-gray-900/50 p-5">
        <h2 className="text-lg font-semibold text-white">Thesis</h2>
        <p className="text-sm text-gray-300 mt-2">{doc.thesis}</p>
      </section>

      <article className="markdown rounded-xl border border-gray-700 bg-gray-900/50 p-5" dangerouslySetInnerHTML={{ __html: doc.html }} />

      <ReferenceList references={doc.references} />

      <section className="rounded-xl border border-gray-700 bg-gray-900/50 p-5">
        <h2 className="text-lg font-semibold text-white">Related Strategies</h2>
        <div className="flex flex-wrap gap-2 mt-3">
          {doc.related_strategies.map((s) => (
            <span key={s} className="px-3 py-1.5 rounded border border-gray-700 bg-gray-900 text-xs text-gray-300 font-mono">
              {s}
            </span>
          ))}
        </div>
      </section>

      <DisclaimerBox />
    </EducationLayout>
  );
}