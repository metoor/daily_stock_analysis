# 修复按日期补填分析实际按当前时间生成

- 日期：2026-07-11
- 范围：`src/storage.py`、`src/core/pipeline.py`、`src/services/analysis_service.py`、`tests/test_pipeline_backfill_mode.py`、`tests/test_analysis_service_backfill.py`、`docs/backfill-guide.md`、`docs/CHANGELOG.md`
- 关联：`docs/superpowers/specs/2026-07-10-backfill-historical-analysis-design.md`（原设计）、`src/storage.py`（`get_analysis_context` 公共方法不动）、回测模块（`src/repositories/backtest_repo.py`）

## 1. 背景与问题

`feat/backfill-historical-analysis` 分支已实现「按指定历史日期补填分析」能力（见 `docs/superpowers/specs/2026-07-10-backfill-historical-analysis-design.md`）。用户反馈：选择补填指定日期 X 后，实际生成的分析记录是「按当前时间」做的，而非以 X 日为基准。

## 2. 根因

沿 `backfill_as_of_date` -> `process_single_stock` -> `analyze_stock` 链路读完代码，确认 bug 真实且有多处，互相传导：

### 2.1 主因：`db.get_analysis_context` 忽略 `target_date`

`src/storage.py:2517-2574` 的 `get_analysis_context(code, target_date)`：

- 形参 `target_date` 默认 `date.today()`，且仅在签名上存在。
- 实际取数走 `self.get_latest_data(code, days=2)`，**永远取数据库里最新两根 K 线**，对应今天和昨天。
- 代码 2536-2539 行已有自承注释：「尽管入参提供了 target_date，但当前实现实际使用的是'最新两天数据'……若未来需要支持'按历史某天复盘/重算'的可解释性，这里需要调整。该行为目前保留（按需求不改逻辑）。」

`pipeline.analyze_stock` 在 backfill 模式下仍调 `_get_analysis_context_with_market_fallback(code)`（`pipeline.py:622`），后者调 `db.get_analysis_context(code)` 不传 `target_date`，返回的 `context["date"]` 是今天、`context["today"]` 是今天的 bar。

### 2.2 传导：`enhanced_context["backfill"]["target_date"]` 取的是今天

`pipeline.py:658-663`：

```python
if backfill_mode:
    enhanced_context["backfill"] = {
        "target_date": context.get("date"),  # <- 取自 context["date"]，即今天
        "data_scope": "price_only",
        "created_at": datetime.now().isoformat(),
    }
```

`context["date"]` 来自 2.1 的今天日期，所以 `backfill.target_date` 写入的是今天，不是用户选的 X。

### 2.3 传导：`realtime.price/change_pct` 来自今天的 bar

`pipeline.py:664-669`：

```python
if not enhanced_context.get("realtime"):
    today_bar = context.get("today") or {}  # <- 今天的 bar
    enhanced_context["realtime"] = {
        "price": today_bar.get("close"),      # 今天的收盘价
        "change_pct": today_bar.get("pct_chg"), # 今天的涨跌
    }
```

报告 `meta.current_price` / `change_pct` 同样来自今天的 bar。

### 2.4 截止日错位：`frozen_target_date = X 的前一交易日`

`backfill_as_of_date` 传 `current_time=datetime.combine(target_date, datetime.min.time())`（X 日 00:00）。

`process_single_stock` 调 `_resolve_resume_target_date(code, current_time=00:00)`（`pipeline.py:2803`）-> `get_effective_trading_date(market, current_time=00:00)`（`trading_calendar.py:203`）。

`get_effective_trading_date` 的规则：「交易日但未到收盘 -> 前一个完成交易日」。X 日 00:00 必然在收盘前，所以返回 **X 的前一交易日**。`set_frozen_target_date(X-1)` 生效。

后果：
- `trend_analyzer` 的 `end_date = frozen = X-1`（`pipeline.py:520-522`），少一根 X 日的 K 线。
- `has_today_data(code, X-1)` 断点续传判断错位。

### 2.5 LLM 拿到的上下文是「今天」

