import Link from "next/link";

type ContentCardProps = {
  href: string;
  title: string;
  summary: string;
  meta?: string;
  tags?: string[];
};

export default function ContentCard({ href, title, summary, meta, tags = [] }: ContentCardProps) {
  return (
    <Link
      href={href}
      className="block rounded-xl border border-gray-700 bg-gray-900/70 p-4 hover:border-pink-600 hover:bg-gray-900 transition-colors"
    >
      <h3 className="text-lg font-semibold text-white leading-tight">{title}</h3>
      {meta && <p className="text-xs text-gray-500 mt-1">{meta}</p>}
      <p className="text-sm text-gray-300 mt-2 leading-relaxed">{summary}</p>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {tags.slice(0, 4).map((tag) => (
            <span key={tag} className="text-[10px] px-2 py-0.5 rounded border border-gray-700 text-gray-400 bg-gray-800">
              {tag}
            </span>
          ))}
        </div>
      )}
    </Link>
  );
}
