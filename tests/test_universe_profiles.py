from pathlib import Path

from ovtlyr.universe.profiles import available_universes, load_universe


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_available_universes_reads_profile_names(tmp_path):
    universes_path = _write(
        tmp_path / "universes.yaml",
        """
profiles:
  default:
    symbols: [AAPL]
  top_50:
    symbols: [AAPL, MSFT]
""".strip(),
    )
    assert available_universes(universes_path) == ["default", "top_50"]


def test_load_universe_normalizes_dedupes_and_skips_invalid(tmp_path):
    universes_path = _write(
        tmp_path / "universes.yaml",
        """
profiles:
  custom:
    symbols: [aapl, AAPL, " msft ", "", null, "brk.b", TSLA]
""".strip(),
    )
    watchlist_path = _write(tmp_path / "watchlist.yaml", "symbols: [SPY]")
    # brk.b is skipped by symbol hygiene (unsupported char '.')
    assert load_universe("custom", universes_path, watchlist_path) == ["AAPL", "MSFT", "TSLA"]


def test_load_universe_falls_back_to_default(tmp_path):
    universes_path = _write(
        tmp_path / "universes.yaml",
        """
profiles:
  default:
    symbols: [SPY, QQQ]
""".strip(),
    )
    watchlist_path = _write(tmp_path / "watchlist.yaml", "symbols: [AAPL]")
    assert load_universe("missing_profile", universes_path, watchlist_path) == ["SPY", "QQQ"]


def test_load_universe_falls_back_to_watchlist_if_profiles_empty(tmp_path):
    universes_path = _write(tmp_path / "universes.yaml", "profiles: {}")
    watchlist_path = _write(tmp_path / "watchlist.yaml", "symbols: [AAPL, MSFT]")
    assert load_universe("default", universes_path, watchlist_path) == ["AAPL", "MSFT"]

