import pytest
from ovtlyr.scanner.filters import (
    credit_spread_setup_score,
    convex_swing_setup_score,
    passes_delta_filter,
    passes_extrinsic_filter,
    passes_open_interest_filter,
    passes_spread_filter,
    score_candidate,
    filter_candidates,
)


def test_delta_filter_pass():
    assert passes_delta_filter(0.80) is True
    assert passes_delta_filter(0.75) is True
    assert passes_delta_filter(0.85) is True


def test_delta_filter_fail():
    assert passes_delta_filter(0.60) is False
    assert passes_delta_filter(0.95) is False


def test_extrinsic_filter():
    assert passes_extrinsic_filter(0.20) is True
    assert passes_extrinsic_filter(0.30) is True
    assert passes_extrinsic_filter(0.31) is False


def test_oi_filter():
    assert passes_open_interest_filter(500) is True
    assert passes_open_interest_filter(499) is False
    # None OI = unknown; allow through by default (indicative feed doesn't return OI)
    assert passes_open_interest_filter(None) is True
    # When require=True, None OI should fail
    assert passes_open_interest_filter(None, require=True) is False


def test_spread_filter():
    assert passes_spread_filter(0.05) is True
    assert passes_spread_filter(0.10) is True
    assert passes_spread_filter(0.11) is False


def test_spread_filter_with_absolute_cap():
    assert passes_spread_filter(0.05, spread_abs=0.40, max_spread_abs=0.50) is True
    assert passes_spread_filter(0.05, spread_abs=0.55, max_spread_abs=0.50) is False


def test_score_candidate_perfect():
    candidate = {
        "delta": 0.80,
        "extrinsic_pct": 0.0,
        "open_interest": 10000,
        "spread_pct": 0.0,
    }
    score = score_candidate(candidate)
    assert score == pytest.approx(100.0)


def test_score_candidate_bad():
    candidate = {
        "delta": 0.60,
        "extrinsic_pct": 0.50,
        "open_interest": 1,
        "spread_pct": 0.50,
    }
    score = score_candidate(candidate)
    assert score < 30.0


def test_credit_spread_setup_score_prefers_bullish_put_credit_context():
    good = credit_spread_setup_score(
        {
            "side": "put",
            "regime": "bull",
            "ret3": -0.022,
            "rsi14": 43.0,
            "iv_percentile": 62.0,
            "breadth_pct": 75.0,
            "execution_quality": 0.85,
        }
    )
    bad = credit_spread_setup_score(
        {
            "side": "put",
            "regime": "bear",
            "ret3": 0.03,
            "rsi14": 64.0,
            "iv_percentile": 15.0,
            "breadth_pct": 30.0,
            "execution_quality": 0.40,
        }
    )

    assert good > bad
    assert good >= 70.0


def test_convex_swing_setup_score_prefers_low_iv_bullish_pullback():
    good = convex_swing_setup_score(
        {
            "style": "pullback",
            "regime": "bull",
            "ret3": -0.03,
            "ret5": -0.01,
            "rsi14": 44.0,
            "iv_percentile": 18.0,
            "breadth_pct": 80.0,
            "execution_quality": 0.80,
        }
    )
    bad = convex_swing_setup_score(
        {
            "style": "pullback",
            "regime": "neutral",
            "ret3": 0.01,
            "ret5": 0.03,
            "rsi14": 62.0,
            "iv_percentile": 70.0,
            "breadth_pct": 40.0,
            "execution_quality": 0.40,
        }
    )

    assert good > bad
    assert good >= 70.0


def test_filter_candidates_basic():
    """filter_candidates should return only qualifying contracts."""
    config = {
        "strategy": {
            "target_delta": 0.80,
            "delta_tolerance": 0.10,
            "max_extrinsic_pct": 0.30,
            "min_open_interest": 100,
            "max_spread_pct": 0.10,
            "option_type": "call",
        }
    }
    underlying_price = 200.0
    # A qualifying contract at ~80 delta, low extrinsic, good OI
    chain = {
        "AAPL240321C00160000": {
            "contract_symbol": "AAPL240321C00160000",
            "underlying": "AAPL",
            "option_type": "call",
            "strike": 160.0,
            "expiration_date": "2024-03-21",
            "bid": 39.50,
            "ask": 40.00,
            "delta": 0.81,
            "open_interest": 1000,
            "implied_volatility": 0.25,
        },
        # Disqualified: delta too low
        "AAPL240321C00190000": {
            "contract_symbol": "AAPL240321C00190000",
            "underlying": "AAPL",
            "option_type": "call",
            "strike": 190.0,
            "expiration_date": "2024-03-21",
            "bid": 12.0,
            "ask": 13.0,
            "delta": 0.50,
            "open_interest": 2000,
            "implied_volatility": 0.30,
        },
    }

    from datetime import date
    results = filter_candidates(chain, underlying_price, config, today=date(2024, 1, 15))
    # Only the 80-delta contract should qualify
    assert len(results) == 1
    assert results[0]["contract_symbol"] == "AAPL240321C00160000"


