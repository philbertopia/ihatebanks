import logging
import time
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

from ovtlyr.api.client import AlpacaClients
from ovtlyr.api.options_data import (
    fetch_option_chain,
    fetch_stock_trend_state,
    fetch_underlying_price,
    snapshot_to_dict,
)
from ovtlyr.database.repository import Repository
from ovtlyr.scanner.expiration import get_target_expirations
from ovtlyr.scanner.filters import filter_candidates

logger = logging.getLogger(__name__)


class DailyScanner:
    def __init__(self, clients: AlpacaClients, repo: Repository, config: Dict[str, Any]):
        self.clients = clients
        self.repo = repo
        self.config = config
        self.strategy = config.get("strategy", {})

    def run(self, watchlist: List[str]) -> List[Dict]:
        """
        Main entry point. Scans each symbol in watchlist and returns all qualifying candidates.
        Also persists results to scan_results table.
        """
        all_candidates: List[Dict] = []
        today = date.today()
        scanner_cfg = self.config.get("scanner", {})
        pause_ms = int(scanner_cfg.get("request_pause_ms", 0) or 0)
        started_at = time.perf_counter()
        attempted = 0
        scanned = 0
        failed = 0
        skipped_existing = 0

        for i, symbol in enumerate(watchlist):
            attempted += 1
            if self._has_existing_position(symbol):
                logger.info(f"Skipping {symbol}: already have an open position")
                skipped_existing += 1
                continue

            try:
                candidates = self.scan_symbol(symbol, today)
                scanned += 1
            except Exception as e:
                failed += 1
                logger.exception(f"Error scanning {symbol}: {e}")
                continue

            all_candidates.extend(candidates)

            # Persist to DB
            for c in candidates:
                try:
                    self.repo.insert_scan_result({
                        "scan_date": today.isoformat(),
                        "underlying": symbol,
                        "contract_symbol": c["contract_symbol"],
                        "strike": c["strike"],
                        "expiration_date": c["expiration_date"],
                        "dte": c["dte"],
                        "delta": c["delta"],
                        "ask": c["ask"],
                        "bid": c["bid"],
                        "spread_pct": c["spread_pct"],
                        "open_interest": c.get("open_interest"),
                        "extrinsic_value": c["extrinsic_value"],
                        "extrinsic_pct": c["extrinsic_pct"],
                        "implied_volatility": c.get("implied_volatility"),
                        "score": c["score"],
                        "action_taken": "none",
                    })
                except Exception as e:
                    logger.debug(f"Could not insert scan result for {c['contract_symbol']}: {e}")

            if pause_ms > 0 and i < (len(watchlist) - 1):
                time.sleep(pause_ms / 1000.0)

        elapsed = time.perf_counter() - started_at
        logger.info(
            "Scan complete. Found %d qualifying contracts across %d symbols | "
            "attempted=%d scanned=%d failed=%d skipped_existing=%d elapsed=%.2fs",
            len(all_candidates),
            len(watchlist),
            attempted,
            scanned,
            failed,
            skipped_existing,
            elapsed,
        )
        return all_candidates

    def scan_symbol(self, symbol: str, today: date = None) -> List[Dict]:
        """Fetch chain and filter for a single symbol. Returns sorted candidate list."""
        if today is None:
            today = date.today()

        min_dte = self.strategy.get("min_dte", 8)
        max_dte = self.strategy.get("max_dte", 60)
        prefer_monthly = self.strategy.get("prefer_monthly", True)
        monthly_only = self.strategy.get("monthly_only", False)
        option_type = self.strategy.get("option_type", "call")
        feed = self.config.get("alpaca", {}).get("feed", "indicative")
        require_symbol_bullish_trend = self.strategy.get("require_symbol_bullish_trend", False)

        if require_symbol_bullish_trend:
            trend = fetch_stock_trend_state(
                client=self.clients.stock_data,
                symbol=symbol,
                ema_fast=int(self.strategy.get("trend_ema_fast", 10)),
                ema_medium=int(self.strategy.get("trend_ema_medium", 20)),
                ema_slow=int(self.strategy.get("trend_ema_slow", 50)),
                lookback_days=int(self.strategy.get("trend_lookback_days", 180)),
            )
            if not trend:
                logger.warning(f"Skipping {symbol}: could not evaluate trend template")
                return []
            if not trend.get("is_bullish", False):
                logger.info(
                    f"Skipping {symbol}: trend not bullish "
                    f"(px={trend['price']:.2f}, ema{self.strategy.get('trend_ema_fast', 10)}={trend['ema_fast']:.2f}, "
                    f"ema{self.strategy.get('trend_ema_medium', 20)}={trend['ema_medium']:.2f}, "
                    f"ema{self.strategy.get('trend_ema_slow', 50)}={trend['ema_slow']:.2f})"
                )
                return []

        expirations = get_target_expirations(
            min_dte=min_dte,
            max_dte=max_dte,
            today=today,
            prefer_monthly=prefer_monthly,
            include_weekly_fallback=not monthly_only,
        )
        if not expirations:
            logger.warning(f"{symbol}: no qualifying expiration dates found in {min_dte}-{max_dte} DTE window")
            return []

        underlying_price = fetch_underlying_price(self.clients.stock_data, symbol)
        if not underlying_price:
            logger.warning(f"{symbol}: could not fetch underlying price")
            return []

        logger.info(f"Scanning {symbol} @ ${underlying_price:.2f} | {len(expirations)} expirations")

        all_candidates: List[Dict] = []

        for exp_date in expirations:
            # Fetch chain for exact expiration date
            chain = fetch_option_chain(
                client=self.clients.options_data,
                symbol=symbol,
                expiration_date_gte=exp_date,
                expiration_date_lte=exp_date,
                option_type=option_type,
                feed=feed,
            )

            if not chain:
                continue

            # Flatten snapshots
            flat_chain = {}
            for contract_sym, snap in chain.items():
                flat_chain[contract_sym] = snapshot_to_dict(contract_sym, snap)

            candidates = filter_candidates(flat_chain, underlying_price, self.config, today)
            all_candidates.extend(candidates)

        # Deduplicate by contract_symbol and re-sort
        seen = set()
        unique: List[Dict] = []
        for c in sorted(all_candidates, key=lambda x: x["score"], reverse=True):
            if c["contract_symbol"] not in seen:
                seen.add(c["contract_symbol"])
                unique.append(c)

        if unique:
            best = unique[0]
            logger.info(
                f"  {symbol}: {len(unique)} candidates | Best: {best['contract_symbol']} "
                f"d={best['delta']:.2f} ext={best['extrinsic_pct']:.1%} "
                f"OI={best.get('open_interest', 'N/A')} score={best['score']:.1f}"
            )
        else:
            logger.info(f"  {symbol}: no qualifying candidates")

        return unique

    def _has_existing_position(self, symbol: str) -> bool:
        pos = self.repo.get_open_position_by_underlying(symbol)
        return pos is not None

    def find_replacement_for_roll(self, underlying: str, today: date = None) -> Optional[Dict]:
        """
        Find the best replacement contract for a position that needs to be rolled.
        Targets ~80 delta in the next monthly expiration with sufficient DTE.
        """
        if today is None:
            today = date.today()

        candidates = self.scan_symbol(underlying, today)
        return candidates[0] if candidates else None