综合 2.1-2.3：`enhanced_context` 里的 `today`/`yesterday`/`realtime`/`date` 全部是今天，`backfill.target_date` 也是今天。LLM 据此生成的分析当然是「按今天」做的。回测 `parse_analysis_date_from_snapshot` 从 `enhanced_context.date` 解析，会把这条错误记录归到今天，而不是用户选的 X。

### 2.6 现有测试为何没拦住

- `tests/test_pipeline_backfill_mode.py:86-110`：`_fake_get_context` 是测试自己写的 mock，**强制返回 `date=target`**，且 mock 掉了 `_get_analysis_context_with_market_fallback`，根本没测真实 `db.get_analysis_context` 忽略 `target_date` 的行为。断言也没检查 `ec["backfill"]["target_date"] == target`。
- `tests/test_analysis_service_backfill.py:43-50`：`test_backfilled_record_resolves_to_target_date_for_backtest` 直接构造 `snapshot = '{"enhanced_context": {"date": "2026-06-10", ...}}'` 字符串，没跑真实管线，只验证了 parser 能解出 X，没验证真实落库的 snapshot 是不是 X。

两个测试都「绿」着，bug 在眼皮底下漏过。

## 3. 修复方案

### 3.1 范围

- **仅修 backfill 路径**。`db.get_analysis_context` 公共方法语义不动（`storage.py:2536` 的 TODO 保留），避免影响所有调用方。
- 截止日错位用**方案 A**：`process_single_stock` 在 `backfill_mode=True` 且 `target_date` 非空时直接 `set_frozen_target_date(target_date)`，绕过 `_resolve_resume_target_date`。契约最清晰，不依赖时区/收盘时间假设。
- 测试重写为**端到端集成测试**：用真实 db（内存 sqlite）+ 真实管线，断言 `enhanced_context.date == X` 等核心契约。

### 3.2 数据流（修复后）

```
[历史趋势抽屉] 点「补填指定日期」-> 选 X
      │  POST /api/v1/analysis/backfill { stock_codes:[当前股], target_date:X }
      ▼
[AnalysisService.backfill_as_of_date]
   ① 校验 X < 今、X 为交易日
   ② 查重：已有真实记录？-> skipped（force 可覆盖）
   ③ process_single_stock(code, target_date=X, backfill_mode=True)
      │  ┌─ 关键修复点 ─────────────────────────────────────┐
      │  │ backfill_mode=True 且 target_date 非空时：       │
      │  │   set_frozen_target_date(X)  ← 直接冻结 X，       │
      │  │                                 绕过 _resolve_resume_target_date │
      │  │   fetch_and_save_stock_data 仍拉 days=30（覆盖 X）│
      │  └──────────────────────────────────────────────────┘
      ▼
[pipeline.analyze_stock(backfill_mode=True, target_date=X)]
   ├─ frozen = get_frozen_target_date()  -> X  ✓（不再是 X-1）
   ├─ trend_analyzer: end_date = X  ✓（含 X 日 bar）
   ├─ search/social/intelligence: 跳过 ✓
   ├─ context = _get_analysis_context_as_of(code, X)   ← 新方法
   │     ├─ today_bar = get_data_range 中 date == X 的那一根（精确取 X 日 bar）
   │     ├─ yesterday_bar = X 之前最近一根 bar（< X）
   │     └─ return {date: X, today: X bar, yesterday: 前一日 bar, ...}
   │     ↳ 若 X 日 bar 不存在 -> return None -> backfill 计 errors
   ├─ enhanced_context["realtime"] = {price: X 收盘, change_pct: X 涨跌}  ✓
   ├─ enhanced_context["backfill"]["target_date"] = X  ✓（直接写 X，不再从 context 取）
   └─ context_snapshot.enhanced_context.date = X  ✓
      │
      ▼
[回测] parse_analysis_date_from_snapshot -> X  ✓
```

## 4. 修改点清单

