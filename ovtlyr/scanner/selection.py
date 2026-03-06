from typing import Any, Dict, Iterable, List, Optional

from ovtlyr.strategy.risk_controls import correlation_gate


def select_ranked_entries(
    candidates: List[Dict[str, Any]],
    max_positions: int,
    open_underlyings: Optional[Iterable[str]] = None,
    corr_frame: Any = None,
    max_pair_corr: float = 0.75,
    max_high_corr_positions: int = 2,
) -> List[Dict[str, Any]]:
    """
    Select the best candidate per underlying, then globally rank by score.
    Returns at most `max_positions` entries.
    """
    best_by_underlying: Dict[str, Dict[str, Any]] = {}
    for c in candidates:
        underlying = str(c.get("underlying") or "").strip().upper()
        if not underlying:
            continue
        score = float(c.get("score", 0.0) or 0.0)
        prev = best_by_underlying.get(underlying)
        if prev is None or score > float(prev.get("score", 0.0) or 0.0):
            best_by_underlying[underlying] = c

    ranked_all = sorted(
        best_by_underlying.values(),
        key=lambda x: float(x.get("score", 0.0) or 0.0),
        reverse=True,
    )

    selected: List[Dict[str, Any]] = []
    open_set = {str(s).upper() for s in (open_underlyings or []) if str(s).strip()}
    for row in ranked_all:
        if len(selected) >= max_positions:
            break
        symbol = str(row.get("underlying", "")).upper()
        if symbol in open_set:
            continue
        ok, _ = correlation_gate(
            candidate_symbol=symbol,
            open_symbols=list(open_set),
            corr_frame=corr_frame,
            max_corr=max_pair_corr,
            max_cluster=max_high_corr_positions,
        )
        if not ok:
            continue
        selected.append(row)
        open_set.add(symbol)

    return selected
