# stage1: builder
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY requirements.txt .

RUN uv venv /opt/venv && uv pip install --no-cache --python /opt/venv/bin/python -r requirements.txt

# stage2: runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=appuser:appuser . .

USER appuser

CMD ["uvicorn", "rag_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]