# -*- coding: utf-8 -*-
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.services.history_service import HistoryService


def _record(ctx):
    rec = MagicMock()
    rec.id = 1
    rec.query_id = "q"
    rec.code = "600519"
    rec.name = "测试"
    rec.report_type = "detailed"
    rec.operation_advice = "持有"
    rec.trend_prediction = "上行"
    rec.analysis_summary = ""
    rec.sentiment_score = 60
    rec.created_at = None
    rec.context_snapshot = json.dumps(ctx) if ctx is not None else None
    rec.raw_result = None
    return rec


def test_history_item_backfilled_true_when_marker_present():
    svc = HistoryService.__new__(HistoryService)
    svc.db = MagicMock()
    item = svc._record_to_list_item_dict(
        _record(
            {
                "enhanced_context": {
                    "date": "2026-06-10",
                    "backfill": {"data_scope": "price_only"},
                }
            }
        )
    )
    assert item["backfilled"] is True


def test_history_item_backfilled_false_when_absent():
    svc = HistoryService.__new__(HistoryService)
    item = svc._record_to_list_item_dict(
        _record({"enhanced_context": {"date": "2026-06-10"}})
    )
    assert item["backfilled"] is False


def test_history_item_target_date_extracted_when_backfill_target_date_present():
    svc = HistoryService.__new__(HistoryService)
    svc.db = MagicMock()
    item = svc._record_to_list_item_dict(
        _record(
            {
                "enhanced_context": {
                    "date": "2026-06-10",
                    "backfill": {
                        "target_date": "2026-06-10",
                        "data_scope": "price_only",
                    },
                }
            }
        )
    )
    assert item["backfilled"] is True
    assert item["target_date"] == "2026-06-10"


def test_history_item_target_date_none_when_not_backfilled():
    svc = HistoryService.__new__(HistoryService)
    item = svc._record_to_list_item_dict(
        _record({"enhanced_context": {"date": "2026-06-10"}})
    )
    assert item["target_date"] is None


def test_history_item_target_date_none_when_backfill_dict_missing_target_date():
    svc = HistoryService.__new__(HistoryService)
    item = svc._record_to_list_item_dict(
        _record(
            {
                "enhanced_context": {
                    "date": "2026-06-10",
                    "backfill": {"data_scope": "price_only"},
                }
            }
        )
    )
    assert item["backfilled"] is True
    assert item["target_date"] is None
