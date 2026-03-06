"""
Basic repository readiness checks for open-source publishing.

Run:
    python scripts/open_source_check.py
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    ".gitignore",
]


def find_nested_git_dirs(root: Path) -> list[Path]:
    return [
        p
        for p in root.rglob(".git")
        if p.is_dir() and p.parent != root
    ]


def main() -> None:
    print("[open-source-check] Repository root:", ROOT)

    missing = [f for f in REQUIRED_FILES if not (ROOT / f).exists()]
    if missing:
        print("[ERROR] Missing required files:")
        for f in missing:
            print("  -", f)
    else:
        print("[OK] Core open-source files are present.")

    env_file = ROOT / ".env"
    if env_file.exists():
        print("[WARN] .env exists locally. Ensure it is not committed.")
    else:
        print("[OK] No root .env detected.")

    nested_git = find_nested_git_dirs(ROOT)
    if nested_git:
        print("[WARN] Nested .git directories detected:")
        for p in nested_git:
            print("  -", p.relative_to(ROOT))
        print("       Consider removing nested repos before publishing as one GitHub repository.")
    else:
        print("[OK] No nested .git directories detected.")

    cache_dir = ROOT / "data" / "cache"
    if cache_dir.exists():
        print("[INFO] data/cache exists locally (expected for research).")
        print("       It is ignored by .gitignore for open-source publishing.")


if __name__ == "__main__":
    main()

