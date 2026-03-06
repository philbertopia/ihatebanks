import "server-only";

import fs from "node:fs/promises";
import path from "node:path";
import { existsSync } from "node:fs";
import matter from "gray-matter";
import { remark } from "remark";
import remarkGfm from "remark-gfm";
import remarkHtml from "remark-html";

import type {
  Article,
  ArticleDoc,
  GlossaryDoc,
  GlossaryEntry,
  Lesson,
  LessonDoc,
  StrategyExplainer,
  StrategyExplainerDoc,
} from "@/lib/content-types";
import {
  assertSlugMatchesFilename,
  validateArticle,
  validateGlossaryEntry,
  validateLesson,
  validateStrategyExplainer,
} from "@/lib/content-validators";

function resolveContentRoot(): string {
  const cwd = process.cwd();
  const candidates = [
    path.join(cwd, "content"),
    path.join(cwd, "dashboard", "content"),
    path.join(path.dirname(cwd), "content"),
  ];
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  // Default path keeps local dev behavior and yields a clear ENOENT log below if missing.
  return path.join(cwd, "content");
}

const CONTENT_ROOT = resolveContentRoot();

const CONTENT_DIRS = {
  glossary: path.join(CONTENT_ROOT, "glossary"),
  lessons: path.join(CONTENT_ROOT, "lessons"),
  articles: path.join(CONTENT_ROOT, "articles"),
  strategyExplainers: path.join(CONTENT_ROOT, "strategy-explainers"),
};

async function markdownToHtml(markdown: string): Promise<string> {
  const file = await remark().use(remarkGfm).use(remarkHtml).process(markdown);
  return String(file);
}

function isMarkdownFile(name: string): boolean {
  return name.endsWith(".md");
}

async function readCollection<T>(
  dirPath: string,
  validator: (pathName: string, fm: Record<string, unknown>) => T
): Promise<Array<T & { body: string; html: string }>> {
  type DirEntryLike = { isFile: () => boolean; name: string };
  let entries: DirEntryLike[];
  try {
    const rawEntries = await fs.readdir(dirPath, { withFileTypes: true });
    entries = rawEntries as unknown as DirEntryLike[];
  } catch (error) {
    const err = error as NodeJS.ErrnoException;
    if (err.code === "ENOENT") {
      console.error(
        `[content] directory not found at runtime: ${dirPath}. ` +
          `Resolved root: ${CONTENT_ROOT}. ` +
          `If deploying on Vercel, ensure output file tracing includes ./content/**/*`
      );
      return [];
    }
    throw error;
  }
  const files = entries.filter((e) => e.isFile() && isMarkdownFile(e.name));
  const docs: Array<T & { body: string; html: string }> = [];

  for (const file of files) {
    const fullPath = path.join(dirPath, file.name);
    const raw = await fs.readFile(fullPath, "utf8");
    const parsed = matter(raw);
    const fm = (parsed.data ?? {}) as Record<string, unknown>;
    const validated = validator(fullPath, fm);
    const fileSlug = file.name.replace(/\.md$/, "");
    assertSlugMatchesFilename(fullPath, (validated as { slug: string }).slug, fileSlug);
    const html = await markdownToHtml(parsed.content);
    docs.push({
      ...validated,
      body: parsed.content.trim(),
      html,
    });
  }

  return docs;
}

function sortByDateDesc<T extends { published_at: string }>(docs: T[]): T[] {
  return docs.slice().sort((a, b) => (a.published_at < b.published_at ? 1 : -1));
}

function sortByTitleAsc<T extends { title: string }>(docs: T[]): T[] {
  return docs.slice().sort((a, b) => a.title.localeCompare(b.title));
}

function sortByLessonNumberAsc<T extends { lesson_number: number }>(docs: T[]): T[] {
  return docs.slice().sort((a, b) => a.lesson_number - b.lesson_number);
}

let glossaryCache: GlossaryDoc[] | null = null;
let lessonCache: LessonDoc[] | null = null;
let articleCache: ArticleDoc[] | null = null;
let strategyCache: StrategyExplainerDoc[] | null = null;

export async function getAllGlossaryEntries(): Promise<GlossaryDoc[]> {
  if (!glossaryCache) {
    const docs = await readCollection<GlossaryEntry>(
      CONTENT_DIRS.glossary,
      validateGlossaryEntry
    );
    glossaryCache = sortByTitleAsc(docs);
  }
  return glossaryCache;
}

export async function getGlossaryEntry(slug: string): Promise<GlossaryDoc | null> {
  const docs = await getAllGlossaryEntries();
  return docs.find((d) => d.slug === slug) ?? null;
}

export async function getAllLessons(): Promise<LessonDoc[]> {
  if (!lessonCache) {
    const docs = await readCollection<Lesson>(CONTENT_DIRS.lessons, validateLesson);
    lessonCache = sortByLessonNumberAsc(docs);
  }
  return lessonCache;
}

export async function getLesson(slug: string): Promise<LessonDoc | null> {
  const docs = await getAllLessons();
  return docs.find((d) => d.slug === slug) ?? null;
}

export async function getAllArticles(): Promise<ArticleDoc[]> {
  if (!articleCache) {
    const docs = await readCollection<Article>(CONTENT_DIRS.articles, validateArticle);
    articleCache = sortByDateDesc(docs);
  }
  return articleCache;
}

export async function getArticle(slug: string): Promise<ArticleDoc | null> {
  const docs = await getAllArticles();
  return docs.find((d) => d.slug === slug) ?? null;
}

export async function getAllStrategyExplainers(): Promise<StrategyExplainerDoc[]> {
  if (!strategyCache) {
    const docs = await readCollection<StrategyExplainer>(
      CONTENT_DIRS.strategyExplainers,
      validateStrategyExplainer
    );
    strategyCache = sortByTitleAsc(docs);
  }
  return strategyCache;
}

export async function getStrategyExplainer(slug: string): Promise<StrategyExplainerDoc | null> {
  const docs = await getAllStrategyExplainers();
  return docs.find((d) => d.slug === slug) ?? null;
}

export async function getStrategyExplainerByKey(
  strategyKey: string
): Promise<StrategyExplainerDoc | null> {
  const docs = await getAllStrategyExplainers();
  return docs.find((d) => d.strategy_key === strategyKey) ?? null;
}

export function getContentDirectories() {
  return CONTENT_DIRS;
}
