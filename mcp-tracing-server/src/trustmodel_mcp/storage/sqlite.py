"""SQLite storage backend for traces."""

import json
import os
from pathlib import Path
from typing import List, Optional

import aiosqlite

from trustmodel_mcp.models import Trace
from trustmodel_mcp.storage.base import StorageBackend


class SQLiteStorage(StorageBackend):
    """SQLite-based storage for traces.

    Default location: ~/.trustmodel/traces.db
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Default to ~/.trustmodel/traces.db
            home = Path.home()
            db_dir = home / ".trustmodel"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(db_dir / "traces.db")

        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
        return self._connection

    async def initialize(self) -> None:
        """Create tables if they don't exist."""
        conn = await self._get_connection()

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                messages TEXT NOT NULL DEFAULT '[]',
                total_tokens INTEGER DEFAULT 0,
                total_input_tokens INTEGER DEFAULT 0,
                total_output_tokens INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0,
                latency_ms REAL DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                provider TEXT,
                model TEXT
            )
        """)

        # Create indexes for common queries
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_agent_id ON traces(agent_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_thread_id ON traces(thread_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status)
        """)

        await conn.commit()

    async def save_trace(self, trace: Trace) -> None:
        """Save or update a trace."""
        conn = await self._get_connection()

        # Serialize messages and metadata to JSON
        messages_json = json.dumps([m.to_dict() for m in trace.messages])
        metadata_json = json.dumps(trace.metadata)

        await conn.execute("""
            INSERT INTO traces (
                id, thread_id, agent_id, created_at, updated_at, status,
                messages, total_tokens, total_input_tokens, total_output_tokens,
                tool_call_count, latency_ms, metadata, provider, model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                updated_at = excluded.updated_at,
                status = excluded.status,
                messages = excluded.messages,
                total_tokens = excluded.total_tokens,
                total_input_tokens = excluded.total_input_tokens,
                total_output_tokens = excluded.total_output_tokens,
                tool_call_count = excluded.tool_call_count,
                latency_ms = excluded.latency_ms,
                metadata = excluded.metadata,
                provider = excluded.provider,
                model = excluded.model
        """, (
            trace.id,
            trace.thread_id,
            trace.agent_id,
            trace.created_at.isoformat(),
            trace.updated_at.isoformat(),
            trace.status.value,
            messages_json,
            trace.total_tokens,
            trace.total_input_tokens,
            trace.total_output_tokens,
            trace.tool_call_count,
            trace.latency_ms,
            metadata_json,
            trace.provider,
            trace.model,
        ))

        await conn.commit()

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID."""
        conn = await self._get_connection()

        async with conn.execute(
            "SELECT * FROM traces WHERE id = ?",
            (trace_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_trace(row)
            return None

    async def get_trace_by_thread(self, thread_id: str) -> Optional[Trace]:
        """Get the most recent trace for a thread."""
        conn = await self._get_connection()

        async with conn.execute(
            "SELECT * FROM traces WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1",
            (thread_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_trace(row)
            return None

    async def list_traces(
        self,
        agent_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[Trace]:
        """List traces with optional filters."""
        conn = await self._get_connection()

        query = "SELECT * FROM traces WHERE 1=1"
        params: List = []

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        traces = []
        async with conn.execute(query, params) as cursor:
            async for row in cursor:
                traces.append(self._row_to_trace(row))

        return traces

    async def count_traces(
        self,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """Count traces matching filters."""
        conn = await self._get_connection()

        query = "SELECT COUNT(*) FROM traces WHERE 1=1"
        params: List = []

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        async with conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def delete_trace(self, trace_id: str) -> bool:
        """Delete a trace."""
        conn = await self._get_connection()

        cursor = await conn.execute(
            "DELETE FROM traces WHERE id = ?",
            (trace_id,)
        )
        await conn.commit()

        return cursor.rowcount > 0

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    def _row_to_trace(self, row: aiosqlite.Row) -> Trace:
        """Convert a database row to a Trace object."""
        messages_data = json.loads(row["messages"])
        metadata = json.loads(row["metadata"])

        trace_dict = {
            "id": row["id"],
            "thread_id": row["thread_id"],
            "agent_id": row["agent_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "status": row["status"],
            "messages": messages_data,
            "total_tokens": row["total_tokens"],
            "total_input_tokens": row["total_input_tokens"],
            "total_output_tokens": row["total_output_tokens"],
            "tool_call_count": row["tool_call_count"],
            "latency_ms": row["latency_ms"],
            "metadata": metadata,
            "provider": row["provider"],
            "model": row["model"],
        }

        return Trace.from_dict(trace_dict)
