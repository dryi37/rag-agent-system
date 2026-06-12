# RAG Agent Frontend

Next.js 14 frontend cho RAG Agent backend.

## Setup

```bash
npm install
cp .env.example .env.local
npm run dev
```

## Cấu trúc

```
src/
├── app/
│   ├── chat/page.tsx       # Trang chat chính
│   ├── login/page.tsx      # Đăng nhập
│   ├── register/page.tsx   # Đăng ký
│   └── layout.tsx
├── components/
│   ├── chat/
│   │   ├── MessageBubble.tsx   # Render message + sources + markdown
│   │   ├── ChatInput.tsx       # Input box với SSE status
│   │   └── EmptyState.tsx      # Empty state với suggestions
│   └── layout/
│       └── Sidebar.tsx         # Thread list + user info
├── hooks/
│   ├── useAuth.tsx         # Auth context (JWT tokens)
│   └── useChat.ts          # Chat state + streaming logic
├── lib/
│   └── api.ts              # API client với auto-refresh token
└── types/index.ts
```

## Backend endpoints cần thêm

Hiện tại backend **chưa có** 2 endpoints sau, cần implement để load lại history:

```python
# GET /threads  → list threads của user hiện tại
@router.get("", response_model=list[ThreadResponse])
async def list_threads(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    ...

# GET /threads/{thread_id}/messages  → load messages của thread
@router.get("/{thread_id}/messages")
async def get_messages(thread_id: str, db = Depends(get_db)):
    return await get_thread_messages(db, thread_id)
```

Cũng cần thêm `GET /auth/me` để verify token khi reload trang:

```python
@router.get("/me")
async def me(current_user = Depends(get_current_user)):
    return current_user
```

## Auth flow

- Login → nhận `access_token` + `refresh_token` → lưu `localStorage`
- Access token expire 15 phút → tự động refresh khi gặp 401
- Refresh token rotation: mỗi lần refresh sẽ revoke token cũ, cấp token mới
- Guest mode: dùng được chat mà không cần đăng nhập
