import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";

const root = process.cwd();
const contentRoot = path.join(root, "content");
const dirs = ["glossary", "lessons", "articles", "strategy-explainers"];
const levels = new Set(["beginner", "intermediate", "advanced"]);
const sources = new Set(["youtube", "article", "docs"]);

function fail(msg) {
  throw new Error(`[content:validate] ${msg}`);
}

function ensure(cond, msg) {
  if (!cond) fail(msg);
}

function ensureDate(value, label) {
  ensure(typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value), `${label} must be YYYY-MM-DD`);
}

function ensureString(value, label) {
  ensure(typeof value === "string" && value.trim().length > 0, `${label} must be non-empty string`);
}

function ensureStringArray(value, label) {
  ensure(Array.isArray(value) && value.length > 0, `${label} must be non-empty array`);
  value.forEach((v, i) => ensure(typeof v === "string" && v.trim(), `${label}[${i}] must be non-empty string`));
}

function validateBase(fm, file) {
  ensureString(fm.slug, `${file}: slug`);
  ensureString(fm.title, `${file}: title`);
  ensureString(fm.summary, `${file}: summary`);
  ensureDate(fm.published_at, `${file}: published_at`);
  if (fm.updated_at !== undefined) ensureDate(fm.updated_at, `${file}: updated_at`);
  ensureString(fm.author, `${file}: author`);
  ensureStringArray(fm.tags, `${file}: tags`);
  ensure(levels.has(fm.level), `${file}: level invalid`);
  ensure(typeof fm.estimated_minutes === "number" && fm.estimated_minutes > 0, `${file}: estimated_minutes must be > 0`);
  ensure(typeof fm.disclaimer_required === "boolean", `${file}: disclaimer_required must be boolean`);
  ensure(Array.isArray(fm.references) && fm.references.length > 0, `${file}: references required`);
  fm.references.forEach((r, idx) => {
    ensure(r && typeof r === "object", `${file}: references[${idx}] must be object`);
    ensureString(r.title, `${file}: references[${idx}].title`);
    ensureString(r.url, `${file}: references[${idx}].url`);
    ensure(String(r.url).startsWith("https://"), `${file}: references[${idx}].url must start with https://`);
    ensure(sources.has(r.source), `${file}: references[${idx}].source invalid`);
    ensureString(r.why_it_matters, `${file}: references[${idx}].why_it_matters`);
  });
}

function validateSpecific(dir, fm, file) {
  if (dir === "glossary") {
    ensureString(fm.term, `${file}: term`);
    ensure(["options-basics", "risk", "execution", "volatility", "strategy"].includes(fm.category), `${file}: category invalid`);
  }
  if (dir === "lessons") {
    ensure(Number.isInteger(fm.lesson_number) && fm.lesson_number > 0, `${file}: lesson_number must be positive integer`);
    ensureStringArray(fm.learning_objectives, `${file}: learning_objectives`);
    ensureStringArray(fm.key_takeaways, `${file}: key_takeaways`);
  }
  if (dir === "articles") {
    ensureString(fm.thesis, `${file}: thesis`);
    ensureStringArray(fm.related_strategies, `${file}: related_strategies`);
  }
  if (dir === "strategy-explainers") {
    ensureString(fm.strategy_key, `${file}: strategy_key`);
    ["setup_rules", "entry_logic", "exit_logic", "risk_profile", "common_failure_modes"].forEach((k) => {
      ensureStringArray(fm[k], `${file}: ${k}`);
    });
  }
}

function countWords(text) {
  const matches = String(text || "").match(/\b[\w'-]+\b/g);
  return matches ? matches.length : 0;
}

function countH2(text) {
  const matches = String(text || "").match(/^##\s+/gm);
  return matches ? matches.length : 0;
}

function validateArticleQuality(fm, body, file) {
  const words = countWords(body);
  ensure(words >= 325, `${file}: article body must be at least 325 words`);

  const h2 = countH2(body);
  ensure(h2 >= 5, `${file}: article body must include at least 5 H2 sections`);

  const phraseTargets = [
    "educational article on",
    "requires context from drawdown, execution quality, and out-of-sample evidence",
    "compare return and drawdown jointly",
    "use this framework before promoting any strategy to production",
  ];
  const lowerBlob = `${String(fm.summary || "")}\n${String(fm.thesis || "")}\n${String(body || "")}`.toLowerCase();
  for (const phrase of phraseTargets) {
    ensure(!lowerBlob.includes(phrase), `${file}: contains banned boilerplate phrase "${phrase}"`);
  }

  const rel = fm.related_strategies || [];
  const relSet = new Set(rel);
  ensure(relSet.size >= 2, `${file}: related_strategies must contain at least 2 distinct values`);

  const refs = fm.references || [];
  const hasYoutube = refs.some((r) => r && r.source === "youtube");
  const hasNonVideo = refs.some((r) => r && (r.source === "article" || r.source === "docs"));
  ensure(hasYoutube, `${file}: references must include at least 1 youtube source`);
  ensure(hasNonVideo, `${file}: references must include at least 1 non-video source`);
}

async function run() {
  let count = 0;
  for (const dir of dirs) {
    const dirPath = path.join(contentRoot, dir);
    const files = (await fs.readdir(dirPath)).filter((f) => f.endsWith(".md"));
    for (const file of files) {
      const full = path.join(dirPath, file);
      const raw = await fs.readFile(full, "utf8");
      const { data, content } = matter(raw);
      ensure(content.trim().length > 0, `${file}: markdown body is empty`);
      validateBase(data, file);
      validateSpecific(dir, data, file);
      if (dir === "articles") {
        validateArticleQuality(data, content, file);
      }
      const slug = file.replace(/\.md$/, "");
      ensure(data.slug === slug, `${file}: slug must match filename (${slug})`);
      count++;
    }
  }
  console.log(`[content:validate] OK (${count} files validated)`);
}

run().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
