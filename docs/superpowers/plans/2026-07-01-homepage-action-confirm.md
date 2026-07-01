# 首页操作按钮二次确认 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add confirmation dialogs before the three homepage action buttons (Analyze, Market Review, Rerun Market Review) execute, preventing accidental triggers.

**Architecture:** Reuse the existing `ConfirmDialog` component with 3 `useState` guards in `HomePage.tsx`, following the same pattern as `SidebarNav` logout confirm. Add i18n keys for zh/en prompt text.

**Tech Stack:** React 19, TypeScript, existing `ConfirmDialog` component, existing i18n system (`useUiLanguage`)

## Global Constraints

- Follow existing `ConfirmDialog` usage pattern (useState + component, no hooks abstraction)
- Do NOT use `isDanger` prop — these are not destructive actions
- All user-facing text must go through i18n (`t('key')`)
- Do NOT modify `ConfirmDialog.tsx` itself
- Do NOT modify any backend code

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `apps/dsa-web/src/i18n/uiText.ts` | Modify | Add 6 i18n keys (3 title + 3 message) for zh and en blocks |
| `apps/dsa-web/src/pages/HomePage.tsx` | Modify | Add 3 useState, change 3 onClick handlers, add 3 ConfirmDialog instances, add ConfirmDialog import |

---

### Task 1: Add i18n keys for confirmation dialogs

**Files:**
- Modify: `apps/dsa-web/src/i18n/uiText.ts`

**Interfaces:**
- Produces: 6 i18n keys accessible via `t()`: `home.analyzeConfirmTitle`, `home.analyzeConfirmMessage`, `home.marketReviewConfirmTitle`, `home.marketReviewConfirmMessage`, `home.rerunMarketReviewConfirmTitle`, `home.rerunMarketReviewConfirmMessage`

- [ ] **Step 1: Add zh i18n keys**

In `apps/dsa-web/src/i18n/uiText.ts`, find the zh block line with `'home.rerunMarketReview': '重新复盘',` and add the 6 new keys immediately after the `'home.submitMarketReview': '提交中',` line:

```ts
  'home.submitMarketReview': '提交中',
  'home.analyzeConfirmTitle': '分析确认',
  'home.analyzeConfirmMessage': '确认开始分析？分析过程将消耗 LLM token。',
  'home.marketReviewConfirmTitle': '大盘复盘确认',
  'home.marketReviewConfirmMessage': '确认执行大盘复盘？复盘过程可能需要几分钟。',
  'home.rerunMarketReviewConfirmTitle': '重新复盘确认',
  'home.rerunMarketReviewConfirmMessage': '确认重新执行大盘复盘？将覆盖当前复盘结果。',
```

- [ ] **Step 2: Add en i18n keys**

In the same file, find the en block line with `'home.submitMarketReview': 'Submitting',` and add the 6 new keys immediately after it:

```ts
  'home.submitMarketReview': 'Submitting',
  'home.analyzeConfirmTitle': 'Confirm Analysis',
  'home.analyzeConfirmMessage': 'Start analysis? This will consume LLM tokens.',
  'home.marketReviewConfirmTitle': 'Confirm Market Review',
  'home.marketReviewConfirmMessage': 'Run market review? This may take a few minutes.',
  'home.rerunMarketReviewConfirmTitle': 'Confirm Rerun',
  'home.rerunMarketReviewConfirmMessage': 'Rerun market review? This will overwrite the current result.',
```

- [ ] **Step 3: Verify TypeScript compilation**

