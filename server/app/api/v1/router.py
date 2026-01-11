"""Main V1 API router."""

from fastapi import APIRouter

from app.api.v1 import agents, certificates, chat, evaluations, registry, sessions, stats, terminal, trace_ingest, trace_stream, traces

api_router = APIRouter()

api_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
api_router.include_router(traces.router, prefix="/traces", tags=["Traces"])
api_router.include_router(evaluations.router, prefix="/evaluations", tags=["Evaluations"])
api_router.include_router(certificates.router, prefix="/certificates", tags=["Certificates"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
api_router.include_router(registry.router, prefix="/registry", tags=["Registry"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(stats.router, prefix="/stats", tags=["Stats"])
api_router.include_router(terminal.router, prefix="/terminal", tags=["Terminal"])
api_router.include_router(trace_ingest.router, prefix="/traces", tags=["Trace Ingestion"])
api_router.include_router(trace_stream.router, prefix="/traces", tags=["Trace Stream"])
