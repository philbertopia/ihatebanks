import fs from "node:fs/promises";
import path from "node:path";

function arg(name) {
  const idx = process.argv.indexOf(name);
  if (idx === -1) return null;
  return process.argv[idx + 1] ?? null;
}

function slugify(input) {
  return input
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

async function run() {
  const input = arg("--slug") ?? arg("-s");
  if (!input) {
    throw new Error("Usage: npm run new:article -- --slug your-article-title");
  }

  const slug = slugify(input);
  if (!slug) {
    throw new Error("Could not derive a valid slug from input");
  }

  const date = new Date().toISOString().slice(0, 10);
  const filePath = path.join(process.cwd(), "content", "articles", `${slug}.md`);

  try {
    await fs.access(filePath);
    throw new Error(`Article already exists: content/articles/${slug}.md`);
  } catch {
    // expected if file doesn't exist
  }

  const template = `---
slug: "${slug}"
title: "${slug
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")}"
summary: "One-paragraph summary of the article's value to the reader."
published_at: "${date}"
author: "I Hate Banks"
tags: ["options", "education"]
level: "intermediate"
estimated_minutes: 8
disclaimer_required: true
thesis: "Primary argument in one sentence."
related_strategies: ["openclaw_put_credit_spread|legacy_replica"]
references:
  - title: "Reference title"
    url: "https://example.com"
    source: "article"
    why_it_matters: "Explain why this reference helps the learner."
---

## Overview

Write the article here.

## Core Idea

Explain the core framework with examples.

## Practical Application

Connect the concept to your strategy results and decision-making process.

## Key Takeaways

- Point one
- Point two
- Point three
`;

  await fs.writeFile(filePath, template, "utf8");
  console.log(`[new:article] created content/articles/${slug}.md`);
}

run().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});