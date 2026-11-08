from typing import Protocol


class MemoryProvider(Protocol):
    async def context_for(self, companion_id: str, end_user_id: str, message: str) -> str: ...

    async def forget(self, end_user_id: str) -> None: ...


class Level1History:
    """Level 1: no long-term memory. Mem0 (Level 2) arrives in week 2."""

    async def context_for(self, companion_id: str, end_user_id: str, message: str) -> str:
        return ""

    async def forget(self, end_user_id: str) -> None:
        return None


memory_provider: MemoryProvider = Level1History()
