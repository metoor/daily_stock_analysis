# 首页操作按钮二次确认设计

## 背景

首页的三个操作按钮（分析、大盘复盘、重新复盘）点击后直接执行，没有二次确认。用户可能误触导致不必要的 LLM token 消耗或长时间等待。需要添加确认弹窗，与项目已有的 `ConfirmDialog` 模式一致。

## 方案

直接复用 `ConfirmDialog` 组件，为三个按钮各添加一组 `useState` + `<ConfirmDialog>`，与 `SidebarNav` 登出确认的写法一致。

## 改动范围

| 文件 | 改动内容 |
|------|---------|
| `apps/dsa-web/src/pages/HomePage.tsx` | 3 组 state + 3 个 ConfirmDialog + 3 个 onClick 改动 |
| `apps/dsa-web/src/i18n/uiText.ts` | 6 个 i18n key（zh + en 各 3 个提示文案） |

## 确认弹窗内容

| 按钮 | i18n title key | title (zh) | title (en) | i18n message key | message (zh) | message (en) |
|------|---------------|------------|------------|-----------------|-------------|-------------|
| 分析 | `home.analyzeConfirmTitle` | 分析确认 | Confirm Analysis | `home.analyzeConfirmMessage` | 确认开始分析？分析过程将消耗 LLM token。 | Start analysis? This will consume LLM tokens. |
| 大盘复盘 | `home.marketReviewConfirmTitle` | 大盘复盘确认 | Confirm Market Review | `home.marketReviewConfirmMessage` | 确认执行大盘复盘？复盘过程可能需要几分钟。 | Run market review? This may take a few minutes. |
| 重新复盘 | `home.rerunMarketReviewConfirmTitle` | 重新复盘确认 | Confirm Rerun | `home.rerunMarketReviewConfirmMessage` | 确认重新执行大盘复盘？将覆盖当前复盘结果。 | Rerun market review? This will overwrite the current result. |

## 实现细节

### HomePage.tsx 改动

#### 1. 新增 state（3 个）

```tsx
const [showAnalyzeConfirm, setShowAnalyzeConfirm] = useState(false);
const [showMarketReviewConfirm, setShowMarketReviewConfirm] = useState(false);
const [showRerunMarketReviewConfirm, setShowRerunMarketReviewConfirm] = useState(false);
```

#### 2. 分析按钮 onClick 改动

- 当前：`onClick={() => void handleSubmitAnalysis()}`
- 改为：`onClick={() => setShowAnalyzeConfirm(true)}`

#### 3. 大盘复盘按钮 onClick 改动

- 当前：`onClick={() => void handleTriggerMarketReview()}`（line 790）
- 改为：`onClick={() => setShowMarketReviewConfirm(true)}`

#### 4. 重新复盘按钮 onClick 改动

- 当前：`onClick={() => void handleTriggerMarketReview()}`（line 972）
- 改为：`onClick={() => setShowRerunMarketReviewConfirm(true)}`

#### 5. 新增 3 个 ConfirmDialog（放在 return JSX 中，与其他 ConfirmDialog 同级）

```tsx
<ConfirmDialog
  isOpen={showAnalyzeConfirm}
  title={t('home.analyzeConfirmTitle')}
  message={t('home.analyzeConfirmMessage')}
  onConfirm={() => { setShowAnalyzeConfirm(false); void handleSubmitAnalysis(); }}
  onCancel={() => setShowAnalyzeConfirm(false)}
/>

<ConfirmDialog
  isOpen={showMarketReviewConfirm}
  title={t('home.marketReviewConfirmTitle')}
  message={t('home.marketReviewConfirmMessage')}
  onConfirm={() => { setShowMarketReviewConfirm(false); void handleTriggerMarketReview(); }}
  onCancel={() => setShowMarketReviewConfirm(false)}
/>

<ConfirmDialog
  isOpen={showRerunMarketReviewConfirm}
  title={t('home.rerunMarketReviewConfirmTitle')}
  message={t('home.rerunMarketReviewConfirmMessage')}
  onConfirm={() => { setShowRerunMarketReviewConfirm(false); void handleTriggerMarketReview(); }}
  onCancel={() => setShowRerunMarketReviewConfirm(false)}
/>
```

### uiText.ts 改动

在 zh block 的 `home` 命名空间下添加：

```ts
home.analyzeConfirmTitle: '分析确认',
home.analyzeConfirmMessage: '确认开始分析？分析过程将消耗 LLM token。',
home.marketReviewConfirmTitle: '大盘复盘确认',
home.marketReviewConfirmMessage: '确认执行大盘复盘？复盘过程可能需要几分钟。',
home.rerunMarketReviewConfirmTitle: '重新复盘确认',
home.rerunMarketReviewConfirmMessage: '确认重新执行大盘复盘？将覆盖当前复盘结果。',
```

在 en block 的 `home` 命名空间下添加：

```ts
home.analyzeConfirmTitle: 'Confirm Analysis',
home.analyzeConfirmMessage: 'Start analysis? This will consume LLM tokens.',
home.marketReviewConfirmTitle: 'Confirm Market Review',
home.marketReviewConfirmMessage: 'Run market review? This may take a few minutes.',
home.rerunMarketReviewConfirmTitle: 'Confirm Rerun',
home.rerunMarketReviewConfirmMessage: 'Rerun market review? This will overwrite the current result.',
```

## 不改动的部分

- `ConfirmDialog` 组件本身 — 已满足需求（不使用 `isDanger`，默认青色确认按钮）
- 后端 API — 无需改动
- 其他页面 — 不受影响

## 验证

- 点击分析按钮 → 弹出确认弹窗 → 点击取消 → 不执行分析
- 点击分析按钮 → 弹出确认弹窗 → 点击确认 → 执行分析
- 点击大盘复盘按钮 → 弹出确认弹窗 → 点击取消 → 不执行复盘
- 点击大盘复盘按钮 → 弹出确认弹窗 → 点击确认 → 执行复盘
- 选中历史复盘报告 → 点击重新复盘按钮 → 弹出确认弹窗 → 点击取消 → 不执行
- 选中历史复盘报告 → 点击重新复盘按钮 → 弹出确认弹窗 → 点击确认 → 执行重新复盘
- 切换语言 → 确认弹窗文案跟随语言切换
