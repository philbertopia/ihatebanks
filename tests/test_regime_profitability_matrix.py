from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "run_regime_profitability_matrix.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("regime_profitability_matrix", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fake_combined_row(
    experiment_id: str,
    overlay_profile: str,
    *,
    oos_return: float,
    oos_sharpe: float,
    oos_dd: float,
    passed: bool,
    full_return: float,
    research_oos: float | None = None,
):
    research = {
        "status": "completed",
        "full_period": {"total_return_pct": 0.0},
        "walkforward_summary": {"avg_total_return_pct": research_oos},
        "walkforward_windows": [],
    }
    if research_oos is None:
        research = {
            "status": "skipped_incomplete_coverage",
            "full_period": None,
            "walkforward_summary": None,
            "walkforward_windows": [],
        }
    return {
        "experiment_id": experiment_id,
        "overlay_profile": overlay_profile,
        "official": {
            "full_period": {"total_return_pct": full_return},
            "walkforward_summary": {
                "avg_total_return_pct": oos_return,
                "avg_sharpe_ratio": oos_sharpe,
                "avg_max_drawdown_pct": oos_dd,
                "pass_validation": passed,
            },
            "walkforward_windows": [],
        },
        "research": research,
    }


def test_build_matrix_specs_expands_to_twenty_seven_rows():
    module = _load_module()

    specs = module.build_matrix_specs()

    assert len(specs) == 27
    assert {row["overlay_profile"] for row in specs} == {"none", "regime_core_base", "regime_core_overlay"}


def test_rank_matrix_rows_prioritizes_pass_and_guardrail():
    module = _load_module()
    rows = [
        _fake_combined_row("base", "none", oos_return=17.0, oos_sharpe=7.0, oos_dd=1.1, passed=True, full_return=180.0),
        _fake_combined_row("candidate_a", "none", oos_return=18.0, oos_sharpe=6.0, oos_dd=2.5, passed=True, full_return=190.0),
        _fake_combined_row("candidate_b", "none", oos_return=17.5, oos_sharpe=7.5, oos_dd=1.4, passed=True, full_return=188.0),
        _fake_combined_row("candidate_c", "none", oos_return=19.0, oos_sharpe=8.0, oos_dd=1.0, passed=False, full_return=200.0),
    ]

    ranked = module.rank_matrix_rows(rows)

    assert ranked[0]["experiment_id"] == "candidate_b"
    assert ranked[0]["eligible"] is True
    assert ranked[-1]["experiment_id"] == "candidate_c"


def test_prepare_research_frame_marks_skip_when_gap_fill_fails(monkeypatch):
    module = _load_module()
    cache_frame = pd.DataFrame(
        [
            {"date": pd.Timestamp("2020-01-02").date(), "underlying": "SPY", "underlying_price": 100.0},
            {"date": pd.Timestamp("2020-01-02").date(), "underlying": "QQQ", "underlying_price": 200.0},
        ]
    )

    def _boom(symbols, intervals):
        raise RuntimeError("offline")

    monkeypatch.setattr(module, "download_gap_fill", _boom)

    result = module.prepare_research_frame(
        cache_frame,
        start_day=pd.Timestamp("2016-01-01").date(),
        end_day=pd.Timestamp("2025-12-31").date(),
    )

    assert result["status"] == "skipped_incomplete_coverage"
    assert result["frame"] is None
    assert result["skip_reason"] == "offline"
    assert result["missing_intervals"]


def test_build_payload_and_report_writes_only_requested_outputs(tmp_path):
    module = _load_module()
    official_rows = [
        {
            "experiment_id": "base",
            "overlay_profile": "none",
            "score_sizing": "none",
            "bull_risk_pct": 0.015,
            "bear_risk_pct": 0.009,
            "neutral_risk_pct": 0.009,
            "research_overrides": {},
            "full_period": {"total_return_pct": 180.0, "sharpe_ratio": 5.0, "max_drawdown_pct": 1.2, "total_trades": 100},
            "walkforward_summary": {
                "avg_total_return_pct": 17.0,
                "avg_sharpe_ratio": 7.0,
                "avg_max_drawdown_pct": 1.1,
                "pass_validation": True,
            },
            "walkforward_windows": [],
            "component_metrics": {},
            "trade_records": [],
        }
    ]
    payload = module.build_payload(
        official_rows,
        research_rows=None,
        official_start=pd.Timestamp("2020-01-02").date(),
        official_end=pd.Timestamp("2025-12-31").date(),
        research_start=pd.Timestamp("2016-01-01").date(),
        research_end=pd.Timestamp("2025-12-31").date(),
        train_days=504,
        test_days=126,
        step_days=126,
        research_status={"status": "skipped_by_flag", "missing_intervals": [], "skip_reason": "skip"},
    )

    json_path = tmp_path / "matrix.json"
    md_path = tmp_path / "matrix.md"
    module.write_json_report(json_path, payload)
    module.write_markdown_report(md_path, payload)

    created = {path.name for path in tmp_path.iterdir()}
    assert created == {"matrix.json", "matrix.md"}
