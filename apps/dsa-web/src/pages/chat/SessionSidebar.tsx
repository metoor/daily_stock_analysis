import { useState } from 'react';
import { ConfirmDialog, ScrollArea } from '../../components/common';
import { DashboardStateBlock } from '../../components/dashboard';
import { useAgentChatStore } from '../../stores/agentChatStore';

interface SessionSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  isMobile: boolean;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
}

export function SessionSidebar({
  isMobile,
  onClose,
  onSelectSession,
  onNewChat,
  onDeleteSession,
}: SessionSidebarProps) {
  const sessions = useAgentChatStore((s) => s.sessions);
  const sessionsLoading = useAgentChatStore((s) => s.sessionsLoading);
  const sessionId = useAgentChatStore((s) => s.sessionId);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const handleSelect = (id: string) => {
    onSelectSession(id);
    if (isMobile) onClose();
  };

  return (
    <>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-white/5 bg-white/2 p-3.5">
          <h2 className="text-sm font-semibold text-cyan uppercase tracking-[0.2em] flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            历史对话
          </h2>
          <button
            onClick={onNewChat}
            className="rounded-lg p-1.5 text-muted-text transition-all hover:bg-white/10 hover:text-foreground"
            aria-label="开启新对话"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
          </button>
        </div>
        <ScrollArea testId="chat-session-list-scroll" viewportClassName="p-3">
          {sessionsLoading ? (
            <DashboardStateBlock
              loading
              compact
              title="加载对话中..."
              className="rounded-2xl border border-dashed border-border/50 bg-surface/30"
            />
          ) : sessions.length === 0 ? (
            <DashboardStateBlock
              compact
              title="暂无历史对话"
              description="开始提问后，这里会保留会话记录。"
              className="rounded-2xl border border-dashed border-border/50 bg-surface/30"
            />
          ) : (
            <div className="space-y-2">
              {sessions.map((s) => (
                <div key={s.session_id} className="session-item-row">
                  <button
                    type="button"
                    onClick={() => handleSelect(s.session_id)}
                    className={`session-item ${s.session_id === sessionId ? 'active' : ''}`}
                    aria-label={`切换到对话 ${s.title}`}
                    aria-current={s.session_id === sessionId ? 'page' : undefined}
                  >
                    <div className="indicator" />
                    <div className="content">
                      <span className="title">{s.title}</span>
                      <div className="mt-0.5 flex items-center gap-2">
                        <span className="meta">
                          {s.message_count} 条对话
                        </span>
                        {s.last_active && (
                          <>
                            <span className="separator" />
                            <span className="meta">
                              {new Date(s.last_active).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </button>
                  <button
                    type="button"
                    className="delete-btn"
                    onClick={() => {
                      setDeleteConfirmId(s.session_id);
                    }}
                    aria-label={`删除对话 ${s.title}`}
                  >
                    <svg
                      className="w-3.5 h-3.5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>
      <ConfirmDialog
        isOpen={Boolean(deleteConfirmId)}
        title="删除对话"
        message="删除后，该对话将不可恢复，确认删除吗？"
        confirmText="删除"
        cancelText="取消"
        isDanger
        onConfirm={() => {
          if (deleteConfirmId) onDeleteSession(deleteConfirmId);
          setDeleteConfirmId(null);
        }}
        onCancel={() => setDeleteConfirmId(null)}
      />
    </>
  );
}
