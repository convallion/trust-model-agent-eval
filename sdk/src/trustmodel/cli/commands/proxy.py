"""Proxy CLI commands for local LLM tracing."""

import asyncio
import json
import os
import signal
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import click
import httpx
from rich.console import Console

from trustmodel.core.config import configure, get_config

console = Console()

# Real API base URLs
ANTHROPIC_API_URL = "https://api.anthropic.com"
OPENAI_API_URL = "https://api.openai.com"


@click.group()
def proxy() -> None:
    """Run local LLM proxy for automatic tracing."""
    pass


@proxy.command("start")
@click.option("--port", "-p", default=8080, help="Port to run proxy on")
@click.option("--agent", "-a", required=True, help="Agent name or ID")
@click.option("--provider", type=click.Choice(["anthropic", "openai", "all"]), default="all")
@click.pass_context
def start_proxy(
    ctx: click.Context,
    port: int,
    agent: str,
    provider: str,
) -> None:
    """Start local proxy server for automatic LLM tracing."""
    console.print(f"Starting TrustModel proxy on port {port}...")
    console.print(f"Agent: {agent}")
    console.print(f"Provider: {provider}")

    configure(
        api_key=ctx.obj.get("api_key"),
        server_url=ctx.obj.get("server"),
        agent_name=agent,
        proxy_enabled=True,
        proxy_port=port,
    )

    # This would start a local HTTP proxy server
    # that intercepts LLM API calls and traces them

    console.print(f"\n[green]Proxy started![/green]")
    console.print(f"\nTo use the proxy, set these environment variables:")

    if provider in ["anthropic", "all"]:
        console.print(f"  export ANTHROPIC_BASE_URL=http://localhost:{port}/anthropic")

    if provider in ["openai", "all"]:
        console.print(f"  export OPENAI_BASE_URL=http://localhost:{port}/openai")

    console.print(f"\nPress Ctrl+C to stop the proxy.")

    async def run_proxy() -> None:
        from aiohttp import web

        config = get_config()
        http_client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout for LLM calls

        async def send_trace_to_server(trace_data: dict) -> None:
            """Send trace data to TrustModel server."""
            try:
                headers = {"Authorization": f"Bearer {config.api_key}"}
                await http_client.post(
                    f"{config.server_url}/v1/traces",
                    json=trace_data,
                    headers=headers,
                )
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to send trace: {e}[/yellow]")

        async def health_handler(request: web.Request) -> web.Response:
            return web.json_response({"status": "ok", "agent": agent})

        async def anthropic_handler(request: web.Request) -> web.Response:
            """Forward requests to Anthropic API with tracing."""
            path = request.match_info.get("path", "")
            target_url = f"{ANTHROPIC_API_URL}/{path}"

            # Read request body
            body = await request.read()
            request_data = json.loads(body) if body else {}

            # Copy headers, removing host
            headers = {k: v for k, v in request.headers.items()
                      if k.lower() not in ["host", "content-length"]}

            # Get API key from request or environment
            if "x-api-key" not in headers and "X-API-Key" not in headers:
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if api_key:
                    headers["x-api-key"] = api_key

            # Start trace
            trace_id = str(uuid4())
            span_id = str(uuid4())
            started_at = datetime.now(timezone.utc)

            console.print(f"[cyan]→ Anthropic: {request.method} /{path}[/cyan]")

            try:
                # Forward request to Anthropic
                response = await http_client.request(
                    method=request.method,
                    url=target_url,
                    content=body,
                    headers=headers,
                )

                response_body = response.content
                ended_at = datetime.now(timezone.utc)

                # Parse response for trace metadata
                response_data = {}
                try:
                    response_data = json.loads(response_body)
                except:
                    pass

                # Extract model and usage info
                model = request_data.get("model", response_data.get("model", "unknown"))
                usage = response_data.get("usage", {})

                console.print(f"[green]← Anthropic: {response.status_code} ({model})[/green]")

                # Build trace data
                trace_data = {
                    "agent_id": agent,
                    "traces": [{
                        "trace_id": trace_id,
                        "name": f"anthropic.{path.replace('/', '.')}",
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "metadata": {"provider": "anthropic", "model": model},
                        "spans": [{
                            "span_id": span_id,
                            "trace_id": trace_id,
                            "name": f"llm.{path}",
                            "span_type": "llm_call",
                            "started_at": started_at.isoformat(),
                            "ended_at": ended_at.isoformat(),
                            "status": "ok" if response.status_code == 200 else "error",
                            "attributes": {
                                "provider": "anthropic",
                                "model": model,
                                "endpoint": path,
                                "status_code": response.status_code,
                                "input_tokens": usage.get("input_tokens"),
                                "output_tokens": usage.get("output_tokens"),
                                "request_messages": len(request_data.get("messages", [])),
                            }
                        }]
                    }]
                }

                # Send trace async (don't block response)
                asyncio.create_task(send_trace_to_server(trace_data))

                # Return response to client
                resp_headers = {k: v for k, v in response.headers.items()
                               if k.lower() not in ["content-encoding", "transfer-encoding", "content-length", "content-type"]}
                return web.Response(
                    body=response_body,
                    status=response.status_code,
                    headers=resp_headers,
                    content_type=response.headers.get("content-type", "application/json"),
                )

            except Exception as e:
                console.print(f"[red]✗ Anthropic error: {e}[/red]")
                return web.json_response(
                    {"error": {"type": "proxy_error", "message": str(e)}},
                    status=502
                )

        async def openai_handler(request: web.Request) -> web.Response:
            """Forward requests to OpenAI API with tracing."""
            path = request.match_info.get("path", "")
            target_url = f"{OPENAI_API_URL}/{path}"

            # Read request body
            body = await request.read()
            request_data = json.loads(body) if body else {}

            # Copy headers, removing host
            headers = {k: v for k, v in request.headers.items()
                      if k.lower() not in ["host", "content-length"]}

            # Get API key from request or environment
            auth_header = headers.get("authorization", headers.get("Authorization", ""))
            if not auth_header:
                api_key = os.environ.get("OPENAI_API_KEY")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

            # Start trace
            trace_id = str(uuid4())
            span_id = str(uuid4())
            started_at = datetime.now(timezone.utc)

            console.print(f"[cyan]→ OpenAI: {request.method} /{path}[/cyan]")

            try:
                # Forward request to OpenAI
                response = await http_client.request(
                    method=request.method,
                    url=target_url,
                    content=body,
                    headers=headers,
                )

                response_body = response.content
                ended_at = datetime.now(timezone.utc)

                # Parse response for trace metadata
                response_data = {}
                try:
                    response_data = json.loads(response_body)
                except:
                    pass

                # Extract model and usage info
                model = request_data.get("model", response_data.get("model", "unknown"))
                usage = response_data.get("usage", {})

                console.print(f"[green]← OpenAI: {response.status_code} ({model})[/green]")

                # Build trace data
                trace_data = {
                    "agent_id": agent,
                    "traces": [{
                        "trace_id": trace_id,
                        "name": f"openai.{path.replace('/', '.')}",
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "metadata": {"provider": "openai", "model": model},
                        "spans": [{
                            "span_id": span_id,
                            "trace_id": trace_id,
                            "name": f"llm.{path}",
                            "span_type": "llm_call",
                            "started_at": started_at.isoformat(),
                            "ended_at": ended_at.isoformat(),
                            "status": "ok" if response.status_code == 200 else "error",
                            "attributes": {
                                "provider": "openai",
                                "model": model,
                                "endpoint": path,
                                "status_code": response.status_code,
                                "prompt_tokens": usage.get("prompt_tokens"),
                                "completion_tokens": usage.get("completion_tokens"),
                                "total_tokens": usage.get("total_tokens"),
                            }
                        }]
                    }]
                }

                # Send trace async (don't block response)
                asyncio.create_task(send_trace_to_server(trace_data))

                # Return response to client
                resp_headers = {k: v for k, v in response.headers.items()
                               if k.lower() not in ["content-encoding", "transfer-encoding", "content-length", "content-type"]}
                return web.Response(
                    body=response_body,
                    status=response.status_code,
                    headers=resp_headers,
                    content_type=response.headers.get("content-type", "application/json"),
                )

            except Exception as e:
                console.print(f"[red]✗ OpenAI error: {e}[/red]")
                return web.json_response(
                    {"error": {"type": "proxy_error", "message": str(e)}},
                    status=502
                )

        app = web.Application(client_max_size=50 * 1024 * 1024)  # 50MB max request size
        app.router.add_get("/health", health_handler)
        app.router.add_route("*", "/anthropic/{path:.*}", anthropic_handler)
        app.router.add_route("*", "/openai/{path:.*}", openai_handler)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "localhost", port)
        await site.start()

        console.print(f"[green]Proxy running on http://localhost:{port}[/green]")

        # Wait for interrupt
        stop_event = asyncio.Event()

        def signal_handler() -> None:
            stop_event.set()

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

        await stop_event.wait()

        console.print("\n[yellow]Stopping proxy...[/yellow]")
        await runner.cleanup()

    try:
        asyncio.run(run_proxy())
    except KeyboardInterrupt:
        pass

    console.print("[green]Proxy stopped.[/green]")


@proxy.command("status")
@click.option("--port", "-p", default=8080, help="Port to check")
def proxy_status(port: int) -> None:
    """Check if proxy is running."""
    import httpx

    try:
        response = httpx.get(f"http://localhost:{port}/health", timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            console.print(f"[green]Proxy is running[/green]")
            console.print(f"  Agent: {data.get('agent')}")
        else:
            console.print(f"[yellow]Proxy responded with status {response.status_code}[/yellow]")
    except httpx.ConnectError:
        console.print(f"[red]Proxy is not running on port {port}[/red]")
    except Exception as e:
        console.print(f"[red]Error checking proxy:[/red] {e}")
