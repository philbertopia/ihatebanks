"use client";

import { useMemo, useState } from "react";
import ContentCard from "@/components/education/ContentCard";
import type { GlossaryEntry } from "@/lib/content-types";

type Props = {
  entries: GlossaryEntry[];
};

const categories = ["all", "options-basics", "risk", "execution", "volatility", "strategy"] as const;
const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

export default function GlossarySearch({ entries }: Props) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<(typeof categories)[number]>("all");
  const [letter, setLetter] = useState<string>("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return entries.filter((entry) => {
      const categoryOk = category === "all" || entry.category === category;
      const queryOk =
        q.length === 0 ||
        entry.term.toLowerCase().includes(q) ||
        entry.summary.toLowerCase().includes(q) ||
        entry.tags.some((tag) => tag.toLowerCase().includes(q));
      const first = entry.term.trim().charAt(0).toUpperCase();
      const letterOk = letter === "all" || first === letter;
      return categoryOk && queryOk && letterOk;
    });
  }, [entries, query, category, letter]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search terms, tags, or definitions"
          className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100"
        />

        <div className="flex flex-wrap gap-1.5">
          {categories.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCategory(c)}
              className={`px-2.5 py-1 rounded text-xs border ${
                category === c
                  ? "bg-pink-600 border-pink-500 text-white"
                  : "bg-gray-900 border-gray-700 text-gray-300 hover:bg-gray-800"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <p className="text-xs text-gray-500">{filtered.length} terms</p>

      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setLetter("all")}
          className={`px-2 py-1 rounded text-xs border ${
            letter === "all"
              ? "bg-pink-600 border-pink-500 text-white"
              : "bg-gray-900 border-gray-700 text-gray-300 hover:bg-gray-800"
          }`}
        >
          All
        </button>
        {alphabet.map((ch) => (
          <button
            key={ch}
            type="button"
            onClick={() => setLetter(ch)}
            className={`px-2 py-1 rounded text-xs border ${
              letter === ch
                ? "bg-pink-600 border-pink-500 text-white"
                : "bg-gray-900 border-gray-700 text-gray-300 hover:bg-gray-800"
            }`}
          >
            {ch}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((entry) => (
          <ContentCard
            key={entry.slug}
            href={`/education/glossary/${entry.slug}`}
            title={entry.term}
            summary={entry.summary}
            meta={`${entry.category} · ${entry.level}`}
            tags={entry.tags}
          />
        ))}
      </div>
    </div>
  );
}
