"""Module-level singleton holding initialized services."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from memory_mcp.core.config import MCPConfig
    from memory_mcp.providers.manager import ProviderManager
    from memory_mcp.services.audit import AuditService
    from memory_mcp.services.cache import CacheService
    from memory_mcp.services.memory import MemoryService


class ServiceRegistry:
    """Populated once during lifespan startup.  Tools import and call
    ``ServiceRegistry.get()`` to access services — no parameters needed.
    """

    _instance: ClassVar["ServiceRegistry | None"] = None

    def __init__(self) -> None:
        self.config: MCPConfig | None = None
        self.memory_service: MemoryService | None = None
        self.cache_service: CacheService | None = None
        self.audit_service: AuditService | None = None
        self.providers: ProviderManager | None = None
        self.governance_service = None
        self.rate_limiter = None
        self.prompt_library = None
        self.decision_service = None

    @classmethod
    def initialize(
        cls,
        config: MCPConfig,
        memory_service: MemoryService,
        cache_service: CacheService,
        audit_service: AuditService,
        providers: ProviderManager,
    ) -> "ServiceRegistry":
        instance = cls()
        instance.config = config
        instance.memory_service = memory_service
        instance.cache_service = cache_service
        instance.audit_service = audit_service
        instance.providers = providers
        cls._instance = instance
        return instance

    @classmethod
    def get(cls) -> "ServiceRegistry":
        if cls._instance is None:
            raise RuntimeError("ServiceRegistry not initialized.")
        return cls._instance
