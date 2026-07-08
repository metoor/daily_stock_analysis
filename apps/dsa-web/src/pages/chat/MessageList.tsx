import { useCallback, useRef, useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ApiErrorAlert, Badge, EmptyState, ScrollArea } from '../../components/common';
import {
  useAgentChatStore,
  type Message,
  type ProgressStep,
} from '../../stores/agentChatStore';
import { cn } from '../../utils/cn';
import { getReportText } from '../../utils/reportLanguage';

interface QuickQuestion {
  label: string;
  skill: string;
}

interface MessageListProps {
  isMobile: boolean;
  quickQuestions: QuickQuestion[];
  onQuickQuestion: (q: QuickQuestion) => void;
  messagesViewportRef: React.RefObject<HTMLDivElement | null>;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  onScroll: () => void;
  showJumpToBottom: boolean;
  onJumpToBottom: () => void;
}

const getMessageSkillNames = (msg: Message): string[] => {
  if (msg.skillNames?.length) return msg.skillNames;
  if (msg.skillName) return [msg.skillName];
  if (msg.skills?.length) return msg.skills;
  if (msg.skill) return [msg.skill];
  return [];
};

const getMessageSkillLabel = (msg: Message): string => getMessageSkillNames(msg).join('、');

export function MessageList({
  isMobile,
  quickQuestions,
  onQuickQuestion,
  messagesViewportRef,
  messagesEndRef,
  onScroll,
  showJumpToBottom,
  onJumpToBottom,
}: MessageListProps) {
  const messages = useAgentChatStore((s) => s.messages);
  const loading = useAgentChatStore((s) => s.loading);
  const progressSteps = useAgentChatStore((s) => s.progressSteps);
  const chatError = useAgentChatStore((s) => s.chatError);

  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set());
  const [copiedMessages, setCopiedMessages] = useState<Set<string>>(new Set());
  const copyResetTimerRef = useRef<Partial<Record<string, number>>>({});
  const text = getReportText('zh');

  const toggleThinking = (msgId: string) => {
    setExpandedThinking((prev) => {
      const next = new Set(prev);
      if (next.has(msgId)) next.delete(msgId);
      else next.add(msgId);
      return next;
    });
  };

  const copyMessageToClipboard = async (msgId: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMessages((prev) => new Set(prev).add(msgId));
      const existingTimer = copyResetTimerRef.current[msgId];
      if (existingTimer !== undefined) {
        window.clearTimeout(existingTimer);
      }
      copyResetTimerRef.current[msgId] = window.setTimeout(() => {
        setCopiedMessages((prev) => {
          const next = new Set(prev);
          next.delete(msgId);
          return next;
        });
        delete copyResetTimerRef.current[msgId];
      }, 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  const downloadMessageAsMarkdown = useCallback((msg: Message) => {
    const skillLabel = getMessageSkillLabel(msg);
    const heading = msg.role === 'user' ? '# 用户消息' : `# AI 回复${skillLabel ? ` · ${skillLabel}` : ''}`;
    const content = [heading, '', msg.content].join('\n');
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${msg.role === 'user' ? 'user' : 'assistant'}-message-${msg.id}.md`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, []);

  const getCurrentStage = (steps: ProgressStep[]): string => {
    if (steps.length === 0) return '正在连接...';
    const last = steps[steps.length - 1];
    if (last.type === 'thinking') return last.message || 'AI 正在思考...';
    if (last.type === 'tool_start')
      return `${last.display_name || last.tool}...`;
    if (last.type === 'tool_done')
      return `${last.display_name || last.tool} 完成`;
    if (last.type === 'generating')
      return last.message || '正在生成最终分析...';
    return '处理中...';
  };

  const renderThinkingBlock = (msg: Message) => {
    if (!msg.thinkingSteps || msg.thinkingSteps.length === 0) return null;
    const isExpanded = expandedThinking.has(msg.id);
    const toolSteps = msg.thinkingSteps.filter((s) => s.type === 'tool_done');
    const totalDuration = toolSteps.reduce(
      (sum, s) => sum + (s.duration || 0),
      0,
    );
    const summary = `${toolSteps.length} 个工具调用 · ${totalDuration.toFixed(1)}s`;

    return (
      <button
        onClick={() => toggleThinking(msg.id)}
        className="flex items-center gap-2 text-xs text-muted-text hover:text-secondary-text transition-colors mb-2 w-full text-left"
      >
        <svg
          className={`w-3 h-3 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-90' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
        <span className="flex items-center gap-1.5">
          <span className="opacity-60">思考过程</span>
          <span className="text-muted-text/50">·</span>
          <span className="opacity-50">{summary}</span>
        </span>
      </button>
    );
  };

  const renderThinkingDetails = (steps: ProgressStep[]) => (
    <div className="mb-3 pl-5 border-l border-border/40 space-y-1.5 animate-fade-in">
      {steps.map((step, idx) => {
        let statusClass = 'chat-progress-item-muted';
        let iconClass = 'chat-progress-dot-muted';
        let stepText = '';
        if (step.type === 'thinking') {
          stepText = step.message || `第 ${step.step} 步：思考`;
          statusClass = 'chat-progress-item-thinking';
          iconClass = 'chat-progress-dot-thinking';
        } else if (step.type === 'tool_start') {
          stepText = `${step.display_name || step.tool}...`;
          statusClass = 'chat-progress-item-tool';
          iconClass = 'chat-progress-dot-tool';
        } else if (step.type === 'tool_done') {
          stepText = `${step.display_name || step.tool} (${step.duration}s)`;
          statusClass = step.success ? 'chat-progress-item-success' : 'chat-progress-item-danger';
          iconClass = step.success ? 'chat-progress-dot-success' : 'chat-progress-dot-danger';
        } else if (step.type === 'generating') {
          stepText = step.message || '生成分析';
          statusClass = 'chat-progress-item-generating';
          iconClass = 'chat-progress-dot-generating';
        }
        return (
          <div
            key={idx}
            className={cn('chat-progress-item', statusClass)}
          >
            <span className={cn('chat-progress-dot', iconClass)} />
            <span className="leading-relaxed">{stepText}</span>
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="relative z-10 flex min-h-0 flex-1 flex-col overflow-hidden border border-white/6 bg-card/78 glass-card">
      {chatError && (
        <div className="sticky top-0 z-20 border-b border-white/6 bg-card/95 backdrop-blur">
          <ApiErrorAlert error={chatError} />
        </div>
      )}
      <ScrollArea
        className="relative z-10 flex-1"
        viewportRef={messagesViewportRef}
        onScroll={onScroll}
        viewportClassName={isMobile ? 'space-y-4 p-3' : 'space-y-6 p-4 md:p-6'}
        testId="chat-message-scroll"
      >
        {messages.length === 0 && !loading ? (
          <div className="flex h-full items-center justify-center">
            <EmptyState
              title="开始问股"
              description={isMobile
                ? '输入「分析 600519」开始问股'
                : '输入「分析 600519」或「茅台现在能买吗」，AI 将调用实时数据工具为您生成决策报告。'
              }
              className="max-w-2xl border-dashed bg-card/55"
              icon={(
                <svg
                  className="h-8 w-8"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                  />
                </svg>
              )}
              action={(
                <div className={isMobile
                  ? 'grid grid-cols-2 gap-2 max-w-md'
                  : 'flex max-w-lg flex-wrap justify-center gap-2'
                }>
                  {quickQuestions.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => onQuickQuestion(q)}
                      className="quick-question-btn"
                    >
                      {q.label}
                    </button>
                  ))}
                </div>
              )}
            />
          </div>
        ) : (
          messages.map((msg) => {
            const skillLabel = getMessageSkillLabel(msg);
            const bubbleMaxWidth = isMobile
              ? msg.role === 'user' ? 'max-w-[85%]' : 'max-w-[92%]'
              : 'max-w-[min(100%,48rem)]';
            return (
              <div
                key={msg.id}
                className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <div
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[10px] font-bold shadow-sm transition-all',
                    msg.role === 'user' ? 'chat-avatar-user' : 'chat-avatar-ai'
                  )}
                >
                  {msg.role === 'user' ? 'U' : 'AI'}
                </div>
                <div
                  className={cn(
                    'group/message min-w-0 w-fit overflow-hidden px-5 py-3.5 transition-colors',
                    bubbleMaxWidth,
                    msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai'
                  )}
                >
                  {msg.role === 'assistant' && skillLabel && (
                    <div className="mb-2">
                      <Badge variant="info" className="chat-skill-badge shadow-none" aria-label={`技能 ${skillLabel}`}>
                        <svg
                          className="w-3 h-3"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M13 10V3L4 14h7v7l9-11h-7z"
                          />
                        </svg>
                        {skillLabel}
                      </Badge>
                    </div>
                  )}
                  {msg.role === 'assistant' && renderThinkingBlock(msg)}
                  {msg.role === 'assistant' &&
                    expandedThinking.has(msg.id) &&
                    msg.thinkingSteps &&
                    renderThinkingDetails(msg.thinkingSteps)}
                  {msg.role === 'assistant' ? (
                    <div className="relative">
                      <div className="chat-message-actions">
                        <button
                          type="button"
                          onClick={() => copyMessageToClipboard(msg.id, msg.content)}
                          className="chat-copy-btn"
                          aria-label={copiedMessages.has(msg.id) ? text.copied : text.copy}
                        >
                          {copiedMessages.has(msg.id) ? text.copied : text.copy}
                        </button>
                        <button
                          type="button"
                          onClick={() => downloadMessageAsMarkdown(msg)}
                          className="chat-copy-btn"
                          aria-label="导出此条消息为 Markdown"
                        >
                          导出
                        </button>
                      </div>
                      <div className={isMobile ? 'chat-prose' : 'chat-prose pr-20 sm:pr-24'}>
                        <Markdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </Markdown>
                      </div>
                    </div>
                  ) : (
                    msg.content
                      .split('\n')
                      .map((line, i) => (
                        <p
                          key={i}
                          className="mb-1 last:mb-0 leading-relaxed"
                        >
                          {line || ' '}
                        </p>
                      ))
                  )}
                </div>
              </div>
            );
          })
        )}

        {loading && (
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full bg-elevated text-foreground flex items-center justify-center flex-shrink-0 text-xs font-bold">
              AI
            </div>
            <div className="min-w-[200px] max-w-[min(100%,48rem)] overflow-hidden rounded-2xl rounded-tl-sm border border-white/6 bg-card/72 px-5 py-4">
              <div className="flex items-center gap-2.5 text-sm text-secondary-text">
                <div className="relative w-4 h-4 flex-shrink-0">
                  <div className="absolute inset-0 rounded-full border-2 border-cyan/20" />
                  <div className="absolute inset-0 rounded-full border-2 border-cyan border-t-transparent animate-spin" />
                </div>
                <span className="text-secondary-text">
                  {getCurrentStage(progressSteps)}
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </ScrollArea>

      {showJumpToBottom && !loading && (
        <div className={cn(
          'pointer-events-none absolute right-4 z-20',
          isMobile ? 'bottom-[5.75rem]' : 'bottom-24 md:right-6'
        )}>
          <button
            type="button"
            className="pointer-events-auto chat-copy-btn shadow-soft-card"
            onClick={onJumpToBottom}
            aria-label="查看最新消息"
          >
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 14l-7 7m0 0l-7-7m7 7V3"
              />
            </svg>
            有新消息
          </button>
        </div>
      )}
    </div>
  );
}