| 文件 | 改动 |
|---|---|
| `src/storage.py` | `DatabaseManager` 新增 `get_analysis_context_as_of(code, target_date) -> Optional[dict]`：内部用已有 `get_data_range(code, target_date - 4 days, target_date)` 取最近若干根 bar，再筛出 `date == target_date` 作 today、`date < target_date` 最近一根作 yesterday；返回形状与 `get_analysis_context` 一致。X 日 bar 缺失返回 `None`。 |
| `src/core/pipeline.py` | `process_single_stock` 增参 `target_date: Optional[date] = None`；`backfill_mode=True` 且 `target_date` 非空时，直接 `set_frozen_target_date(target_date)`，不调 `_resolve_resume_target_date`。`analyze_stock` 增参 `target_date`；`backfill_mode=True` 且 `target_date` 非空时调 `self.db.get_analysis_context_as_of(code, target_date)` 取代 `_get_analysis_context_with_market_fallback(code)`；`enhanced_context["backfill"]["target_date"]` 直接写 `target_date.isoformat()`；`realtime` 用新方法返回的 today_bar 填充。`process_single_stock` 调 `analyze_stock` 时透传 `target_date`。 |
| `src/services/analysis_service.py` | `backfill_as_of_date` 调 `process_single_stock` 时多传 `target_date=target_date`；移除 `current_time` 透传（不再需要，冻结由 `target_date` 直接接管）。 |
| `tests/test_pipeline_backfill_mode.py` | 重写：用内存 sqlite 插入 X 日及之前 N 天 K 线，**不再 mock** `_get_analysis_context_with_market_fallback`；断言 `enhanced_context["date"] == X`、`enhanced_context["today"]["date"] == X`、`enhanced_context["backfill"]["target_date"] == X`、`enhanced_context["realtime"]["price"] == X 日收盘`、`trend_analyzer` 收到的 df 最后一根 bar 是 X 日、search/social 未被调用、正常模式回归。 |
| `tests/test_analysis_service_backfill.py` | 现有 `test_backfilled_record_resolves_to_target_date_for_backtest` 保留（parser 测试）；新增端到端：真实管线 + 真实 db，断言落库的 `context_snapshot.enhanced_context.date == X`。 |
| `docs/backfill-guide.md` | 补一段「已知限制」：X 日 K 线缺失时 backfill 计 errors；回填记录的 `enhanced_context.date = X`。 |
| `docs/CHANGELOG.md` | `[Unreleased]` 加一条扁平格式：`- [修复] 按指定日期补填分析实际按当前时间生成（db.get_analysis_context 忽略 target_date、冻结日错位、backfill 标记取错日期）` |

**不改**：`db.get_analysis_context` 公共方法语义、`fetch_and_save_stock_data` 签名、回测引擎、报告结构、API 契约（`POST /api/v1/analysis/backfill` 不变）、前端。

## 5. 新增方法契约

### 5.1 `DatabaseManager.get_analysis_context_as_of`

放在 `src/storage.py` 的 `DatabaseManager` 上（与 `get_analysis_context` 同类），`pipeline.db` 可直接调用，无需新增依赖注入。

```python
def get_analysis_context_as_of(
    self, code: str, target_date: date
) -> Optional[Dict[str, Any]]:
    """
    按 target_date 精确取当日 + 前一交易日 bar，构造分析上下文。
    供 backfill 模式专用，不替代 get_analysis_context。

    - today_bar: 精确取 target_date 当日 bar（无 fallback）。
    - yesterday_bar: target_date 之前最近一根 bar（< target_date）。
    - 两者任一缺失 -> 返回 None（backfill 计 errors）。
    - 返回形状与 get_analysis_context 一致：
        {
          "code": code,
          "date": target_date.isoformat(),
          "today": {...bar dict...},
          "yesterday": {...bar dict...},
          "volume_change_ratio": ...,
          "price_change_ratio": ...,
          "ma_status": ...,
        }
    """
```

实现要点：
- 用 `self.get_data_range(code, target_date - timedelta(days=4), target_date)` 取最近 5 个自然日的 bar（覆盖 X 日及之前，含跨周末/短假）。
- `today_bar` = 列表中 `date == target_date` 的那一根；不存在 -> return `None`。
- `yesterday_bar` = 列表中 `date < target_date` 的最后一根（按 `date` 升序后取倒数第二个，或过滤后取最后一条）；不存在 -> return `None`。
- 复用 `self._analyze_ma_status(today_bar)` 计算均线形态（与 `get_analysis_context:2572` 一致）。
- `volume_change_ratio` / `price_change_ratio` 计算逻辑与 `get_analysis_context:2557-2569` 一致。
- 注：`StockRepository`（`src/repositories/stock_repo.py`）已有 `get_daily_on_date` / `get_start_daily` 可独立完成同样查询，但 `pipeline.db` 是 `DatabaseManager` 而非 `StockRepository`，为避免给 pipeline 新增依赖注入，方法放在 `DatabaseManager` 上，内部用 `get_data_range`（已有）实现。

