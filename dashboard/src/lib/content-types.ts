export type ReferenceSource = "youtube" | "article" | "docs";
export type ContentLevel = "beginner" | "intermediate" | "advanced";

export type ReferenceLink = {
  title: string;
  url: string;
  source: ReferenceSource;
  why_it_matters: string;
};

export type BaseContent = {
  slug: string;
  title: string;
  summary: string;
  published_at: string;
  updated_at?: string;
  author: string;
  tags: string[];
  level: ContentLevel;
  estimated_minutes: number;
  references: ReferenceLink[];
  disclaimer_required: boolean;
};

export type GlossaryCategory =
  | "options-basics"
  | "risk"
  | "execution"
  | "volatility"
  | "strategy";

export type GlossaryEntry = BaseContent & {
  term: string;
  category: GlossaryCategory;
};

export type Lesson = BaseContent & {
  lesson_number: number;
  learning_objectives: string[];
  key_takeaways: string[];
};

export type Article = BaseContent & {
  thesis: string;
  related_strategies: string[];
};

export type StrategyExplainer = BaseContent & {
  strategy_key: string;
  setup_rules: string[];
  entry_logic: string[];
  exit_logic: string[];
  risk_profile: string[];
  common_failure_modes: string[];
};

export type GlossaryDoc = GlossaryEntry & { body: string; html: string };
export type LessonDoc = Lesson & { body: string; html: string };
export type ArticleDoc = Article & { body: string; html: string };
export type StrategyExplainerDoc = StrategyExplainer & { body: string; html: string };

export type EducationDoc =
  | GlossaryDoc
  | LessonDoc
  | ArticleDoc
  | StrategyExplainerDoc;

