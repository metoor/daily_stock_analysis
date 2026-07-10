# -*- coding: utf-8 -*-
from datetime import datetime, date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _build_pipeline_with_mocks():
    from src.core.pipeline import StockAnalysisPipeline
    from src.config import Config

    pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
    pipeline.config = MagicMock(spec=Config)
    pipeline.config.enable_realtime_quote = True
    pipeline.config.report_language = "zh"
    pipeline.config.agent_mode = False
    pipeline.config.agent_skills = []
    pipeline.config.fundamental_stage_timeout_seconds = 1
    pipeline.query_source = "api"
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

    pipeline.db = MagicMock()
    # 返回一根 bar，使 context['date'] 落到目标日
    bar = SimpleNamespace(
        to_dict=lambda: {
            "date": "2026-06-10", "close": 10.0, "open": 9.5,
            "high": 10.2, "low": 9.4, "volume": 1000, "pct_chg": 1.0,
        }
    )
    pipeline.db.get_data_range.return_value = [bar]
    pipeline.db.save_fundamental_snapshot = MagicMock()
    pipeline.db.save_analysis_history.return_value = 1

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
            model_used="m", report_language="zh",
            analysis_summary="", news_summary="", technical_analysis="",
            fundamental_analysis="", risk_warning="", to_dict=lambda: {},
            error_message=None,
        )

    pipeline.analyzer = MagicMock()
    pipeline.analyzer.analyze = _fake_analyze
    pipeline._emit_progress = MagicMock()

    def _fake_get_context(code):
        return {
            "code": code,
            "date": "2026-06-10",
            "today": {
                "date": "2026-06-10",
                "close": 10.0,
                "open": 9.5,
                "high": 10.2,
                "low": 9.4,
                "volume": 1000,
                "pct_chg": 1.0,
            },
            "yesterday": {
                "date": "2026-06-09",
                "close": 9.9,
                "open": 9.8,
                "high": 10.0,
                "low": 9.7,
                "volume": 900,
                "pct_chg": 0.5,
            },
        }

    pipeline._get_analysis_context_with_market_fallback = _fake_get_context
    return pipeline, captured


def test_backfill_mode_skips_intelligence_and_stamps_marker():
    pipeline, captured = _build_pipeline_with_mocks()
    target = date(2026, 6, 10)

    pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q1",
        current_time=datetime.combine(target, datetime.min.time()),
        backfill_mode=True,
    )

    pipeline.search_service.search_comprehensive_intel.assert_not_called()
    ec = captured["enhanced_context"]
    assert "backfill" in ec
    assert ec["backfill"]["data_scope"] == "price_only"
    assert ec["realtime"]["price"] == 10.0


def test_normal_mode_does_not_set_backfill_marker():
    pipeline, captured = _build_pipeline_with_mocks()
    pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q2",
        current_time=None,
        backfill_mode=False,
    )
    assert "backfill" not in captured["enhanced_context"]

