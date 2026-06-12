"use client";

import { useState, useRef, useEffect } from "react";
import { ArrowUp } from "lucide-react";

interface ChatInputProps {
  onSend: (query: string) => void;
  disabled?: boolean;
  status?: string;
}

export function ChatInput({ onSend, disabled, status }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [value]);

  const handleSubmit = () => {
    const q = value.trim();
    if (!q || disabled) return;
    onSend(q);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="px-4 pb-4 pt-0">
      {status && (
        <p className="w-full bg-transparent text-[0.9375rem] text-ink placeholder-ink-faint resize-none focus:outline-none disabled:opacity-50 px-5 pt-4 pb-12 leading-relaxed">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          {status}
        </p>
      )}
      <div className="relative bg-surface-1 border border-surface-3 rounded-2xl shadow-sm focus-within:border-ink/20 focus-within:shadow-md transition-shadow">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Nhắn tin với RAG Agent"
          disabled={disabled}
          rows={1}
          className="w-full bg-transparent text-sm text-ink placeholder-ink-faint resize-none focus:outline-none disabled:opacity-50 px-4 pt-3.5 pb-10"
        />
        <div className="absolute bottom-2.5 right-2.5 flex items-center gap-2">
          <span className="text-[10px] text-ink-faint">
            {value.length > 0 ? "Enter ↵" : ""}
          </span>
          <button
            onClick={handleSubmit}
            disabled={!value.trim() || disabled}
            className="w-7 h-7 rounded-lg bg-ink disabled:bg-surface-3 disabled:cursor-not-allowed text-white disabled:text-ink-faint flex items-center justify-center transition"
          >
            <ArrowUp size={14} />
          </button>
        </div>
      </div>
      <p className="text-[10px] text-ink-faint text-center mt-2">
        AI có thể mắc lỗi. Kiểm tra thông tin quan trọng từ nguồn gốc.
      </p>
    </div>
  );
}