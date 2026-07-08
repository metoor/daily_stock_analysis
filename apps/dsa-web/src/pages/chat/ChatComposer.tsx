import { useState, useEffect, useCallback } from 'react';
import { Plus, X, SlidersHorizontal, ChevronDown } from 'lucide-react';
import { ApiErrorAlert, Button, InlineAlert } from '../../components/common';
import type { SkillInfo } from '../../api/agent';
import { systemConfigApi } from '../../api/systemConfig';
import { getParsedApiError } from '../../api/error';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { cn } from '../../utils/cn';

const MAX_SELECTED_SKILLS = 3;
const CONTEXT_COMPRESSION_CONFIG_KEY = 'AGENT_CONTEXT_COMPRESSION_ENABLED';

interface ChatComposerProps {
  isMobile: boolean;
  composerValue: string;
  setComposerValue: (v: string) => void;
  onSend: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  skills: SkillInfo[];
  selectedSkillIds: string[];
  setSelectedSkillIds: (ids: string[]) => void;
  toggleSkillSelection: (id: string) => void;
  selectedSkillSummary: string;
  activeStockCode: string | null;
  onToggleWatchlist: (code: string) => void;
  stockInWatchlist: (code: string) => boolean;
  isWatchlistActioning: boolean;
  watchlistMessage: string | null;
  isFollowUpContextLoading: boolean;
}