Run: `cd apps/dsa-web && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors related to uiText.ts

- [ ] **Step 4: Commit**

```bash
git add apps/dsa-web/src/i18n/uiText.ts
git commit -m "feat(i18n): add confirmation dialog keys for homepage actions"
```

---

### Task 2: Add confirmation dialogs to HomePage

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

**Interfaces:**
- Consumes: `ConfirmDialog` from `../components/common` (already exported from barrel)
- Consumes: i18n keys from Task 1

- [ ] **Step 1: Add ConfirmDialog to imports**

In `HomePage.tsx` line 10, the current import is:

```tsx
import { ApiErrorAlert, Button, Drawer, EmptyState, InlineAlert } from '../components/common';
```

Change to:

```tsx
import { ApiErrorAlert, Button, ConfirmDialog, Drawer, EmptyState, InlineAlert } from '../components/common';
```

- [ ] **Step 2: Add 3 useState declarations**

Find the existing `useState` declarations near the top of the `HomePage` component (after line 50). Add these 3 states after the existing state declarations (e.g., after the `sidebarOpen` state):

```tsx
  const [showAnalyzeConfirm, setShowAnalyzeConfirm] = useState(false);
  const [showMarketReviewConfirm, setShowMarketReviewConfirm] = useState(false);
  const [showRerunMarketReviewConfirm, setShowRerunMarketReviewConfirm] = useState(false);
```

- [ ] **Step 3: Change Analyze button onClick**

Find the analyze button at line 798:

```tsx
onClick={() => handleSubmitAnalysis()}
```

Change to:

```tsx
onClick={() => setShowAnalyzeConfirm(true)}
```

- [ ] **Step 4: Change Market Review button onClick**

Find the market review button at line 790:

```tsx
onClick={() => void handleTriggerMarketReview()}
```

Change to:

```tsx
onClick={() => setShowMarketReviewConfirm(true)}
```

- [ ] **Step 5: Change Rerun Market Review button onClick**

Find the rerun market review button at line 972:

```tsx
onClick={() => void handleTriggerMarketReview()}
```

Change to:

```tsx
onClick={() => setShowRerunMarketReviewConfirm(true)}
```

- [ ] **Step 6: Add 3 ConfirmDialog instances to JSX**

Find the closing `</div>` and `);` at the end of the return statement (around line 1082). Add the 3 ConfirmDialog instances just before the final `</div>`:

```tsx
      <ConfirmDialog
        isOpen={showAnalyzeConfirm}
        title={t('home.analyzeConfirmTitle')}
        message={t('home.analyzeConfirmMessage')}
        onConfirm={() => { setShowAnalyzeConfirm(false); handleSubmitAnalysis(); }}
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

Note: The Analyze button's `handleSubmitAnalysis()` does not return a Promise (it calls `submitAnalysis` internally with `void`), so no `void` prefix needed. The Market Review handlers are async, so `void` prefix is used to satisfy the `no-floating-promises` rule.

- [ ] **Step 7: Verify TypeScript compilation**

Run: `cd apps/dsa-web && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 8: Verify dev server starts**

Run: `cd apps/dsa-web && npx vite build 2>&1 | tail -5`
Expected: Build succeeds with no errors

- [ ] **Step 9: Commit**

```bash
git add apps/dsa-web/src/pages/HomePage.tsx
git commit -m "feat(home): add confirmation dialogs before analyze, market review, and rerun actions"
```

---

### Task 3: Manual verification

**Files:** None (runtime verification)

- [ ] **Step 1: Start dev server and verify in browser**

Run: `cd apps/dsa-web && npx vite dev`

Verify each scenario:
1. Click Analyze button → confirmation dialog appears with title "分析确认" and message about LLM token
2. Click Cancel → dialog closes, no analysis triggered
3. Click Analyze again → Click Confirm → analysis starts
4. Click 大盘复盘 button → confirmation dialog appears with title "大盘复盘确认"
5. Click Cancel → dialog closes, no review triggered
6. Click 大盘复盘 again → Click Confirm → review starts
7. Select a history market review record → Click 重新复盘 → confirmation dialog appears with title "重新复盘确认"
8. Click Cancel → dialog closes
9. Click 重新复盘 again → Click Confirm → rerun starts
10. Switch language to English → all dialog text switches to English

- [ ] **Step 2: Commit if any fixes were needed**

Only if verification revealed issues that required code changes.
