import type {
  Article,
  BaseContent,
  ContentLevel,
  GlossaryCategory,
  GlossaryEntry,
  Lesson,
  ReferenceLink,
  ReferenceSource,
  StrategyExplainer,
} from "@/lib/content-types";

const LEVELS: ContentLevel[] = ["beginner", "intermediate", "advanced"];
const SOURCES: ReferenceSource[] = ["youtube", "article", "docs"];
const GLOSSARY_CATEGORIES: GlossaryCategory[] = [
  "options-basics",
  "risk",
  "execution",
  "volatility",
  "strategy",
];

function fail(path: string, message: string): never {
  throw new Error(`[content] ${path}: ${message}`);
}

function asString(path: string, key: string, value: unknown): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    fail(path, `Expected non-empty string for "${key}"`);
  }
  return value.trim();
}

function asStringArray(path: string, key: string, value: unknown): string[] {
  if (!Array.isArray(value) || value.length === 0) {
    fail(path, `Expected non-empty string[] for "${key}"`);
  }
  const arr = value.map((v, idx) => {
    if (typeof v !== "string" || v.trim().length === 0) {
      fail(path, `Expected "${key}[${idx}]" to be a non-empty string`);
    }
    return v.trim();
  });
  return arr;
}

function asNumber(path: string, key: string, value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    fail(path, `Expected finite number for "${key}"`);
  }
  return value;
}

function asBoolean(path: string, key: string, value: unknown): boolean {
  if (typeof value !== "boolean") {
    fail(path, `Expected boolean for "${key}"`);
  }
  return value;
}

function asDateString(path: string, key: string, value: unknown): string {
  const raw = asString(path, key, value);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    fail(path, `Expected "${key}" to be YYYY-MM-DD`);
  }
  return raw;
}

function asEnum<T extends string>(
  path: string,
  key: string,
  value: unknown,
  allowed: readonly T[]
): T {
  const raw = asString(path, key, value);
  if (!allowed.includes(raw as T)) {
    fail(path, `Expected "${key}" to be one of: ${allowed.join(", ")}`);
  }
  return raw as T;
}

function validateReference(path: string, index: number, value: unknown): ReferenceLink {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail(path, `Expected references[${index}] to be an object`);
  }
  const v = value as Record<string, unknown>;
  const url = asString(path, `references[${index}].url`, v.url);
  if (!url.startsWith("https://")) {
    fail(path, `Expected references[${index}].url to start with https://`);
  }
  return {
    title: asString(path, `references[${index}].title`, v.title),
    url,
    source: asEnum(path, `references[${index}].source`, v.source, SOURCES),
    why_it_matters: asString(
      path,
      `references[${index}].why_it_matters`,
      v.why_it_matters
    ),
  };
}

function validateReferences(path: string, value: unknown): ReferenceLink[] {
  if (!Array.isArray(value) || value.length === 0) {
    fail(path, `Expected non-empty references[]`);
  }
  return value.map((ref, idx) => validateReference(path, idx, ref));
}

export function validateBaseContent(path: string, fm: Record<string, unknown>): BaseContent {
  const base: BaseContent = {
    slug: asString(path, "slug", fm.slug),
    title: asString(path, "title", fm.title),
    summary: asString(path, "summary", fm.summary),
    published_at: asDateString(path, "published_at", fm.published_at),
    author: asString(path, "author", fm.author),
    tags: asStringArray(path, "tags", fm.tags),
    level: asEnum(path, "level", fm.level, LEVELS),
    estimated_minutes: asNumber(path, "estimated_minutes", fm.estimated_minutes),
    references: validateReferences(path, fm.references),
    disclaimer_required: asBoolean(path, "disclaimer_required", fm.disclaimer_required),
  };

  if (fm.updated_at !== undefined) {
    base.updated_at = asDateString(path, "updated_at", fm.updated_at);
  }
  if (base.estimated_minutes <= 0) {
    fail(path, `"estimated_minutes" must be > 0`);
  }
  return base;
}

export function validateGlossaryEntry(
  path: string,
  fm: Record<string, unknown>
): GlossaryEntry {
  const base = validateBaseContent(path, fm);
  return {
    ...base,
    term: asString(path, "term", fm.term),
    category: asEnum(path, "category", fm.category, GLOSSARY_CATEGORIES),
  };
}

export function validateLesson(path: string, fm: Record<string, unknown>): Lesson {
  const base = validateBaseContent(path, fm);
  const lessonNumber = asNumber(path, "lesson_number", fm.lesson_number);
  if (!Number.isInteger(lessonNumber) || lessonNumber <= 0) {
    fail(path, `"lesson_number" must be a positive integer`);
  }
  return {
    ...base,
    lesson_number: lessonNumber,
    learning_objectives: asStringArray(path, "learning_objectives", fm.learning_objectives),
    key_takeaways: asStringArray(path, "key_takeaways", fm.key_takeaways),
  };
}

export function validateArticle(path: string, fm: Record<string, unknown>): Article {
  const base = validateBaseContent(path, fm);
  return {
    ...base,
    thesis: asString(path, "thesis", fm.thesis),
    related_strategies: asStringArray(path, "related_strategies", fm.related_strategies),
  };
}

export function validateStrategyExplainer(
  path: string,
  fm: Record<string, unknown>
): StrategyExplainer {
  const base = validateBaseContent(path, fm);
  return {
    ...base,
    strategy_key: asString(path, "strategy_key", fm.strategy_key),
    setup_rules: asStringArray(path, "setup_rules", fm.setup_rules),
    entry_logic: asStringArray(path, "entry_logic", fm.entry_logic),
    exit_logic: asStringArray(path, "exit_logic", fm.exit_logic),
    risk_profile: asStringArray(path, "risk_profile", fm.risk_profile),
    common_failure_modes: asStringArray(path, "common_failure_modes", fm.common_failure_modes),
  };
}

export function assertSlugMatchesFilename(
  path: string,
  slug: string,
  fileName: string
): void {
  if (slug !== fileName) {
    fail(path, `Frontmatter slug "${slug}" must match filename "${fileName}"`);
  }
}

