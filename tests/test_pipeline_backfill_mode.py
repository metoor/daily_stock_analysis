# -*- coding: utf-8 -*-
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest


def _build_pipeline_with_real_db():
    """真实内存 db + 真实 pipeline.db 取数路径，仅 mock LLM/网络/趋势分析。"""
    from src.core.pipeline import StockAnalysisPipeline
    from src.config import Config
    from src.storage import DatabaseManager

    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")

    target = date(2026, 6, 10)
    rows = []
    for i in range(10):
        d = date(2026, 6, 1) + timedelta(days=i)
        rows.append({
            "date": d,
            "open": 9.0 + i * 0.1,
            "high": 10.0 + i * 0.1,
            "low": 8.5 + i * 0.1,
            "close": 9.5 + i * 0.1,
            "volume": 1000.0 + i * 100,
            "pct_chg": 1.0 + i * 0.1,
            "ma5": 9.0,
            "ma10": 8.8,
            "ma20": 8.5,
        })
    df = pd.DataFrame(rows)
    df["code"] = "600519"
    db.save_daily_data(df, "600519", "test")

    pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
    pipeline.db = db
    pipeline.config = MagicMock(spec=Config)
    pipeline.config.enable_realtime_quote = True
    pipeline.config.report_language = "zh"
    pipeline.config.agent_mode = False
    pipeline.config.agent_skills = []
    pipeline.config.fundamental_stage_timeout_seconds = 1
    pipeline.config.daily_market_context_enabled = False
    pipeline.config.market_review_enabled = False
    pipeline.config.litellm_model = "test-model"
    pipeline.query_source = "backfill"
    pipeline.analysis_phase = "auto"
    pipeline.analysis_skills = None
    pipeline.save_context_snapshot = True
    pipeline.portfolio_context = None

    pipeline.fetcher_manager = MagicMock()
    pipeline.fetcher_manager.get_stock_name.return_value = "测试股"
    pipeline.fetcher_manager.get_realtime_quote.return_value = None
    pipeline.fetcher_manager.get_chip_distribution.return_value = None
    pipeline.fetcher_manager.get_fundamental_context.return_value = {}
    pipeline.fetcher_manager.build_failed_fundamental_context.return_value = {}

    pipeline.search_service = MagicMock()
    pipeline.search_service.is_available = True
    pipeline.search_service.search_comprehensive_intel = MagicMock(return_value={})
    pipeline.social_sentiment_service = None

    pipeline.trend_analyzer = MagicMock()
    pipeline.trend_analyzer.analyze.return_value = SimpleNamespace(
        trend_status=SimpleNamespace(value="up"),
        buy_signal=SimpleNamespace(value="none"),
        signal_score=50,
        ma_alignment="bull",
        trend_strength=0.5,
        bias_ma5=0.01,
        bias_ma10=0.02,
        volume_status=SimpleNamespace(value="normal"),
        volume_trend="up",
        signal_reasons=[],
        risk_factors=[],
        ma5=10.0,
        ma10=9.8,
        ma20=9.5,
    )

    captured = {}

    def _fake_analyze(enhanced_context, **kwargs):
        captured["enhanced_context"] = enhanced_context
        return SimpleNamespace(
            success=True, code="600519", name="测试股",
            current_price=None, change_pct=None, query_id="q",
            operation_advice="持有", sentiment_score=60,
            model_used="test-model", report_language="zh",
            analysis_summary="", news_summary="", technical_analysis="",
            fundamental_analysis="", risk_warning="", to_dict=lambda: {},
            error_message=None,
        )

    pipeline.analyzer = MagicMock()
    pipeline.analyzer.analyze = _fake_analyze
    pipeline._emit_progress = MagicMock()
    db.save_analysis_history = MagicMock(return_value=1)
    db.save_fundamental_snapshot = MagicMock()

    return pipeline, captured, target


def test_backfill_uses_target_date_context():
    pipeline, captured, target = _build_pipeline_with_real_db()
    pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q1",
        target_date=target,
        backfill_mode=True,
    )
    ec = captured["enhanced_context"]
    assert ec["date"] == "2026-06-10"
    assert ec["today"]["date"] == date(2026, 6, 10)
    assert ec["today"]["close"] == 10.4
    assert ec["backfill"]["target_date"] == "2026-06-10"
    assert ec["realtime"]["price"] == 10.4
    assert ec["realtime"]["change_pct"] == 1.9
    pipeline.search_service.search_comprehensive_intel.assert_not_called()


def test_backfill_missing_target_bar_returns_none():
    pipeline, captured, target = _build_pipeline_with_real_db()
    from src.storage import StockDaily
    with pipeline.db.get_session() as session:
        session.query(StockDaily).filter(
            StockDaily.code == "600519",
            StockDaily.date == target,
        ).delete()
        session.commit()
    result = pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q2",
        target_date=target,
        backfill_mode=True,
    )
    assert result is None


def test_normal_mode_does_not_set_backfill_marker():
    pipeline, captured, _ = _build_pipeline_with_real_db()
    pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q3",
        current_time=None,
        backfill_mode=False,
    )
    assert "backfill" not in captured["enhanced_context"]
