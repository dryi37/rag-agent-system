import json
from datetime import datetime, timezone
from enum import Enum
from typing import AsyncGenerator

import redis.asyncio as aioredis

STREAM_TTL  = 1800   
STREAM_MAXLEN = 100  

KEY_STREAM = "stream:events:{thread_id}"
KEY_RESULT = "stream:result:{thread_id}"


class AgentEvent(str, Enum):
    STATUS = "processing"
    AGENT_THINKING = "agent_thinking"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_DONE = "tool_call_done"
    GENERATING = "generating"
    HALLUCINATION_CHECK = "hallucination_check"
    RETRYING = "retrying"
    CACHE_HIT = "cache_hit"
    DONE = "done"
    ERROR = "error"
    TOKEN = "token"


class EventPublisher:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def _publish(self, thread_id: str, event: AgentEvent, data: dict) -> None:
        key = KEY_STREAM.format(thread_id=thread_id)
        payload = {
            "type":      event.value,
            "data":      json.dumps(data, ensure_ascii=False),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.redis.xadd(key, payload, maxlen=STREAM_MAXLEN)
        await self.redis.expire(key, STREAM_TTL)

    async def status(self, thread_id: str) -> None:
        await self._publish(thread_id, AgentEvent.STATUS, {})

    async def agent_thinking(self, thread_id: str, query: str) -> None:
        preview = query[:50] + "..." if len(query) > 50 else query
        await self._publish(thread_id, AgentEvent.AGENT_THINKING, {"query_preview": preview})

    async def tool_started(self, thread_id: str, tool_name: str) -> None:
        await self._publish(thread_id, AgentEvent.TOOL_CALL_STARTED, {"tool": tool_name})

    async def tool_done(self, thread_id: str, tool_name: str) -> None:
        await self._publish(thread_id, AgentEvent.TOOL_CALL_DONE, {"tool": tool_name})

    async def generating(self, thread_id: str) -> None:
        await self._publish(thread_id, AgentEvent.GENERATING, {})

    async def token(self, thread_id: str, content: str) -> None:
        await self._publish(thread_id, AgentEvent.TOKEN, {"content": content})

    async def hallucination_check(self, thread_id: str) -> None:
        await self._publish(thread_id, AgentEvent.HALLUCINATION_CHECK, {})

    async def retrying(self, thread_id: str, iteration: int) -> None:
        await self._publish(thread_id, AgentEvent.RETRYING, {"iteration": iteration})

    async def error(self, thread_id: str, message: str) -> None:
        await self._publish(thread_id, AgentEvent.ERROR, {"message": message})

    async def done(self, thread_id: str, answer: str = "", sources: list = None, iterations: int = 0, from_cache: bool = False) -> None:
        result = {
            "answer":     answer,
            "sources":    sources or [],
            "iterations": iterations,
            "cache_hit":  from_cache,
        }
        key_result = KEY_RESULT.format(thread_id=thread_id)
        await self.redis.setex(key_result, STREAM_TTL, json.dumps(result, ensure_ascii=False))

        event = AgentEvent.CACHE_HIT if from_cache else AgentEvent.DONE
        await self._publish(thread_id, event, result)


class EventSubscriber:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def subscribe(self, thread_id: str, last_event_id: str = "0") -> AsyncGenerator[dict, None]:
        key = KEY_STREAM.format(thread_id=thread_id)
        last_id = last_event_id
        empty_polls = 0
        MAX_EMPTY_POLLS = 5

        while True:
            results = await self.redis.xread({key: last_id}, block=5000, count=10)

            if not results:
                empty_polls += 1
                if empty_polls >= MAX_EMPTY_POLLS:
                    break
                continue
            
            empty_polls = 0
            for _, messages in results:
                for msg_id, fields in messages:
                    # print(f"RAW FIELDS: {fields}")
                    last_id = msg_id
                    event_type = fields.get("type", "")
                    event = {
                        "id":        msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                        "type":      fields.get("type", ""),
                        "data":      json.loads(fields.get("data", "{}")),
                        "timestamp": fields.get("timestamp", ""),
                    }
                    yield event

                    if event_type in (AgentEvent.DONE.value, AgentEvent.CACHE_HIT.value, AgentEvent.ERROR.value):
                        return

    async def get_result(self, thread_id: str) -> dict | None:
        key = KEY_RESULT.format(thread_id=thread_id)
        data = await self.redis.get(key)
        return json.loads(data) if data else None