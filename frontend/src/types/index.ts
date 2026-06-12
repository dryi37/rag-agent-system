export interface User {
  id: number;
  username: string;
  email: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Thread {
  id: string;
  created_at: string;
  preview?: string; // first message preview (từ local state)
}

export interface Source {
  source: string;
  type: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  created_at?: string;
  isStreaming?: boolean;
  fromCache?: boolean;
}

export type StreamEvent =
  | { type: "token"; content: string }
  | { type: "status"; message: string }
  | { type: "cache_hit"; answer: string; sources: Source[] };
