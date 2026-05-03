from typing import Optional
from langchain_core.runnables import RunnableConfig

def _get_publisher(config: RunnableConfig) -> Optional[object]:
    return config.get("configurable", {}).get("publisher")


async def _publish(config: RunnableConfig, event_fn) -> None:
    try:
        publisher = _get_publisher(config)
        if publisher:
            await event_fn(publisher)
    except Exception:
        pass
