"use client";

import { useEffect, useRef } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ChatInput } from "@/components/chat/ChatInput";
import { EmptyState } from "@/components/chat/EmptyState";
import { useChat } from "@/hooks/useChat";

export default function ChatPage() {
  const { threads, activeThreadId, getMessages, sendMessage, startNewThread, selectThread, isLoading, status } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messages = activeThreadId ? getMessages(activeThreadId) : [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex h-screen bg-surface-0 overflow-hidden">
      <Sidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onNewChat={startNewThread}
        onSelectThread={selectThread}
      />

      <main className="flex flex-col flex-1 min-w-0 bg-surface-0">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <EmptyState onSuggestion={sendMessage} />
          ) : (
            <div className="max-w-[700px] w-full mx-auto px-6 py-10 space-y-8">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="max-w-[700px] w-full mx-auto px-6 pb-6 pt-2">
          <ChatInput onSend={sendMessage} disabled={isLoading} status={status} />
        </div>
      </main>
    </div>
  );
}