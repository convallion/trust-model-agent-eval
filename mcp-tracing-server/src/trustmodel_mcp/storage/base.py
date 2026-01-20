"""Base storage interface."""

from abc import ABC, abstractmethod
from typing import List, Optional

from trustmodel_mcp.models import Trace


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage (create tables, etc.)."""
        pass

    @abstractmethod
    async def save_trace(self, trace: Trace) -> None:
        """Save or update a trace."""
        pass

    @abstractmethod
    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID."""
        pass

    @abstractmethod
    async def get_trace_by_thread(self, thread_id: str) -> Optional[Trace]:
        """Get a trace by thread ID."""
        pass

    @abstractmethod
    async def list_traces(
        self,
        agent_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[Trace]:
        """List traces with optional filters."""
        pass

    @abstractmethod
    async def count_traces(
        self,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """Count traces matching filters."""
        pass

    @abstractmethod
    async def delete_trace(self, trace_id: str) -> bool:
        """Delete a trace. Returns True if deleted."""
        pass

    async def close(self) -> None:
        """Close the storage connection."""
        pass
