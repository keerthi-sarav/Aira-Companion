from typing import Protocol


class KnowledgeProvider(Protocol):
    async def get_context(self, tenant_id: str, message: str, tag_id: str | None) -> str: ...


class NullKnowledge:
    """Stub until the real Anril knowledge base is wired. campaign_tag_id = knowledge_tag_id."""

    async def get_context(self, tenant_id: str, message: str, tag_id: str | None) -> str:
        return ""


knowledge_provider: KnowledgeProvider = NullKnowledge()
