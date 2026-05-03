import os
import time
import torch
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import CrossEncoder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__) 

MODEL_NAME = os.getenv("MODEL_NAME", "BAAI/bge-reranker-v2-m3")
MODEL_DIR = os.getenv("MODEL_DIR", "/models/bge-reranker-v2-m3")
USE_FP16   = os.getenv("USE_FP16", "true").lower() == "true"

reranker: CrossEncoder = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global reranker

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_path = MODEL_DIR if os.path.exists(MODEL_DIR) else MODEL_NAME

    logger.info(f"Loading reranker: {model_path} on {device}")
    
    reranker = CrossEncoder(
        model_path,
        max_length=512,
        device=device
    )

    if USE_FP16 and device == "cuda":
        reranker.model.half()

    logger.info("[INFO] Reranker loaded")
    yield

    del reranker
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

app = FastAPI(
    title="BGE-Reranker-v2-m3 Service",
    version="1.0.0",
    lifespan=lifespan,
)

# schemas
class RerankRequest(BaseModel):
    query: str 
    documents: list[str]
    top_n: int = 3
    return_documents: bool = True


class RankedDocument(BaseModel):
    index: int
    score: float
    document: str | None = None


class RerankResponse(BaseModel):
    results: list[RankedDocument]

# Endpoint
@app.get("/health")
def health():
    gpu_available = torch.cuda.is_available()
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "gpu": gpu_available,
    }

@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    if reranker is None:
        raise HTTPException(status_code=503, detail="Reranker not loaded")
    if not request.documents:
        raise HTTPException(status_code=400, detail="Documents cannot be empty")
    
    try:
        pairs = [[request.query, doc] for doc in request.documents]
        scores = reranker.predict(pairs, show_progress_bar=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reranking failed: {str(e)}")
    
    indexed_scores = sorted(
        enumerate(scores),
        key=lambda x: x[1],
        reverse=True,
    )[:request.top_n]

    results = [
        RankedDocument(
            index=idx,
            score=round(float(score), 4),
            document=request.documents[idx] if request.return_documents else None,
        )
        for idx, score in indexed_scores
    ]

    logger.info(
        f"Reranked {len(request.documents)} docs -> top {request.top_n} "
    )
    print(f"[INFO] Reranked {len(request.documents)} docs -> top {request.top_n}")

    return RerankResponse(results=results)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=False)