def test_filter_candidates_respects_dte_window():
    config = {
        "strategy": {
            "target_delta": 0.80,
            "delta_tolerance": 0.10,
            "max_extrinsic_pct": 0.30,
            "min_open_interest": 100,
            "max_spread_pct": 0.10,
            "option_type": "call",
            "min_dte": 30,
            "max_dte": 60,
        }
    }
    chain = {
        # DTE ~32 from 2024-01-15 => allowed
        "AAPL240216C00160000": {
            "contract_symbol": "AAPL240216C00160000",
            "underlying": "AAPL",
            "option_type": "call",
            "strike": 160.0,
            "expiration_date": "2024-02-16",
            "bid": 39.5,
            "ask": 40.0,
            "delta": 0.81,
            "open_interest": 1000,
            "implied_volatility": 0.25,
        },
        # DTE ~4 from 2024-01-15 => blocked by min_dte
        "AAPL240119C00160000": {
            "contract_symbol": "AAPL240119C00160000",
            "underlying": "AAPL",
            "option_type": "call",
            "strike": 160.0,
            "expiration_date": "2024-01-19",
            "bid": 39.5,
            "ask": 40.0,
            "delta": 0.81,
            "open_interest": 1000,
            "implied_volatility": 0.25,
        },
    }

    from datetime import date
    results = filter_candidates(chain, 200.0, config, today=date(2024, 1, 15))
    assert len(results) == 1
    assert results[0]["contract_symbol"] == "AAPL240216C00160000"


def test_filter_candidates_monthly_only_blocks_weekly():
    config = {
        "strategy": {
            "target_delta": 0.80,
            "delta_tolerance": 0.10,
            "max_extrinsic_pct": 0.30,
            "min_open_interest": 100,
            "max_spread_pct": 0.10,
            "option_type": "call",
            "min_dte": 30,
            "max_dte": 60,
            "monthly_only": True,
        }
    }
    chain = {
        # Monthly Feb 2024 expiry (3rd Friday)
        "AAPL240216C00160000": {
            "contract_symbol": "AAPL240216C00160000",
            "underlying": "AAPL",
            "option_type": "call",
            "strike": 160.0,
            "expiration_date": "2024-02-16",
            "bid": 39.5,
            "ask": 40.0,
            "delta": 0.81,
            "open_interest": 1000,
            "implied_volatility": 0.25,
        },
        # Weekly Feb 2024 expiry (not 3rd Friday)
        "AAPL240223C00160000": {
            "contract_symbol": "AAPL240223C00160000",
            "underlying": "AAPL",
            "option_type": "call",
            "strike": 160.0,
            "expiration_date": "2024-02-23",
            "bid": 39.5,
            "ask": 40.0,
            "delta": 0.81,
            "open_interest": 1000,
            "implied_volatility": 0.25,
        },
    }

    from datetime import date
    results = filter_candidates(chain, 200.0, config, today=date(2024, 1, 15))
    assert len(results) == 1
    assert results[0]["contract_symbol"] == "AAPL240216C00160000"


def test_filter_candidates_respects_absolute_spread_cap():
    config = {
        "strategy": {
            "target_delta": 0.80,
            "delta_tolerance": 0.10,
            "max_extrinsic_pct": 0.30,
            "min_open_interest": 100,
            "max_spread_pct": 0.20,
            "max_spread_abs": 0.50,
            "option_type": "call",
        }
    }
    chain = {
        "TIGHT": {
            "contract_symbol": "TIGHT",
            "underlying": "AAPL",
            "option_type": "call",
            "strike": 160.0,
            "expiration_date": "2024-02-16",
            "bid": 39.50,
            "ask": 39.90,
            "delta": 0.81,
            "open_interest": 1000,
            "implied_volatility": 0.25,
        },
        "WIDE": {
            "contract_symbol": "WIDE",
            "underlying": "AAPL",
            "option_type": "call",
            "strike": 160.0,
            "expiration_date": "2024-02-16",
            "bid": 39.00,
            "ask": 39.70,
            "delta": 0.81,
            "open_interest": 1000,
            "implied_volatility": 0.25,
        },
    }

    from datetime import date
    results = filter_candidates(chain, 200.0, config, today=date(2024, 1, 15))
    assert len(results) == 1
    assert results[0]["contract_symbol"] == "TIGHT"
