import type { AuthTokens, Source } from "@/types";

// Server-side proxy (non-streaming calls)
const BASE = "/api";

// Direct backend URL for streaming (bypass Next.js proxy buffering)
function getDirectBase(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

// ─── Token storage ───────────────────────────────────────────────────────────

export function getAccessToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
}

export function getRefreshToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null;
}

export function saveTokens(tokens: AuthTokens) {
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

// ─── Base fetch with auto-refresh ────────────────────────────────────────────

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh_token = getRefreshToken();
  if (!refresh_token) return null;

  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    });
    if (!res.ok) { clearTokens(); return null; }
    const tokens: AuthTokens = await res.json();
    saveTokens(tokens);
    return tokens.access_token;
  } catch {
    clearTokens();
    return null;
  }
}

export async function apiFetch(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<Response> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401 && retry) {
    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => { refreshPromise = null; });
    }
    const newToken = await refreshPromise;
    if (!newToken) {
      clearTokens();
      window.location.href = "/login";
      return res;
    }
    headers["Authorization"] = `Bearer ${newToken}`;
    return fetch(`${BASE}${path}`, { ...options, headers });
  }

  return res;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export async function login(username: string, password: string): Promise<AuthTokens> {
  const body = new URLSearchParams({ username, password });
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Login failed");
  }
  return res.json();
}

export async function register(username: string, email: string, password: string) {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Registration failed");
  }
  return res.json();
}

export async function logout() {
  const refresh_token = getRefreshToken();
  if (refresh_token) {
    await apiFetch("/auth/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    }).catch(() => {});
  }
  clearTokens();
}

// ─── Threads ──────────────────────────────────────────────────────────────────

export async function createThread(): Promise<{ thread_id: string }> {
  const res = await apiFetch("/threads", { method: "POST" });
  if (!res.ok) throw new Error("Failed to create thread");
  return res.json();
}

export async function listThreads(): Promise<{ id: string; created_at: string }[]> {
  const res = await apiFetch("/threads");
  if (!res.ok) return [];
  return res.json();
}

export async function getThreadMessages(threadId: string) {
  const res = await apiFetch(`/threads/${threadId}/messages`);
  if (!res.ok) return [];
  return res.json();
}

// ─── Streaming chat (direct to backend, bypass Next.js proxy) ────────────────

export async function* streamMessage(
  threadId: string,
  query: string,
  onStatus?: (msg: string) => void
): AsyncGenerator<{ token?: string; sources?: Source[]; fromCache?: boolean }> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Gọi thẳng backend để tránh Next.js proxy buffer mất streaming
  const url = `${getDirectBase()}/threads/${threadId}/messages`;

  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({ query }),
  });

  if (!res.ok || !res.body) throw new Error("Stream failed");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const event = JSON.parse(line.slice(6));
        if (event.type === "token") {
          yield { token: event.content };
        } else if (event.type === "status") {
          onStatus?.(event.message);
        } else if (event.type === "sources") {    
          yield { sources: event.sources };
        } else if (event.type === "cache_hit") {
          yield { token: event.answer, sources: event.sources, fromCache: true };
        }
      } catch {}
    }
  }
}