### 5.2 `pipeline.analyze_stock` 调用点改动

```python
# pipeline.py:622 附近
if backfill_mode and target_date is not None:
    context = self.db.get_analysis_context_as_of(code, target_date)
else:
    context = self._get_analysis_context_with_market_fallback(code)
```

### 5.3 `enhanced_context["backfill"]["target_date"]` 直接写 X

```python
# pipeline.py:658-669
if backfill_mode and target_date is not None:
    enhanced_context["backfill"] = {
        "target_date": target_date.isoformat(),  # 直接写 X，不再从 context 取
        "data_scope": "price_only",
        "created_at": datetime.now().isoformat(),
    }
    today_bar = context.get("today") or {}
    enhanced_context["realtime"] = {
        "price": today_bar.get("close"),
        "change_pct": today_bar.get("pct_chg"),
    }
```

### 5.4 `process_single_stock` 冻结逻辑

```python
# pipeline.py:2802-2804
if backfill_mode and target_date is not None:
    frozen_td = target_date
else:
    frozen_td = self._resolve_resume_target_date(code, current_time=current_time)
token = set_frozen_target_date(frozen_td)
```

`process_single_stock` 调 `analyze_stock` 时透传 `target_date`：

```python
# pipeline.py:2833-2838
analyze_kwargs = {"query_id": effective_query_id}
if current_time is not None:
    analyze_kwargs["current_time"] = current_time
if backfill_mode:
    analyze_kwargs["backfill_mode"] = True
    analyze_kwargs["target_date"] = target_date  # 新增
result = self.analyze_stock(code, report_type, **analyze_kwargs)
```

### 5.5 `analysis_service.backfill_as_of_date` 调用改动

```python
# analysis_service.py:211-218
result = pipeline.process_single_stock(
    code=code,
    skip_analysis=False,
    single_stock_notify=False,
    report_type=ReportType.from_str(report_type),
    target_date=target_date,  # 新增，替代 current_time
    backfill_mode=True,
)
```

移除 `current_time=datetime.combine(target_date, datetime.min.time())`（不再需要）。

## 6. 测试设计

### 6.1 `tests/test_pipeline_backfill_mode.py` 重写

```python
@pytest.fixture
def pipeline_with_real_db():
    # 1. 创建内存 sqlite db_manager
    # 2. 插入 600519 的 K 线：2026-06-01 ~ 2026-06-10（10 根 bar）
    #    X = 2026-06-10，收盘价 10.0，pct_chg 1.0
    # 3. 用真实 db_manager 构造 pipeline（不 mock _get_analysis_context_with_market_fallback）
    # 4. mock 掉 LLM analyzer、fetcher_manager（数据已入库，无需网络）
    # 5. spy trend_analyzer.analyze 的入参 df
    # 返回 (pipeline, captured, target_date)

def test_backfill_uses_target_date_context(pipeline_with_real_db):
    pipeline, captured, target = pipeline_with_real_db
    pipeline.analyze_stock(
        code="600519",
        report_type=SimpleNamespace(value="detailed"),
        query_id="q1",
        target_date=target,
        backfill_mode=True,
    )
    ec = captured["enhanced_context"]
    assert ec["date"] == "2026-06-10"
    assert ec["today"]["date"] == "2026-06-10"
    assert ec["today"]["close"] == 10.0
    assert ec["backfill"]["target_date"] == "2026-06-10"
    assert ec["realtime"]["price"] == 10.0
    assert ec["realtime"]["change_pct"] == 1.0
    # trend_analyzer 收到的 df 最后一根 bar 是 X 日
    last_bar = captured["trend_df"].iloc[-1]
    assert str(last_bar["date"]).startswith("2026-06-10")
    # search/social 未被调用
    pipeline.search_service.search_comprehensive_intel.assert_not_called()

def test_backfill_missing_target_bar_returns_none(pipeline_with_real_db):
    # 删掉 2026-06-10 的 bar
    # 调 backfill_mode=True, target_date=2026-06-10
    # 断言 analyze_stock 返回 None 或 result.success == False

def test_normal_mode_unchanged(pipeline_with_real_db):
    # backfill_mode=False, target_date=None
    # 断言 "backfill" not in ec（回归）
    # 断言走 _get_analysis_context_with_market_fallback（最新两天）
```

