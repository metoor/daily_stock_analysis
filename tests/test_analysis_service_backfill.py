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
    Pipe.return_value.process_single_stock.assert_called_once()


def test_backfilled_record_resolves_to_target_date_for_backtest():
    """回填记录的 enhanced_context.date == target_date，回测据此归类。"""
    from src.repositories.backtest_repo import BacktestRepository
    svc = _service()
    # 模拟回填后落库的 context_snapshot（由管线 backfill_mode 产生）
    snapshot = '{"enhanced_context": {"date": "2026-06-10", "backfill": {"data_scope": "price_only"}}}'
    parsed = BacktestRepository.parse_analysis_date_from_snapshot(snapshot)
    assert parsed == date(2026, 6, 10)
