# -*- coding: utf-8 -*-
"""Repository for daily ETF capital-flow snapshots."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.storage import DatabaseManager, EtfCapitalFlowSnapshot

logger = logging.getLogger(__name__)


class EtfCapitalFlowRepository:
    """DB access layer for daily ETF capital-flow snapshots."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def save_snapshot(self, trade_date: str, payload: Dict[str, Any]) -> None:
        """Upsert a daily snapshot by trade_date."""
        status = str(payload.get("status") or "ok")
        payload_json = json.dumps(payload, ensure_ascii=False, default=str)
        with self.db.get_session() as session:
            stmt = sqlite_insert(EtfCapitalFlowSnapshot).values(
                trade_date=trade_date,
                payload=payload_json,
                status=status,
                updated_at=datetime.now(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["trade_date"],
                set_={
                    "payload": stmt.excluded.payload,
                    "status": stmt.excluded.status,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            session.execute(stmt)
            session.commit()

    def get_snapshot(self, trade_date: str) -> Optional[Dict[str, Any]]:
        with self.db.get_session() as session:
            row = session.execute(
                select(EtfCapitalFlowSnapshot)
                .where(EtfCapitalFlowSnapshot.trade_date == trade_date)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._row_to_dict(row)

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        with self.db.get_session() as session:
            row = session.execute(
                select(EtfCapitalFlowSnapshot)
                .order_by(desc(EtfCapitalFlowSnapshot.trade_date))
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._row_to_dict(row)

    def get_snapshots_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(EtfCapitalFlowSnapshot)
                .where(EtfCapitalFlowSnapshot.trade_date >= start_date)
                .where(EtfCapitalFlowSnapshot.trade_date <= end_date)
                .order_by(EtfCapitalFlowSnapshot.trade_date.asc())
            ).scalars().all()
            return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row: EtfCapitalFlowSnapshot) -> Dict[str, Any]:
        try:
            payload = json.loads(row.payload) if row.payload else {}
        except json.JSONDecodeError:
            logger.warning("invalid JSON payload for etf snapshot trade_date=%s", row.trade_date)
            payload = {}
        return {
            "trade_date": row.trade_date,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            **payload,
        }