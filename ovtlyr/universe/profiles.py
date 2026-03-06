import logging
import re
from typing import List

import yaml

logger = logging.getLogger(__name__)

_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9]{0,9}$")


def _load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _normalize_symbols(symbols: list, profile_name: str) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in symbols or []:
        if raw is None:
            continue
        symbol = str(raw).strip().upper()
        if not symbol:
            continue
        if not _SYMBOL_RE.match(symbol):
            logger.warning(f"Skipping invalid symbol '{raw}' in universe profile '{profile_name}'")
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        out.append(symbol)
    return out


def available_universes(universes_path: str = "config/universes.yaml") -> List[str]:
    data = _load_yaml(universes_path)
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        return []
    return sorted(profiles.keys())


def load_universe(
    profile_name: str,
    universes_path: str = "config/universes.yaml",
    watchlist_path: str = "config/watchlist.yaml",
) -> List[str]:
    """
    Load a named universe profile.

    If profile is missing/empty, fallback to `default`.
    If `default` is missing, fallback to `config/watchlist.yaml`.
    """
    data = _load_yaml(universes_path)
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}

    requested = profile_name or "default"
    cfg = profiles.get(requested)
    if cfg is None:
        logger.warning(f"Universe profile '{requested}' not found. Falling back to 'default'")
        cfg = profiles.get("default")
        requested = "default"

    symbols = []
    if isinstance(cfg, dict):
        symbols = cfg.get("symbols", []) or []

    normalized = _normalize_symbols(symbols, requested)
    if normalized:
        return normalized

    logger.warning("Universe profiles are empty or invalid. Falling back to config/watchlist.yaml")
    watchlist = _load_yaml(watchlist_path).get("symbols", []) or []
    return _normalize_symbols(watchlist, "watchlist_fallback")

