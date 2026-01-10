"""Trace exporters for sending data to TrustModel server."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Deque, Optional
from uuid import UUID

from trustmodel.core.logging import get_logger
from trustmodel.models.trace import TraceCreate

if TYPE_CHECKING:
    from trustmodel.api.client import TrustModelClient

logger = get_logger(__name__)


class BatchTraceExporter:
    """Batches traces and exports them to the TrustModel server."""

    def __init__(
        self,
        client: "TrustModelClient",
        agent_id: UUID,
        batch_size: int = 100,
        export_interval: float = 5.0,
        max_queue_size: int = 10000,
    ) -> None:
        self.client = client
        self.agent_id = agent_id
        self.batch_size = batch_size
        self.export_interval = export_interval
        self.max_queue_size = max_queue_size

        self._queue: Deque[TraceCreate] = deque(maxlen=max_queue_size)
        self._export_task: Optional[asyncio.Task[None]] = None
        self._shutdown_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._active = True
        self._stats = {
            "traces_queued": 0,
            "traces_exported": 0,
            "traces_dropped": 0,
            "export_errors": 0,
        }

    def add_trace(self, trace: TraceCreate) -> None:
        """Add a trace to the export queue."""
        if not self._active:
            return

        if len(self._queue) >= self.max_queue_size:
            self._stats["traces_dropped"] += 1
            logger.warning("Trace queue full, dropping trace", trace_id=str(trace.trace_id))
            return

        self._queue.append(trace)
        self._stats["traces_queued"] += 1

        # Start export task if not running
        if self._export_task is None or self._export_task.done():
            self._start_export_loop()

    def _start_export_loop(self) -> None:
        """Start the background export loop."""
        try:
            loop = asyncio.get_running_loop()
            self._export_task = loop.create_task(self._export_loop())
        except RuntimeError:
            # No running event loop, will export on flush
            pass

    async def _export_loop(self) -> None:
        """Background loop for periodic exports."""
        while self._active and not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.export_interval,
                )
            except asyncio.TimeoutError:
                pass

            if self._queue:
                await self._export_batch()

    async def _export_batch(self) -> None:
        """Export a batch of traces."""
        if not self._queue:
            return

        async with self._lock:
            # Collect batch
            batch: list[TraceCreate] = []
            while self._queue and len(batch) < self.batch_size:
                batch.append(self._queue.popleft())

            if not batch:
                return

            # Convert to API format
            traces_data = []
            for trace in batch:
                trace_dict = {
                    "trace_id": str(trace.trace_id),
                    "session_id": str(trace.session_id) if trace.session_id else None,
                    "started_at": trace.started_at.isoformat(),
                    "ended_at": trace.ended_at.isoformat() if trace.ended_at else None,
                    "metadata": trace.metadata,
                    "spans": [
                        {
                            "span_id": str(span.span_id),
                            "parent_span_id": str(span.parent_span_id) if span.parent_span_id else None,
                            "span_type": span.span_type.value,
                            "name": span.name,
                            "started_at": span.started_at.isoformat(),
                            "ended_at": span.ended_at.isoformat() if span.ended_at else None,
                            "status": span.status.value,
                            "attributes": span.attributes,
                            "model": span.model,
                            "input_tokens": span.input_tokens,
                            "output_tokens": span.output_tokens,
                            "prompt": span.prompt,
                            "response": span.response,
                            "tool_name": span.tool_name,
                            "tool_input": span.tool_input,
                            "tool_output": span.tool_output,
                            "error_message": span.error_message,
                            "error_type": span.error_type,
                        }
                        for span in trace.spans
                    ],
                }
                traces_data.append(trace_dict)

            try:
                result = await self.client.ingest_traces({
                    "agent_id": str(self.agent_id),
                    "traces": traces_data,
                })
                self._stats["traces_exported"] += result.get("accepted", len(batch))
                logger.debug(
                    "Exported traces",
                    count=result.get("accepted", len(batch)),
                )
            except Exception as e:
                self._stats["export_errors"] += 1
                logger.error(f"Failed to export traces: {e}")
                # Re-queue failed traces (at the front)
                for trace in reversed(batch):
                    self._queue.appendleft(trace)

    async def flush(self) -> None:
        """Flush all pending traces."""
        logger.debug("Flushing traces", queue_size=len(self._queue))
        while self._queue:
            await self._export_batch()

    async def shutdown(self) -> None:
        """Shutdown the exporter."""
        self._active = False
        self._shutdown_event.set()

        if self._export_task:
            self._export_task.cancel()
            try:
                await self._export_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self.flush()

        logger.info(
            "Exporter shutdown",
            stats=self._stats,
        )

    def get_stats(self) -> dict[str, int]:
        """Get export statistics."""
        return self._stats.copy()
