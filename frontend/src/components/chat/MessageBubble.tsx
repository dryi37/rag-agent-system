"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ExternalLink, Zap, FileText } from "lucide-react";
import type { Message } from "@/types";

interface MessageBubbleProps {
  message: Message;
}

function SourceBadge({ source, type }: { source: string; type: string }) {
  const isWeb = type === "web_search" || source.startsWith("http");
  const label = isWeb
    ? source.replace(/^https?:\/\/(www\.)?/, "").split("/")[0]
    : source.split("/").pop() ?? source;

  const inner = (
    <span className="inline-flex items-center gap-1 text-[10px] bg-surface-2 border border-surface-3 text-ink-muted rounded-full px-2 py-0.5 hover:border-accent/40 hover:text-ink transition">
      {isWeb ? <ExternalLink size={9} /> : <FileText size={9} />}
      <span className="truncate max-w-[120px]">{label}</span>
    </span>
  );

  return isWeb ? (
    <a href={source} target="_blank" rel="noopener noreferrer" className="cursor-pointer">
      {inner}
    </a>
  ) : (
    <span className="cursor-default">{inner}</span>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isEmpty = !message.content && message.isStreaming;

  return (
    <div className={`flex gap-3 animate-slide-up ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-[11px] font-semibold ${
        isUser
          ? "bg-ink text-surface-0"
          : "bg-accent text-white"
      }`}>
        {isUser ? "U" : "R"}
      </div>

      {/* Content */}
      <div className={`max-w-[80%] min-w-0 flex flex-col gap-1.5 ${isUser ? "items-end" : "items-start"}`}>
        {isUser ? (
          <div className="bg-surface-1 border border-surface-3 text-ink rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm shadow-sm">
            {message.content}
          </div>
        ) : (
          <div className="text-sm w-full">
            {isEmpty ? (
              <div className="flex gap-1 items-center h-6">
                {[0, 150, 300].map((delay) => (
                  <span
                    key={delay}
                    className="w-1.5 h-1.5 rounded-full bg-accent"
                    style={{ animation: `pulse 1.4s ease-in-out ${delay}ms infinite` }}
                  />
                ))}
              </div>
            ) : (
              <div className={`prose-chat ${message.isStreaming ? "cursor-blink" : ""}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
        )}

        {/* Sources */}
        {!isUser && !message.isStreaming && message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {message.fromCache && (
              <span className="inline-flex items-center gap-1 text-[10px] bg-success/10 text-success border border-success/20 rounded-full px-2 py-0.5">
                <Zap size={9} />
                Cached
              </span>
            )}
            {message.sources.map((s, i) => (
              <SourceBadge key={i} source={s.source} type={s.type} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}