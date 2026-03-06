import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";

const root = process.cwd();
const contentRoot = path.join(root, "content");
const outPath = path.join(root, "public", "data", "education_index.json");
const dirs = {
  glossary: "glossary",
  lessons: "lessons",
  articles: "articles",
  "strategy-explainers": "strategy-explainers",
};

async function collect(type, dirName) {
  const dirPath = path.join(contentRoot, dirName);
  const files = (await fs.readdir(dirPath)).filter((f) => f.endsWith(".md"));
  const rows = [];
  for (const file of files) {
    const full = path.join(dirPath, file);
    const raw = await fs.readFile(full, "utf8");
    const { data } = matter(raw);
    rows.push({
      type,
      slug: data.slug,
      title: data.title,
      summary: data.summary,
      published_at: data.published_at,
      level: data.level,
      tags: data.tags ?? [],
      estimated_minutes: data.estimated_minutes,
    });
  }
  return rows;
}

async function run() {
  const all = [];
  for (const [type, dirName] of Object.entries(dirs)) {
    const rows = await collect(type, dirName);
    all.push(...rows);
  }
  all.sort((a, b) => String(b.published_at).localeCompare(String(a.published_at)));
  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, JSON.stringify(all, null, 2));
  console.log(`[content:index] wrote ${all.length} entries -> public/data/education_index.json`);
}

run().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});