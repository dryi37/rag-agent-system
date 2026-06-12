"use client";

import { useState } from "react";
import Link from "next/link";
import { PencilLine, MessageSquare, LogOut, LogIn, ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import type { Thread } from "@/types";

interface SidebarProps {
  threads: Thread[];
  activeThreadId: string | null;
  onNewChat: () => void;
  onSelectThread: (id: string) => void;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 60_000) return "Vừa xong";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} phút trước`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} giờ trước`;
  return d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
}

export function Sidebar({ threads, activeThreadId, onNewChat, onSelectThread }: SidebarProps) {
  const { user, signOut } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside className={`relative flex flex-col bg-surface-1 border-r border-surface-3 transition-all duration-200 shrink-0 ${collapsed ? "w-14" : "w-64"}`}>
      {/* Header */}
      <div className="flex items-center px-3 py-3 border-b border-surface-3">
        {!collapsed && (
          <span className="text-sm font-semibold text-ink truncate flex-1">RAG Agent</span>
        )}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="p-1.5 rounded-md text-ink-faint hover:text-ink hover:bg-surface-2 transition ml-auto"
        >
          {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
        </button>
      </div>

      {/* New chat */}
      <div className="px-2 pt-3 pb-2">
        <button
          onClick={onNewChat}
          className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-2 text-sm font-medium border border-surface-3 bg-surface-1 text-ink-muted hover:bg-surface-2 hover:text-ink hover:border-accent/40 transition ${collapsed ? "justify-center" : ""}`}
        >
          <PencilLine size={14} />
          {!collapsed && <span>Chat mới</span>}
        </button>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        {!collapsed && threads.length > 0 && (
          <p className="text-[10px] font-medium text-ink-faint uppercase tracking-wider px-2 py-2">
            Lịch sử
          </p>
        )}
        {threads.map((thread) => (
          <button
            key={thread.id}
            onClick={() => onSelectThread(thread.id)}
            className={`flex items-start gap-2 w-full rounded-lg px-2.5 py-2 text-left transition ${
              activeThreadId === thread.id
                ? "bg-accent/10 text-ink border border-accent/20"
                : "text-ink-muted hover:bg-surface-2 hover:text-ink border border-transparent"
            } ${collapsed ? "justify-center" : ""}`}
            title={thread.preview ?? thread.id}
          >
            <MessageSquare size={13} className="mt-0.5 shrink-0" />
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="text-xs truncate leading-snug">
                  {thread.preview ?? `Thread ${thread.id.slice(0, 8)}`}
                </p>
                <p className="text-[10px] text-ink-faint mt-0.5">{formatDate(thread.created_at)}</p>
              </div>
            )}
          </button>
        ))}
        {!collapsed && threads.length === 0 && (
          <p className="text-xs text-ink-faint text-center py-8 px-2">Chưa có cuộc trò chuyện nào</p>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-surface-3 px-2 py-2">
        {user ? (
          <div className={`flex items-center gap-2 ${collapsed ? "justify-center" : ""}`}>
            {!collapsed && (
              <div className="min-w-0 flex-1 px-1">
                <p className="text-xs font-medium text-ink truncate">{user.username}</p>
                <p className="text-[10px] text-ink-faint truncate">{user.email}</p>
              </div>
            )}
            <button
              onClick={signOut}
              className="p-1.5 rounded-md text-ink-faint hover:text-danger hover:bg-danger/10 transition"
              title="Đăng xuất"
            >
              <LogOut size={14} />
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className={`flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-ink-muted hover:text-ink hover:bg-surface-2 transition ${collapsed ? "justify-center" : ""}`}
          >
            <LogIn size={14} />
            {!collapsed && <span>Đăng nhập</span>}
          </Link>
        )}
      </div>
    </aside>
  );
}