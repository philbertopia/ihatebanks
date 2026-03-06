import { notFound } from "next/navigation";
import Link from "next/link";
import EducationLayout from "@/components/education/EducationLayout";
import DisclaimerBox from "@/components/education/DisclaimerBox";
import ReferenceList from "@/components/education/ReferenceList";
import { getAllGlossaryEntries, getGlossaryEntry } from "@/lib/content";

export async function generateStaticParams() {
  const docs = await getAllGlossaryEntries();
  return docs.map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = await getGlossaryEntry(slug);
  if (!doc) return { title: "Glossary Term | I Hate Banks" };
  return {
    title: `${doc.term} | Glossary | I Hate Banks`,
    description: doc.summary,
  };
}

export default async function GlossaryTermPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = await getGlossaryEntry(slug);
  if (!doc) notFound();

  const all = await getAllGlossaryEntries();
  const related = all
    .filter((d) => d.category === doc.category && d.slug !== doc.slug)
    .slice(0, 4);

  return (
    <EducationLayout title={doc.term} description={doc.summary} showFooterDisclaimer={false}>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <Link href="/education">Education</Link>
        <span>/</span>
        <Link href="/education/glossary">Glossary</Link>
        <span>/</span>
        <span className="text-gray-300">{doc.slug}</span>
      </div>

      <div className="rounded-xl border border-gray-700 bg-gray-900/60 p-4 flex flex-wrap gap-2 text-xs">
        <span className="px-2 py-0.5 rounded border border-gray-700 text-gray-300">{doc.category}</span>
        <span className="px-2 py-0.5 rounded border border-gray-700 text-gray-300">{doc.level}</span>
        <span className="px-2 py-0.5 rounded border border-gray-700 text-gray-300">{doc.estimated_minutes} min read</span>
      </div>

      <article className="markdown rounded-xl border border-gray-700 bg-gray-900/50 p-5" dangerouslySetInnerHTML={{ __html: doc.html }} />

      <ReferenceList references={doc.references} />

      {related.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold text-white">Related Terms</h2>
          <div className="flex flex-wrap gap-2">
            {related.map((r) => (
              <Link key={r.slug} href={`/education/glossary/${r.slug}`} className="text-sm px-3 py-1.5 rounded border border-gray-700 bg-gray-900 text-gray-300 hover:border-pink-600">
                {r.term}
              </Link>
            ))}
          </div>
        </section>
      )}

      <DisclaimerBox />
    </EducationLayout>
  );
}