export function ChatComposer({
  isMobile,
  composerValue,
  setComposerValue,
  onSend,
  onKeyDown,
  skills,
  selectedSkillIds,
  setSelectedSkillIds,
  toggleSkillSelection,
  selectedSkillSummary,
  activeStockCode,
  onToggleWatchlist,
  stockInWatchlist,
  isWatchlistActioning,
  watchlistMessage,
  isFollowUpContextLoading,
}: ChatComposerProps) {
  const loading = useAgentChatStore((s) => s.loading);
  const chatError = useAgentChatStore((s) => s.chatError);

  const [showSkillDesc, setShowSkillDesc] = useState<string | null>(null);
  const [composerOpen, setComposerOpen] = useState(false);
  const [contextCompressionEnabled, setContextCompressionEnabled] = useState(false);
  const [contextCompressionLoaded, setContextCompressionLoaded] = useState(false);
  const [contextCompressionSaving, setContextCompressionSaving] = useState(false);
  const [contextCompressionError, setContextCompressionError] = useState<string | null>(null);
  const [configVersion, setConfigVersion] = useState('');
  const [maskToken, setMaskToken] = useState('******');

  const updateContextCompressionEnabled = useCallback(async (nextEnabled: boolean) => {
    if (!contextCompressionLoaded || contextCompressionSaving) return;
    const previousEnabled = contextCompressionEnabled;
    setContextCompressionEnabled(nextEnabled);
    setContextCompressionSaving(true);
    setContextCompressionError(null);
    try {
      const result = await systemConfigApi.update({
        configVersion,
        maskToken,
        reloadNow: true,
        items: [{ key: CONTEXT_COMPRESSION_CONFIG_KEY, value: nextEnabled ? 'true' : 'false' }],
      });
      setConfigVersion(result.configVersion || configVersion);
    } catch (error) {
      setContextCompressionEnabled(previousEnabled);
      const parsed = getParsedApiError(error);
      setContextCompressionError(parsed.message || '上下文压缩设置保存失败');
    } finally {
      setContextCompressionSaving(false);
    }
  }, [contextCompressionLoaded, contextCompressionSaving, contextCompressionEnabled, configVersion, maskToken]);

  useEffect(() => {
    let active = true;
    void systemConfigApi.getConfig(false)
      .then((cfg) => {
        if (!active) return;
        const item = cfg.items.find((i) => i.key === CONTEXT_COMPRESSION_CONFIG_KEY);
        setContextCompressionEnabled(String(item?.value ?? '').trim().toLowerCase() === 'true');
        setConfigVersion(cfg.configVersion);
        setMaskToken(cfg.maskToken || '******');
        setContextCompressionLoaded(true);
        setContextCompressionError(null);
      })
      .catch((error) => {
        if (!active) return;
        const parsed = getParsedApiError(error);
        setContextCompressionLoaded(false);
        setContextCompressionError(parsed.message || '无法读取上下文压缩配置');
      });
    return () => { active = false; };
  }, []);

  const selectedSkillIdSet = new Set(selectedSkillIds);
  const skillLimitReached = selectedSkillIds.length >= MAX_SELECTED_SKILLS;

  const selectedBadges = selectedSkillIds.length > 0 ? (
    <div className="mb-2 flex flex-wrap gap-1">
      {selectedSkillIds.map((id) => {
        const skill = skills.find((s) => s.id === id);
        return (
          <span key={id} className="inline-flex items-center gap-1 rounded-full bg-cyan/15 px-2 py-0.5 text-xs text-cyan">
            {skill?.name}
            <button
              onClick={() => toggleSkillSelection(id)}
              aria-label={`移除 ${skill?.name}`}
              className="hover:text-cyan/70"
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        );
      })}
    </div>
  ) : null;

  const skillChips = (
    <div className="flex gap-2 overflow-x-auto pb-1">
      <button
        onClick={() => setSelectedSkillIds([])}
        className={cn(
          'flex-shrink-0 rounded-full border px-3 py-1.5 text-xs',
          selectedSkillIds.length === 0
            ? 'border-cyan bg-cyan/15 text-cyan'
            : 'border-white/10 text-secondary-text',
        )}
      >
        通用分析
      </button>
      {skills.map((s) => {
        const checked = selectedSkillIdSet.has(s.id);
        const disabled = !checked && skillLimitReached;
        return (
          <button
            key={s.id}
            disabled={disabled}
            onClick={() => toggleSkillSelection(s.id)}
            className={cn(
              'flex-shrink-0 rounded-full border px-3 py-1.5 text-xs',
              checked ? 'border-cyan bg-cyan/15 text-cyan' : 'border-white/10 text-secondary-text',
              disabled && 'opacity-40',
            )}
          >
            {s.name}
          </button>
        );
      })}
    </div>
  );

  const desktopSkillCheckboxes = (
    <div className="flex flex-wrap items-start gap-x-5 gap-y-2">
      <span className="text-xs text-muted-text font-medium uppercase tracking-wider flex-shrink-0 mt-1">
        策略
      </span>
      <label className="flex items-center gap-1.5 text-sm cursor-pointer group mt-0.5">
        <input
          type="checkbox"
          checked={selectedSkillIds.length === 0}
          onChange={() => setSelectedSkillIds([])}
          className="chat-skill-checkbox"
        />
        <span className={cn('text-sm', selectedSkillIds.length === 0 ? 'text-foreground font-medium' : 'text-secondary-text group-hover:text-foreground')}>
          通用分析
        </span>
      </label>
      {skills.map((s) => {
        const checked = selectedSkillIdSet.has(s.id);
        const disabled = !checked && skillLimitReached;
        return (
          <label
            key={s.id}
            className={cn('flex items-center gap-1.5 cursor-pointer group relative mt-0.5', disabled && 'opacity-60 cursor-not-allowed')}
            onMouseEnter={() => setShowSkillDesc(s.id)}
            onMouseLeave={() => setShowSkillDesc(null)}
          >
            <input
              type="checkbox"
              checked={checked}
              disabled={disabled}
              onChange={() => toggleSkillSelection(s.id)}
              className="chat-skill-checkbox"
            />
            <span className={cn('text-sm', checked ? 'text-foreground font-medium' : 'text-secondary-text group-hover:text-foreground')}>
              {s.name}
            </span>
            {showSkillDesc === s.id && s.description && (
              <div className="skill-desc-tooltip">
                <p className="skill-title">{s.name}</p>
                <p>{s.description}</p>
              </div>
            )}
          </label>
        );
      })}
    </div>
  );

  const stockCodeDisplay = activeStockCode && (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-text font-mono">{activeStockCode}</span>
      <Button
        variant="secondary"
        size="xsm"
        isLoading={isWatchlistActioning}
        onClick={() => onToggleWatchlist(activeStockCode)}
        className="text-[11px]"
      >
        {stockInWatchlist(activeStockCode) ? '从自选删除' : '加入自选'}
      </Button>
      {watchlistMessage && (
        <span className="text-[11px] text-secondary-text animate-in fade-in">{watchlistMessage}</span>
      )}
    </div>
  );

  if (isMobile) {
    return (
      <div className="sticky bottom-0 z-20 border-t border-white/6 bg-card/88 px-3 py-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))]">
        {isFollowUpContextLoading && (
          <InlineAlert
            variant="info"
            title="追问上下文加载中"
            message="正在加载历史分析上下文；现在可直接发送追问。"
            className="mb-2 rounded-xl px-3 py-2 text-xs shadow-none"
          />
        )}
        {selectedBadges}
        <div className="flex items-end gap-2">
          <button
            type="button"
            onClick={() => setComposerOpen((open) => !open)}
            className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full border border-white/6 bg-surface/50 text-secondary-text hover:text-foreground"
            aria-label="展开更多选项"
          >
            <Plus className="h-5 w-5" />
          </button>
          <textarea
            value={composerValue}
            onChange={(e) => setComposerValue(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="分析 600519 / 茅台现在能买吗？"
            disabled={loading}
            rows={1}
            className="input-surface input-focus-glow flex-1 min-h-[48px] max-h-[120px] rounded-2xl border bg-transparent px-4 py-3 text-sm transition-all focus:outline-none resize-none disabled:cursor-not-allowed disabled:opacity-60"
            style={{ height: 'auto' }}
            onInput={(e) => {
              const t = e.target as HTMLTextAreaElement;
              t.style.height = 'auto';
              t.style.height = `${Math.min(t.scrollHeight, 120)}px`;
            }}
          />
          <button
            type="button"
            onClick={onSend}
            disabled={!composerValue.trim() || loading}
            className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-cyan text-white disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="发送"
          >
            {loading ? (
              <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </div>

        {composerOpen && (
          <div
            data-testid="chat-composer-drawer"
            className="fixed inset-0 z-50 flex items-end"
            onClick={() => setComposerOpen(false)}
          >
            <div className="page-drawer-overlay absolute inset-0" />
            <div
              className="relative w-full rounded-t-2xl border-t border-white/10 bg-card/95 p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] backdrop-blur"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-medium text-foreground">更多选项</h3>
                <button onClick={() => setComposerOpen(false)} aria-label="关闭">
                  <X className="w-4 h-4 text-secondary-text" />
                </button>
              </div>
              <label className="mb-3 flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={contextCompressionEnabled}
                  disabled={!contextCompressionLoaded || contextCompressionSaving}
                  onChange={(e) => void updateContextCompressionEnabled(e.target.checked)}
                  className="chat-skill-checkbox"
                />
                <span className="font-medium">上下文压缩</span>
                <span className="text-xs text-muted-text">节省长会话 token</span>
              </label>
              {contextCompressionError && (
                <InlineAlert
                  variant="danger"
                  title="上下文压缩设置未保存"
                  message={contextCompressionError}
                  className="mb-3 rounded-xl px-3 py-2 text-xs shadow-none"
                />
              )}
              <div className="mb-3">
                <span className="mb-1.5 block text-xs text-muted-text font-medium uppercase tracking-wider">策略</span>
                {skillChips}
              </div>
              {stockCodeDisplay}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="border-t border-white/6 bg-card/88 p-4 md:p-6 relative z-20">
      <div className="space-y-3">
        {chatError ? <ApiErrorAlert error={chatError} /> : null}
        {isFollowUpContextLoading ? (
          <InlineAlert
            variant="info"
            title="追问上下文加载中"
            message="正在加载历史分析上下文；现在可直接发送追问。"
            className="rounded-xl px-3 py-2 text-xs shadow-none"
          />
        ) : null}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/6 bg-surface/25 px-3 py-2">
          <label
            className={cn(
              'inline-flex items-center gap-2 text-sm',
              contextCompressionLoaded && !contextCompressionSaving
                ? 'cursor-pointer text-foreground'
                : 'cursor-not-allowed text-muted-text',
            )}
          >
            <input
              type="checkbox"
              checked={contextCompressionEnabled}
              disabled={!contextCompressionLoaded || contextCompressionSaving}
              onChange={(event) => void updateContextCompressionEnabled(event.target.checked)}
              className="chat-skill-checkbox"
            />
            <span className="font-medium">上下文压缩</span>
            <span className="text-xs text-muted-text">节省长会话 token</span>
          </label>
          <span className="text-xs text-muted-text">
            {contextCompressionSaving
              ? '保存中...'
              : contextCompressionEnabled
                ? '已启用'
                : '未启用'}
          </span>
        </div>
        {contextCompressionError ? (
          <InlineAlert
            variant="danger"
            title="上下文压缩设置未保存"
            message={contextCompressionError}
            className="rounded-xl px-3 py-2 text-xs shadow-none"
          />
        ) : null}
        {skills.length > 0 && (
          <div className="space-y-2">
            <button
              type="button"
              className="home-surface-button flex h-10 w-full items-center justify-between gap-3 rounded-xl px-3 text-left text-sm text-foreground md:hidden"
              aria-label="展开策略选择"
              aria-expanded={false}
              aria-controls="chat-skill-picker-panel"
              onClick={() => {}}
            >
              <span className="flex min-w-0 items-center gap-2">
                <SlidersHorizontal className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
                <span className="flex-shrink-0 font-medium">策略</span>
                <span className="truncate text-xs text-muted-text">{selectedSkillSummary}</span>
              </span>
              <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-text transition-transform" aria-hidden="true" />
            </button>
            <div
              id="chat-skill-picker-panel"
              data-testid="chat-skill-picker-panel"
              className="flex max-h-none flex-wrap items-start gap-x-5 gap-y-2 md:overflow-visible md:border-0 md:bg-transparent md:p-0"
            >
              {desktopSkillCheckboxes}
            </div>
          </div>
        )}
        {stockCodeDisplay}
        <div className="flex items-end gap-3">
          <textarea
            value={composerValue}
            onChange={(e) => setComposerValue(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="例如：分析 600519 / 茅台现在适合买入吗？ (Enter 发送, Shift+Enter 换行)"
            disabled={loading}
            rows={1}
            className="input-surface input-focus-glow flex-1 min-h-[44px] max-h-[200px] rounded-xl border bg-transparent px-4 py-2.5 text-sm transition-all focus:outline-none resize-none disabled:cursor-not-allowed disabled:opacity-60"
            style={{ height: 'auto' }}
            onInput={(e) => {
              const t = e.target as HTMLTextAreaElement;
              t.style.height = 'auto';
              t.style.height = `${Math.min(t.scrollHeight, 200)}px`;
            }}
          />
          <Button
            variant="primary"
            onClick={onSend}
            disabled={!composerValue.trim() || loading}
            isLoading={loading}
            className="btn-primary flex-shrink-0"
          >
            发送
          </Button>
        </div>
      </div>
    </div>
  );
}
