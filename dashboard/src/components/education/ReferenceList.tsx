import type { ReferenceLink } from "@/lib/content-types";

export default function ReferenceList({ references }: { references: ReferenceLink[] }) {
  if (!references.length) return null;

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold text-white">References</h2>
      <ul className="space-y-2">
        {references.map((ref) => (
          <li key={`${ref.url}-${ref.title}`} className="rounded-lg border border-gray-700 bg-gray-900/60 p-3">
            <a
              href={ref.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-pink-300 hover:text-pink-200 font-medium"
            >
              {ref.title}
            </a>
            <p className="text-xs text-gray-500 mt-1 uppercase tracking-wide">{ref.source}</p>
            <p className="text-sm text-gray-300 mt-1">{ref.why_it_matters}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
