import os
import json
import hashlib
import numpy as np
from typing import Optional
from datetime import timedelta

import redis.asyncio as aioredis
from langchain_google_genai import GoogleGenerativeAIEmbeddings

DEFAULT_TTL = int(os.getenv("CACHE_TTL_SECOND", 3600))
SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", 0.92))

KEY_EMBEDDING = "cache:emb:"
KEY_ANSWER = "cache:ans:"
KEY_META = "cache:meta:"
KEY_INDEX = "cache:index"

class SemanticCache:
    def __init__(self, redis_client: aioredis.Redis, embeddings: GoogleGenerativeAIEmbeddings):
        self.redis = redis_client
        self.embeddings = embeddings

    def _query_key(self, query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()[:16]
    
    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        a, b = np.array(a), np.array(b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        if norm == 0:
            return 0.0
        return float(np.dot(a, b) / norm)
    
    async def get(self, query: str) -> Optional[dict]:
        query_embedding = await self.embeddings.aembed_query(query)

        cached_keys = await self.redis.smembers(KEY_INDEX)
        if not cached_keys:
            return None
        
        best_similarity = 0.0
        best_key = None
        for key in cached_keys:
            key = key.decode() if isinstance(key, bytes) else key
            emb_data = await self.redis.get(KEY_EMBEDDING + key)
            if not emb_data:
                await self.redis.srem(KEY_INDEX, key)
                continue

            cached_embedding = json.loads(emb_data)
            similarity_score = self._cosine_similarity(query_embedding, cached_embedding)
            if similarity_score > best_similarity:
                best_similarity = similarity_score
                best_key = key

        if best_similarity < SIMILARITY_THRESHOLD or best_key is None:
            return None
        
        answer_data = await self.redis.get(KEY_ANSWER + best_key)
        if not answer_data:
            return None
        
        result = json.loads(answer_data)
        result["cache_hit"] = True
        result["similarity_score"] = round(best_similarity, 4)
        return result
    
    async def set(self, query: str, answer: str, metadata: dict = None) -> None:
        key = self._query_key(query)
        query_embedding = await self.embeddings.aembed_query(query)
        await self.redis.setex(
            KEY_EMBEDDING + key,
            DEFAULT_TTL,
            json.dumps(query_embedding)
        )

        cache_entry = {
            "answer": answer,
            "query": query,
            **(metadata or {}),
            "cache_hit": False,
        }
        await self.redis.setex(
            KEY_ANSWER + key,
            DEFAULT_TTL,
            json.dumps(cache_entry)
        )

        await self.redis.sadd(KEY_INDEX, key)

    async def invalidate(self, query: str) -> None:
        key = self._query_key(query)
        await self.redis.delete(KEY_EMBEDDING + key, KEY_ANSWER + key)
        await self.redis.srem(KEY_INDEX, key)

    async def clear_all(self) -> None:
        keys = await self.redis.smembers(KEY_INDEX)
        for key in keys:
            key = key.decode() if isinstance(key, bytes) else key
            await self.redis.delete(KEY_EMBEDDING + key, KEY_ANSWER + key)
        await self.redis.delete(KEY_INDEX)