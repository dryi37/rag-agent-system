"use client";

const suggestions = [
  { icon: "🔍", text: "Tìm kiếm thông tin trong tài liệu nội bộ" },
  { icon: "⚖️", text: "So sánh và tổng hợp các khái niệm" },
  { icon: "💡", text: "Giải thích chi tiết một vấn đề cụ thể" },
  { icon: "📝", text: "Tóm tắt nội dung tài liệu" },
];

interface EmptyStateProps {
  onSuggestion: (text: string) => void;
}

export function EmptyState({ onSuggestion }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4 py-16 text-center">
      <div className="w-12 h-12 rounded-2xl bg-accent flex items-center justify-center mb-5 shadow-sm">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-white">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <h2 className="text-2xl font-semibold text-ink mb-2">Xin chào!</h2>
      <p className="text-sm text-ink-muted mb-8 max-w-xs leading-relaxed">
        Đặt câu hỏi để tìm kiếm thông tin từ tài liệu nội bộ và web
      </p>

      <div className="grid grid-cols-1 gap-2 w-full max-w-lg">
        {suggestions.map((s) => (
          <button
            key={s.text}
            onClick={() => onSuggestion(s.text)}
            className="flex items-start gap-3 text-left bg-surface-1 hover:bg-surface-2 border border-surface-3 hover:border-accent/30 rounded-2xl px-4 py-4 transition shadow-sm group"
          >
            <span className="text-lg mt-0.5">{s.icon}</span>
            <span className="text-sm text-ink-muted group-hover:text-ink leading-snug">{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}