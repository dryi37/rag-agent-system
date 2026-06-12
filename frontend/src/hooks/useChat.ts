"use client";

import { useState, useCallback, useRef } from "react";
import { createThread, streamMessage } from "@/lib/api";
import type { Message, Thread, Source } from "@/types";

export function useChat() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Map<string, Message[]>>(new Map());
  const [status, setStatus] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef(false);

  const getMessages = (threadId: string) => messages.get(threadId) ?? [];

  const startNewThread = useCallback(async () => {
    const { thread_id } = await createThread();
    const newThread: Thread = { id: thread_id, created_at: new Date().toISOString() };
    setThreads((prev) => [newThread, ...prev]);
    setActiveThreadId(thread_id);
    setMessages((prev) => new Map(prev).set(thread_id, []));
    return thread_id;
  }, []);

  const selectThread = useCallback((threadId: string) => {
    setActiveThreadId(threadId);
    setStatus("");
  }, []);

  const sendMessage = useCallback(
    async (query: string, threadId?: string) => {
      let tid = threadId ?? activeThreadId;
      if (!tid) {
        tid = await startNewThread();
      }

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: query,
        created_at: new Date().toISOString(),
      };

      // Update thread preview
      setThreads((prev) =>
        prev.map((t) => (t.id === tid ? { ...t, preview: query.slice(0, 60) } : t))
      );

      setMessages((prev) => {
        const next = new Map(prev);
        const existing = next.get(tid!) ?? [];
        next.set(tid!, [...existing, userMsg]);
        return next;
      });

      // Placeholder assistant message
      const assistantId = crypto.randomUUID();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => {
        const next = new Map(prev);
        const existing = next.get(tid!) ?? [];
        next.set(tid!, [...existing, assistantMsg]);
        return next;
      });

      setIsLoading(true);
      setStatus("");
      abortRef.current = false;

      try {
        let fullContent = "";
        let finalSources: Source[] = [];
        let fromCache = false;

        for await (const event of streamMessage(tid, query, setStatus)) {
          if (abortRef.current) break;
          if (event.token) fullContent += event.token;
          if (event.sources) finalSources = event.sources;
          if (event.fromCache) fromCache = true;

          setMessages((prev) => {
            const next = new Map(prev);
            const msgs = [...(next.get(tid!) ?? [])];
            const idx = msgs.findIndex((m) => m.id === assistantId);
            if (idx >= 0) {
              msgs[idx] = { ...msgs[idx], content: fullContent, isStreaming: true };
            }
            next.set(tid!, msgs);
            return next;
          });
        }

        // Finalize
        setMessages((prev) => {
          const next = new Map(prev);
          const msgs = [...(next.get(tid!) ?? [])];
          const idx = msgs.findIndex((m) => m.id === assistantId);
          if (idx >= 0) {
            msgs[idx] = {
              ...msgs[idx],
              content: fullContent,
              sources: finalSources,
              fromCache,
              isStreaming: false,
            };
          }
          next.set(tid!, msgs);
          return next;
        });
      } catch (err) {
        setMessages((prev) => {
          const next = new Map(prev);
          const msgs = [...(next.get(tid!) ?? [])];
          const idx = msgs.findIndex((m) => m.id === assistantId);
          if (idx >= 0) {
            msgs[idx] = {
              ...msgs[idx],
              content: "Đã xảy ra lỗi khi kết nối. Vui lòng thử lại.",
              isStreaming: false,
            };
          }
          next.set(tid!, msgs);
          return next;
        });
      } finally {
        setIsLoading(false);
        setStatus("");
      }
    },
    [activeThreadId, startNewThread]
  );

  return {
    threads,
    setThreads,
    activeThreadId,
    getMessages,
    sendMessage,
    startNewThread,
    selectThread,
    isLoading,
    status,
  };
}
