import logging
from datetime import date
from typing import List, Dict, Any

from tabulate import tabulate
from colorama import Fore, Style, init

from ovtlyr.database.repository import Repository
from ovtlyr.reporting.stats import get_portfolio_stats
from ovtlyr.utils.math_utils import compute_unrealized_pnl

init(autoreset=True)
logger = logging.getLogger(__name__)

SEP = "=" * 70


def _pnl_color(val: float) -> str:
    if val > 0:
        return Fore.GREEN + f"+${val:,.2f}" + Style.RESET_ALL
    elif val < 0:
        return Fore.RED + f"-${abs(val):,.2f}" + Style.RESET_ALL
    return f"${val:,.2f}"


def _pct_color(val: float) -> str:
    s = f"{val:.1%}"
    if val >= 0.70:
        return Fore.GREEN + s + Style.RESET_ALL
    elif val >= 0.50:
        return Fore.YELLOW + s + Style.RESET_ALL
    return Fore.RED + s + Style.RESET_ALL


class DailyReport:
    def __init__(
        self,
        repo: Repository,
        scan_candidates: List[Dict] = None,
        rolls_executed: List[Dict] = None,
        positions_opened: List[Dict] = None,
    ):
        self.repo = repo
        self.scan_candidates = scan_candidates or []
        self.rolls_executed = rolls_executed or []
        self.positions_opened = positions_opened or []

    def generate(self) -> str:
        today = date.today().isoformat()
        lines: List[str] = []

        lines.append(SEP)
        lines.append(f"  OVTLYR DAILY REPORT — {today}")
        lines.append(SEP)

        # ── Open Positions ──
        open_positions = self.repo.get_open_positions()
        lines.append(f"\n{'OPEN POSITIONS':} ({len(open_positions)})")
        lines.append("-" * 70)

        if open_positions:
            rows = []
            for p in open_positions:
                entry = p["entry_price"]
                current = p.get("current_price") or entry
                pnl = compute_unrealized_pnl(entry, current, p["qty"])
                pnl_str = _pnl_color(pnl)
                delta_str = f"{p.get('current_delta') or p.get('entry_delta', 0):.3f}"
                rows.append([
                    p["underlying"],
                    p["contract_symbol"][-15:],
                    f"${p['strike']:.0f}",
                    p["expiration_date"],
                    delta_str,
                    f"${entry:.2f}",
                    f"${current:.2f}",
                    pnl_str,
                ])
            headers = ["Symbol", "Contract", "Strike", "Expiry", "Delta", "Entry", "Current", "P&L"]
            lines.append(tabulate(rows, headers=headers, tablefmt="simple"))
        else:
            lines.append("  No open positions")

        # ── Rolls ──
        lines.append(f"\n{'ROLLS EXECUTED TODAY':} ({len(self.rolls_executed)})")
        lines.append("-" * 70)
        if self.rolls_executed:
            for r in self.rolls_executed:
                lines.append(f"  {r}")
        else:
            lines.append("  None")

        # ── New Positions Opened ──
        lines.append(f"\n{'NEW POSITIONS OPENED TODAY':} ({len(self.positions_opened)})")
        lines.append("-" * 70)
        if self.positions_opened:
            for p in self.positions_opened:
                lines.append(
                    f"  {p.get('underlying','?'):6s} | {p['contract_symbol']} | "
                    f"d={p.get('delta',0):.2f} | ext={p.get('extrinsic_pct',0):.1%} | "
                    f"score={p.get('score',0):.1f}"
                )
        else:
            lines.append("  None")

        # ── Today's Scan Candidates ──
        lines.append(f"\n{'TOP SCAN CANDIDATES TODAY':}")
        lines.append("-" * 70)
        if self.scan_candidates:
            # Group by underlying
            by_sym: Dict[str, List] = {}
            for c in self.scan_candidates:
                sym = c.get("underlying", "?")
                by_sym.setdefault(sym, []).append(c)

            for sym, cands in sorted(by_sym.items()):
                top = cands[:3]
                lines.append(f"  {sym} ({len(cands)} qualifying):")
                for c in top:
                    lines.append(
                        f"    {c['contract_symbol']} | "
                        f"d={c.get('delta',0):.2f} | "
                        f"ext={c.get('extrinsic_pct',0):.1%} | "
                        f"OI={c.get('open_interest','N/A')} | "
                        f"score={c.get('score',0):.1f}"
                    )
        else:
            lines.append("  No qualifying candidates found today")

        # ── Portfolio Summary ──
        stats = get_portfolio_stats(self.repo)
        lines.append(f"\n{'PORTFOLIO SUMMARY':}")
        lines.append("-" * 70)
        lines.append(f"  Open Positions:     {stats.get('open_positions', 0)}")
        lines.append(f"  Portfolio Delta:    {stats.get('portfolio_delta', 0):.4f}")
        lines.append(f"  Unrealized P&L:     {_pnl_color(stats.get('total_unrealized_pnl', 0))}")
        lines.append(f"  Realized P&L:       {_pnl_color(stats.get('total_realized_pnl', 0) or 0)}")

        total_closed = stats.get("total_closed", 0) or 0
        if total_closed > 0:
            lines.append(f"  Closed Trades:      {total_closed}")
            lines.append(f"  Win Rate:           {_pct_color(stats.get('win_rate', 0) / 100)}")
            pf = stats.get("profit_factor", 0)
            pf_str = f"{pf:.2f}" if pf != float("inf") else "∞"
            lines.append(f"  Profit Factor:      {pf_str}")

        lines.append(SEP)

        report = "\n".join(lines)
        print(report)

        # Also write to file if configured
        report_path = "logs/daily_report.txt"
        try:
            import os
            os.makedirs("logs", exist_ok=True)
            with open(report_path, "a", encoding="utf-8") as f:
                # Strip color codes for file
                import re
                clean = re.sub(r'\x1b\[[0-9;]*m', '', report)
                f.write(clean + "\n\n")
        except Exception as e:
            logger.debug(f"Could not write report to file: {e}")

        return report