### 6.2 `tests/test_analysis_service_backfill.py` 补充端到端

```python
def test_backfill_writes_target_date_to_snapshot_e2e():
    # 真实 AnalysisService + 真实 pipeline（mock LLM）+ 内存 sqlite
    # 插入 600519 的 K 线含 X 日
    # 调 backfill_as_of_date(["600519"], X, force=True)
    # 断言：
    #   - result["saved"] == 1
    #   - 落库的 context_snapshot.enhanced_context.date == X
    #   - 落库的 context_snapshot.enhanced_context.backfill.target_date == X
```

### 6.3 现有测试保留项

- `test_rejects_future_target_date`、`test_skips_when_real_record_exists_without_force`、`test_force_overrides_existing_record`、`test_backfilled_record_resolves_to_target_date_for_backtest` 均保留。

## 7. 风险与回滚

### 7.1 风险

- `get_analysis_context_as_of` 与 `db.get_analysis_context` 返回形状不一致 -> 下游解析失败。缓解：复用相同字段名和计算逻辑，单测覆盖形状。
- `process_single_stock` 新增 `target_date` 参数 -> 其他调用方未传时走原逻辑（默认 `None`），无破坏。缓解：参数默认 `None`，`backfill_mode=False` 时完全不影响。
- 端到端测试依赖内存 sqlite -> 若 db_manager 不支持 sqlite in-memory，需用临时文件。缓解：先验证现有测试是否已有 sqlite in-memory 先例；若无，用临时文件 db。
- `trend_analyzer` 收到的 df 最后一根 bar 是 X 日 -> 若 frozen=X 生效，`load_history_df` 的 DB 路径会按 end=X 截断，正确。但若 DB 缺 X 日 bar，`load_history_df` 会 fallback 到网络，拉到今天 -> 污染。缓解：测试覆盖「X 日 bar 缺失」场景；生产路径下 `get_analysis_context_as_of` 已先拦 None，`trend_analyzer` 不会跑到。

### 7.2 回滚

- 回退本次提交即可。回填记录仍是普通 `analysis_history` + backfill 标记字段，历史查询/抽屉/接口/回测兼容性不变。
- 若需清理 bug 期间产生的错误回填记录（按当前时间生成但标记为 backfill 的）：按 `context_snapshot` 含 `backfill` 标记且 `enhanced_context.date != backfill.target_date` 筛选清理。这是 bug 产生的特征，修复后新记录两者相等。

### 7.3 未覆盖项

- 真实 LLM 调用（测试仍 mock analyzer）。
- 跨市场（港股/美股）时区 -- 方案 A 不依赖时区，理论无差异，但测试只覆盖 A 股。
- `fetch_and_save_stock_data` 网络拉取仍拉到今天，未按 X 截止 -- 不影响正确性（db 取数按 frozen 截断），但若 X 日数据源拉不到，backfill 仍会失败。本期不改。

## 8. 验证矩阵

按 `AGENTS.md` 第 6 节「验证矩阵」：

- **Python 后端改动**（`src/core/pipeline.py`、`src/services/analysis_service.py`、`src/storage.py`）：
  - 优先执行：`./scripts/ci_gate.sh`
  - 最低要求：`python -m py_compile src/core/pipeline.py src/services/analysis_service.py src/storage.py`
  - 测试：`python -m pytest tests/test_pipeline_backfill_mode.py tests/test_analysis_service_backfill.py -v`
- **文档改动**（`docs/backfill-guide.md`、`docs/CHANGELOG.md`）：核对命令、文件名、字段名与实际仓库一致。
- **API 契约未变**：`POST /api/v1/analysis/backfill` 签名不变，无需前端联动验证。
