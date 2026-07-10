# -*- coding: utf-8 -*-
"""
===================================
分析服务层
===================================

职责：
1. 封装股票分析逻辑
2. 调用 analyzer 和 pipeline 执行分析
3. 保存分析结果到数据库
"""

import logging
import copy
import uuid
from datetime import date, datetime
from typing import Optional, Dict, Any, Callable, List

from data_provider.base import normalize_stock_code
from src.core.trading_calendar import is_market_open, get_market_for_stock
from src.repositories.analysis_repo import AnalysisRepository
from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.market_phase_summary import extract_market_phase_summary
from src.schemas.decision_action import build_action_fields
from src.services.run_diagnostics import (
    activate_run_diagnostic_context,
    build_run_diagnostic_summary,
    get_current_diagnostic_context,
    reset_run_diagnostic_context,
)

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    分析服务
    
    封装股票分析相关的业务逻辑
    """
    
    def __init__(self):
        """初始化分析服务"""
        self.repo = AnalysisRepository()
        self.last_error: Optional[str] = None
    
    def analyze_stock(
        self,
        stock_code: str,
        report_type: str = "detailed",
        force_refresh: bool = False,
        query_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        send_notification: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        skills: Optional[List[str]] = None,
        analysis_phase: str = "auto",
        query_source: str = "api",
        portfolio_context: Optional[Dict[str, Any]] = None,
        report_language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        执行股票分析
        
        Args:
            stock_code: 股票代码
            report_type: 报告类型 (simple/detailed)
            force_refresh: 是否强制刷新
            query_id: 查询 ID（可选）
            send_notification: 是否发送通知（API 触发默认发送）
            analysis_phase: 请求的分析阶段覆盖（auto/premarket/intraday/postmarket）
            
        Returns:
            分析结果字典，包含:
            - stock_code: 股票代码
            - stock_name: 股票名称
            - report: 分析报告
        """
        try:
            self.last_error = None
            # 导入分析相关模块
            from src.config import get_config
            from src.core.pipeline import StockAnalysisPipeline
            from src.enums import ReportType
            
            # 生成 query_id
            if query_id is None:
                query_id = uuid.uuid4().hex
            effective_trace_id = trace_id or query_id
            diag_token = None
            if get_current_diagnostic_context() is None:
                diag_token = activate_run_diagnostic_context(
                    trace_id=effective_trace_id,
                    query_id=query_id,
                    stock_code=stock_code,
                    trigger_source=query_source or "api",
                )
            
            # 获取配置
            config = get_config()
            normalized_report_language = normalize_report_language(report_language, default="")
            if normalized_report_language:
                config = copy.copy(config)
                config.report_language = normalized_report_language
            
            # 创建分析流水线
            pipeline = StockAnalysisPipeline(
                config=config,
                query_id=query_id,
                trace_id=effective_trace_id,
                query_source=query_source or "api",
                progress_callback=progress_callback,
                analysis_skills=skills,
                analysis_phase=analysis_phase,
                portfolio_context=portfolio_context,
            )
            
            # 确定报告类型 (API: simple/detailed/full/brief -> ReportType)
            rt = ReportType.from_str(report_type)
            
            # 执行分析
            result = pipeline.process_single_stock(
                code=stock_code,
                skip_analysis=False,
                single_stock_notify=send_notification,
                report_type=rt,
            )
            
            if result is None:
                logger.warning(f"分析股票 {stock_code} 返回空结果")
                self.last_error = self.last_error or f"分析股票 {stock_code} 返回空结果"
                return None

            if not getattr(result, "success", True):
                self.last_error = getattr(result, "error_message", None) or f"分析股票 {stock_code} 失败"
                logger.warning(f"分析股票 {stock_code} 未成功完成: {self.last_error}")
                return None
            
            # 构建响应
            return self._build_analysis_response(result, query_id, report_type=rt.value)
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"分析股票 {stock_code} 失败: {e}", exc_info=True)
            return None
        finally:
            reset_run_diagnostic_context(locals().get("diag_token"))

    def backfill_as_of_date(
        self,
        stock_codes: List[str],
        target_date: date,
        force: bool = False,
        report_type: str = "detailed",
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        以 target_date 为基准补填分析（冻结价格、跳过新闻/基本面、标记为回填）。

        - target_date 必须 < 今天且为该股交易日。
        - 该股 target_date 已有真实记录则跳过（force 可覆盖）。
        - 单股失败不中断，计入 errors。
        """
        from src.config import get_config
        from src.core.pipeline import StockAnalysisPipeline
        from src.enums import ReportType

        today = datetime.now().date()
        processed = saved = skipped = errors = 0
        skip_reasons: list = []

        if not stock_codes:
            return {"processed": 0, "saved": 0, "skipped": 0, "errors": 0,
                    "message": "stock_codes 不能为空", "diagnostics": {}}

        if target_date >= today:
            return {"processed": 0, "saved": 0, "skipped": 0,
                    "errors": len(stock_codes),
                    "message": "目标日期须早于今天（未收盘/未来日期不接受）",
                    "diagnostics": {}}

        for code in stock_codes:
            market = get_market_for_stock(normalize_stock_code(code)) or "cn"
            if not is_market_open(market, target_date):
                errors += 1
                skip_reasons.append(f"{code}: {target_date} 非该市场交易日（或日历不可用）")
                continue
            if not force and self.repo.find_real_analysis_for_date(code, target_date):
                skipped += 1
                skip_reasons.append(f"{code}: {target_date} 已有真实分析记录，已跳过（force 可覆盖）")
                continue

            processed += 1
            try:
                if progress_callback:
                    progress_callback(20, f"{code}：正在以 {target_date} 为基准补填分析")
                config = get_config()
                pipeline = StockAnalysisPipeline(
                    config=config,
                    query_id=uuid.uuid4().hex,
                    trace_id=uuid.uuid4().hex,
                    query_source="backfill",
                    progress_callback=progress_callback,
                )
                result = pipeline.process_single_stock(
                    code=code,
                    skip_analysis=False,
                    single_stock_notify=False,
                    report_type=ReportType.from_str(report_type),
                    current_time=datetime.combine(target_date, datetime.min.time()),
                    backfill_mode=True,
                )
                if result is not None and getattr(result, "success", False):
                    saved += 1
                else:
                    errors += 1
                    skip_reasons.append(f"{code}: 分析未成功（可能无 {target_date} 行情）")
            except Exception as e:
                errors += 1
                logger.error(f"backfill {code}@{target_date} 失败: {e}", exc_info=True)
                skip_reasons.append(f"{code}: {e}")

        message = (
            f"补填完成：处理 {processed}，保存 {saved}，跳过 {skipped}，错误 {errors}"
            if processed else ("未处理任何记录；" + "；".join(skip_reasons[:3]))
        )
        return {
            "processed": processed,
            "saved": saved,
            "skipped": skipped,
            "errors": errors,
            "message": message,
            "diagnostics": {"reasons": skip_reasons},
        }

    def _build_analysis_response(
        self,
        result: Any,
        query_id: str,
        report_type: str = "detailed",
    ) -> Dict[str, Any]:
        """
        构建分析响应
        
        Args:
            result: AnalysisResult 对象
            query_id: 查询 ID
            report_type: 归一化后的报告类型
            
        Returns:
            格式化的响应字典
        """
        # 获取狙击点位
        sniper_points = {}
        if hasattr(result, 'get_sniper_points'):
            sniper_points = result.get_sniper_points() or {}
        
        # 计算情绪标签
        report_language = normalize_report_language(getattr(result, "report_language", "zh"))
        sentiment_label = get_sentiment_label(result.sentiment_score, report_language)
        stock_name = get_localized_stock_name(getattr(result, "name", None), result.code, report_language)
        action_fields = build_action_fields(
            operation_advice=getattr(result, "operation_advice", None),
            explicit_action=getattr(result, "action", None),
            report_type=report_type,
            report_language=report_language,
            sentiment_score=getattr(result, "sentiment_score", None),
            guardrail_reason=getattr(result, "guardrail_reason", None),
            align_with_score=True,
        )
        diagnostic_context = get_current_diagnostic_context()
        trace_id = diagnostic_context.trace_id if diagnostic_context is not None else query_id
        diagnostic_snapshot = diagnostic_context.snapshot() if diagnostic_context is not None else None
        diagnostic_context_snapshot = getattr(result, "diagnostic_context_snapshot", None)
        market_phase_summary = extract_market_phase_summary(diagnostic_context_snapshot)
        if isinstance(diagnostic_context_snapshot, dict):
            context_snapshot = dict(diagnostic_context_snapshot)
            if diagnostic_snapshot is not None:
                context_snapshot["diagnostics"] = diagnostic_snapshot
        elif diagnostic_snapshot is not None:
            context_snapshot = {"diagnostics": diagnostic_snapshot}
        else:
            context_snapshot = None
        diagnostic_summary = build_run_diagnostic_summary(
            context_snapshot=context_snapshot,
            raw_result=result.to_dict() if hasattr(result, "to_dict") else None,
            report_saved=True,
            query_id=query_id,
            stock_code=result.code,
        )
        
        # 构建报告结构
        report = {
            "meta": {
                "query_id": query_id,
                "trace_id": trace_id,
                "stock_code": result.code,
                "stock_name": stock_name,
                "report_type": report_type,
                "report_language": report_language,
                "current_price": result.current_price,
                "change_pct": result.change_pct,
                "model_used": getattr(result, "model_used", None),
                "market_phase_summary": market_phase_summary,
            },
            "summary": {
                "analysis_summary": result.analysis_summary,
                "operation_advice": localize_operation_advice(result.operation_advice, report_language),
                "action": action_fields["action"],
                "action_label": action_fields["action_label"],
                "trend_prediction": localize_trend_prediction(result.trend_prediction, report_language),
                "sentiment_score": result.sentiment_score,
                "sentiment_label": sentiment_label,
            },
            "strategy": {
                "ideal_buy": sniper_points.get("ideal_buy"),
                "secondary_buy": sniper_points.get("secondary_buy"),
                "stop_loss": sniper_points.get("stop_loss"),
                "take_profit": sniper_points.get("take_profit"),
            },
            "details": {
                "news_summary": result.news_summary,
                "technical_analysis": result.technical_analysis,
                "fundamental_analysis": result.fundamental_analysis,
                "risk_warning": result.risk_warning,
            }
        }
        
        return {
            "query_id": query_id,
            "trace_id": trace_id,
            "stock_code": result.code,
            "stock_name": stock_name,
            "report": report,
            "diagnostic_summary": diagnostic_summary,
        }
