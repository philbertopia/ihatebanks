# Project Structure Guide

This repository contains two primary applications:

1. Python strategy/backtesting stack (root, `ovtlyr/`, `main.py`, `server.py`)
2. Next.js frontend app (`dashboard/`)

## Top-Level Folders

- `config/`  
  Runtime configuration and universe definitions.

- `data/`  
  Local research outputs and generated artifacts. Large cache files are ignored by default.

- `db/`  
  Local SQLite data.

- `ovtlyr/`  
  Core Python package with engines, API routes, and business logic.

- `scripts/`  
  Root maintenance scripts such as exporting static dashboard JSON.

- `tests/`  
  Python test suite.

- `dashboard/`  
  Frontend app + education content publishing system.

## Dashboard Content System

Educational markdown is authored in:

- `dashboard/content/glossary`
- `dashboard/content/lessons`
- `dashboard/content/articles`
- `dashboard/content/strategy-explainers`

Validated and indexed via:

- `npm run content:validate`
- `npm run content:index`

## Suggested Ownership Boundaries

- Python strategy changes: `ovtlyr/`, `main.py`, `tests/`
- Frontend UI changes: `dashboard/src/`
- Educational content: `dashboard/content/`
- Static publishing/data export: `scripts/`, `dashboard/scripts/`

