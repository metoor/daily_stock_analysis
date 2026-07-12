# tests/test_analysis_repo_backfill.py
# -*- coding: utf-8 -*-
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.repositories.analysis_repo import AnalysisRepository


def _record(ctx_dict):
    return SimpleNamespace(context_snapshot=json.dumps(ctx_dict))


def _make_repo(records):
    repo = AnalysisRepository.__new__(AnalysisRepository)
    repo.db = MagicMock()
    repo.db.get_analysis_history.return_value = records
    return repo


def test_returns_true_when_real_record_matches_date():
    repo = _make_repo([_record({"enhanced_context": {"date": "2026-06-10"}})])
    assert repo.find_real_analysis_for_date("600519", date(2026, 6, 10)) is True


def test_returns_false_when_only_backfill_record_matches_date():
    repo = _make_repo([
        _record({"enhanced_context": {"date": "2026-06-10", "backfill": {"data_scope": "price_only"}}})
    ])
    assert repo.find_real_analysis_for_date("600519", date(2026, 6, 10)) is False


def test_returns_false_when_no_matching_date():
    repo = _make_repo([_record({"enhanced_context": {"date": "2026-06-09"}})])
    assert repo.find_real_analysis_for_date("600519", date(2026, 6, 10)) is False
