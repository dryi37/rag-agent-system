FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY requirements.txt .
RUN uv pip install --no-cache --system -r requirements.txt

COPY --chown=appuser:appuser main.py .

RUN mkdir -p /models && chown -R appuser:appuser /models

USER appuser

ENV HF_HOME=/models

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]