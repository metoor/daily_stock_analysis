import { useCallback, useRef, useState } from 'react';
import { Button, InlineAlert, Tooltip } from '../../components/common';
import { agentApi } from '../../api/agent';
import { getParsedApiError } from '../../api/error';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { downloadSession, formatSessionAsMarkdown } from '../../utils/chatExport';

interface ChatHeaderProps {
  onToggleSidebar: () => void;
  isMobile: boolean;
}

export function ChatHeader({ onToggleSidebar, isMobile }: ChatHeaderProps) {
  const messages = useAgentChatStore((s) => s.messages);
  const [sending, setSending] = useState(false);
  const [sendToast, setSendToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const sendToastTimerRef = useRef<number | null>(null);

  const showSendFeedback = useCallback(
    (nextToast: { type: 'success' | 'error'; message: string }, durationMs: number) => {
      if (sendToastTimerRef.current !== null) {
        window.clearTimeout(sendToastTimerRef.current);
      }
      setSendToast(nextToast);
      sendToastTimerRef.current = window.setTimeout(() => {
        setSendToast(null);
        sendToastTimerRef.current = null;
      }, durationMs);
    },
    [],
  );

  const handleSend = async () => {
    if (sending) return;
    setSending(true);
    setSendToast(null);
    try {
      const content = formatSessionAsMarkdown(messages);
      await agentApi.sendChat(content);
      showSendFeedback({ type: 'success', message: '已发送到通知渠道' }, 3000);
    } catch (err) {
      const parsed = getParsedApiError(err);
      showSendFeedback({
        type: 'error',
        message: parsed.message || '发送失败',
      }, 5000);
    } finally {
      setSending(false);
    }
  };

  const hasMessages = messages.length > 0;

  if (isMobile) {
    return (
      <header className="sticky top-0 z-30 flex-shrink-0 border-b border-white/6 bg-card/90 px-3 py-2 backdrop-blur">
        <div className="flex items-center justify-between gap-2">
          <button
            data-testid="chat-sidebar-toggle"
            onClick={onToggleSidebar}
            className="p-1.5 -ml-1 rounded-lg hover:bg-hover transition-colors text-secondary-text hover:text-foreground"
            aria-label="历史对话"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <h1 className="flex items-center gap-1.5 text-base font-bold text-foreground">
            <svg className="w-4 h-4 text-cyan" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            问股
          </h1>
          <div className="flex flex-shrink-0 items-center gap-1">
            {hasMessages && (
              <>
                <Tooltip content="导出会话为 Markdown 文件">
                  <span className="inline-flex">
                    <Button
                      variant="action-primary"
                      size="sm"
                      onClick={() => downloadSession(messages)}
                      aria-label="导出会话为 Markdown 文件"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                    </Button>
                  </span>
                </Tooltip>
                <Tooltip content="发送到已配置的通知机器人/邮箱">
                  <span className="inline-flex">
                    <Button
                      variant="action-primary"
                      size="sm"
                      disabled={sending}
                      onClick={handleSend}
                      aria-label="发送到已配置的通知机器人/邮箱"
                    >
                      {sending ? (
                        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                      )}
                    </Button>
                  </span>
                </Tooltip>
              </>
            )}
          </div>
        </div>
        {sendToast && (
          <InlineAlert
            variant={sendToast.type === 'success' ? 'success' : 'danger'}
            title={sendToast.type === 'success' ? '发送成功' : '发送失败'}
            message={sendToast.message}
            className="mt-2 rounded-xl px-3 py-2 text-xs shadow-none"
          />
        )}
      </header>
    );
  }

  return (
    <header className="mb-4 flex-shrink-0 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <svg className="w-6 h-6 text-cyan" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          问股
        </h1>
        {hasMessages && (
          <div className="flex flex-shrink-0 flex-wrap items-center justify-end gap-2">
            <Tooltip content="导出会话为 Markdown 文件">
              <span className="inline-flex">
                <Button
                  variant="action-primary"
                  size="sm"
                  onClick={() => downloadSession(messages)}
                  aria-label="导出会话为 Markdown 文件"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  导出会话
                </Button>
              </span>
            </Tooltip>
            <Tooltip content="发送到已配置的通知机器人/邮箱">
              <span className="inline-flex">
                <Button
                  variant="action-primary"
                  size="sm"
                  disabled={sending}
                  onClick={handleSend}
                  aria-label="发送到已配置的通知机器人/邮箱"
                >
                  {sending ? (
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  )}
                  发送
                </Button>
              </span>
            </Tooltip>
          </div>
        )}
      </div>
      <p className="text-secondary-text text-sm">
        向 AI 询问个股分析，获取基于技能视角的交易建议与实时决策报告。
      </p>
      {sendToast && (
        <InlineAlert
          variant={sendToast.type === 'success' ? 'success' : 'danger'}
          title={sendToast.type === 'success' ? '发送成功' : '发送失败'}
          message={sendToast.message}
          className="max-w-md rounded-xl px-3 py-2 text-xs shadow-none"
        />
      )}
    </header>
  );
}
