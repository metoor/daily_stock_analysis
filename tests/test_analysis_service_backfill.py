# -*- coding: utf-8 -*-
from datetime import date, datetime
from unittest.mock import patch

from src.services.analysis_service import AnalysisService


def _service():
    return AnalysisService()


def test_rejects_future_target_date():
    svc = _service()
    future = date.today().replace(year=date.today().year + 1)
    result = svc.backfill_as_of_date(["600519"], future)
    assert result["processed"] == 0
    assert result["errors"] >= 1
    assert "未来" in result["message"] or "未收盘" in result["message"]


def test_skips_when_real_record_exists_without_force():
    svc = _service()
    with patch.object(svc.repo, "find_real_analysis_for_date", return_value=True), \
         patch("src.services.analysis_service.is_market_open", return_value=True):
        result = svc.backfill_as_of_date(["600519"], date(2026, 6, 10))
    assert result["skipped"] == 1
    assert result["processed"] == 0


def test_force_overrides_existing_record():
    svc = _service()
    with patch.object(svc.repo, "find_real_analysis_for_date", return_value=True), \
         patch("src.services.analysis_service.is_market_open", return_value=True), \
         patch("src.core.pipeline.StockAnalysisPipeline") as Pipe:
        Pipe.return_value.process_single_stock.return_value = None
        result = svc.backfill_as_of_date(["600519"], date(2026, 6, 10), force=True)
    assert result["skipped"] == 0
    assert result["errors"] == 1
    assert result["saved"] == 0
    Pipe.return_value.process_single_stock.assert_called_once()


def test_backfilled_record_resolves_to_target_date_for_backtest():
    """回填记录的 enhanced_context.date == target_date，回测据此归类。"""
    from src.repositories.backtest_repo import BacktestRepository
    svc = _service()
    # 模拟回填后落库的 context_snapshot（由管线 backfill_mode 产生）
    snapshot = '{"enhanced_context": {"date": "2026-06-10", "backfill": {"data_scope": "price_only"}}}'
    parsed = BacktestRepository.parse_analysis_date_from_snapshot(snapshot)
    assert parsed == date(2026, 6, 10)


def test_backfill_writes_target_date_to_snapshot_e2e(tmp_path):
    """端到端：真实 pipeline + 真实 db，落库 enhanced_context.date == X。"""
    from unittest.mock import patch, MagicMock

    from src.storage import DatabaseManager
    from src.services.analysis_service import AnalysisService

    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path}/backfill_e2e.db")

    target = date(2026, 6, 10)
    from datetime import timedelta
    import pandas as pd
    rows = []
    for i in range(10):
        d = date(2026, 6, 1) + timedelta(days=i)
        rows.append({
            "date": d, "open": 9.0 + i * 0.1, "high": 10.0 + i * 0.1,
            "low": 8.5 + i * 0.1, "close": 9.5 + i * 0.1,
            "volume": 1000.0 + i * 100, "pct_chg": 1.0 + i * 0.1,
            "ma5": 9.0, "ma10": 8.8, "ma20": 8.5,
        })
    df = pd.DataFrame(rows)
    df["code"] = "600519"
    db.save_daily_data(df, "600519", "test")

    saved_snapshots = []
    original_save = db.save_analysis_history

    def _capture_save(result, query_id, report_type, news_content, context_snapshot, save_snapshot):
        saved_snapshots.append(context_snapshot)
        return 1

    db.save_analysis_history = _capture_save

    from src.core.pipeline import StockAnalysisPipeline
    from src.config import Config

    with patch("src.services.analysis_service.is_market_open", return_value=True), \
         patch("src.core.pipeline.StockAnalysisPipeline") as Pipe:
        real_pipe = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        real_pipe.db = db
        real_pipe.config = MagicMock(spec=Config)
        real_pipe.config.enable_realtime_quote = True
        real_pipe.config.report_language = "zh"
        real_pipe.config.agent_mode = False
        real_pipe.config.agent_skills = []
        real_pipe.config.fundamental_stage_timeout_seconds = 1
        real_pipe.config.daily_market_context_enabled = False
        real_pipe.config.market_review_enabled = False
        real_pipe.config.litellm_model = "test-model"
        real_pipe.query_source = "backfill"
        real_pipe.analysis_phase = "auto"
        real_pipe.analysis_skills = None
        real_pipe.save_context_snapshot = True
        real_pipe.portfolio_context = None
        real_pipe.fetcher_manager = MagicMock()
        real_pipe.fetcher_manager.get_stock_name.return_value = "测试股"
        real_pipe.fetcher_manager.get_realtime_quote.return_value = None
        real_pipe.fetcher_manager.get_chip_distribution.return_value = None
        real_pipe.fetcher_manager.get_fundamental_context.return_value = {}
        real_pipe.fetcher_manager.build_failed_fundamental_context.return_value = {}
        real_pipe.search_service = MagicMock()
        real_pipe.search_service.is_available = True
        real_pipe.search_service.search_comprehensive_intel = MagicMock(return_value={})
        real_pipe.social_sentiment_service = None
        real_pipe.trend_analyzer = MagicMock()
        real_pipe.trend_analyzer.analyze.return_value = MagicMock(
            trend_status=MagicMock(value="up"), buy_signal=MagicMock(value="none"),
            signal_score=50, ma_alignment="bull", trend_strength=0.5,
            bias_ma5=0.01, bias_ma10=0.02,
            volume_status=MagicMock(value="normal"), volume_trend="up",
            signal_reasons=[], risk_factors=[], ma5=10.0, ma10=9.8, ma20=9.5,
        )
        real_pipe.analyzer = MagicMock()
        real_pipe.analyzer.analyze = MagicMock(return_value=MagicMock(
            success=True, code="600519", name="测试股",
            current_price=None, change_pct=None, query_id="q",
            operation_advice="持有", sentiment_score=60,
            model_used="m", report_language="zh",
            analysis_summary="", news_summary="", technical_analysis="",
            fundamental_analysis="", risk_warning="", to_dict=lambda: {},
            error_message=None,
        ))
        real_pipe._emit_progress = MagicMock()

        Pipe.return_value = real_pipe

        svc = AnalysisService()
        with patch.object(svc.repo, "find_real_analysis_for_date", return_value=False):
            result = svc.backfill_as_of_date(["600519"], target, force=True)

    assert result["saved"] == 1
    assert len(saved_snapshots) == 1
    snapshot = saved_snapshots[0]
    enhanced = snapshot.get("enhanced_context", {})
    assert enhanced.get("date") == "2026-06-10"
    assert enhanced.get("backfill", {}).get("target_date") == "2026-06-10"

    DatabaseManager.reset_instance()
