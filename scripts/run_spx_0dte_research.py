"""
Research-only parameter sweep for SPX 0DTE short put spread.

Runs each variant (conservative, balanced, aggressive) over cached data,
collects metrics and sub-period breakdown, writes JSON + Markdown under data/reports/.
Does not write to official backtest stores.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ovtlyr.backtester.spx_0dte_engine import run_spx_0dte_put_spread

DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
CACHE_DIR = DATA_DIR / "cache"

VARIANTS = ["conservative", "balanced", "aggressive"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SPX 0DTE put spread parameter sweep (research only)."
    )
    parser.add_argument("--start", default="2022-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: latest cache)")
    parser.add_argument("--variants", nargs="*", default=VARIANTS, help="Variants to run")
    return parser.parse_args()


def load_cached_data(start: date, end: date) -> pd.DataFrame:
    if not CACHE_DIR.exists():
        raise FileNotFoundError(
            f"Cache dir {CACHE_DIR} not found. Run 'python main.py generate' or 'python main.py collect' first."
        )
    dfs: List[pd.DataFrame] = []
    for path in sorted(CACHE_DIR.glob("*.parquet")):
        try:
            d = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if start <= d <= end:
            dfs.append(pd.read_parquet(path))
    if not dfs:
        return pd.DataFrame()
    out = pd.concat(dfs, ignore_index=True)
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"])
    return out.sort_values("date").reset_index(drop=True)


def main() -> None:
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end) if args.end else date.today()

    data = load_cached_data(start, end)
    if data.empty:
        print("No cached data in range; aborting.")
        sys.exit(1)

    # Ensure we have required columns for 0DTE (put chain with dte)
    required = {"date", "underlying", "option_type", "strike", "expiration_date", "dte", "bid", "ask"}
    missing = required - set(data.columns)
    if missing:
        print(f"Cache missing columns: {missing}. Need option chain with dte.")
        sys.exit(1)

    results: List[Dict[str, Any]] = []
    for variant in args.variants:
        if variant not in VARIANTS:
            print(f"Unknown variant {variant}; skipping.")
            continue
        print(f"Running variant: {variant} ...")
        output = run_spx_0dte_put_spread(
            data=data,
            start_date=start,
            end_date=end,
            variant=variant,
            config={},
        )
        results.append({
            "variant": variant,
            "metrics": output["metrics"],
            "strategy_parameters": output["strategy_parameters"],
            "sub_period_metrics": output.get("sub_period_metrics") or {},
            "total_trades": len(output.get("closed_trades") or []),
        })

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d")
    json_path = REPORTS_DIR / f"spx_0dte_sweep_{ts}.json"
    md_path = REPORTS_DIR / f"spx_0dte_sweep_{ts}.md"

    payload = {
        "report_date": datetime.now().isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "variants": results,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    # Markdown summary
    lines = [
        "# SPX 0DTE Short Put Spread Parameter Sweep",
        "",
        f"**Generated:** {payload['report_date']}",
        f"**Period:** {start} to {end}",
        "",
        "## Per-variant metrics",
        "",
        "| Variant | Trades | Win rate | Sharpe | Sortino | Max DD % | Total return % | Bad-day conc % |",
        "|---------|--------|----------|--------|---------|----------|----------------|----------------|",
    ]
    for r in results:
        m = r["metrics"]
        lines.append(
            f"| {r['variant']} | {m.get('total_trades', 0)} | {m.get('win_rate', 0):.1f} | "
            f"{m.get('sharpe_ratio', 0):.2f} | {m.get('sortino_ratio', 0):.2f} | "
            f"{m.get('max_drawdown_pct', 0):.1f} | {m.get('total_return_pct', 0):.1f} | "
            f"{m.get('bad_day_concentration_pct', 0):.1f} |"
        )
    lines.extend(["", "## Sub-period breakdown", ""])
    if results:
        first = results[0]
        for period, pm in (first.get("sub_period_metrics") or {}).items():
            lines.append(f"### {period}")
            lines.append(f"- Trades: {pm.get('total_trades', 0)}, Win rate: {pm.get('win_rate', 0):.1f}%, Return: {pm.get('total_return_pct', 0):.1f}%")
            lines.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
