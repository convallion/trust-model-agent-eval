"""Proxy CLI commands for local LLM tracing."""

import asyncio
import signal
from typing import Optional

import click
from rich.console import Console

from trustmodel.core.config import configure

console = Console()


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

        async def health_handler(request: web.Request) -> web.Response:
            return web.json_response({"status": "ok", "agent": agent})

        async def anthropic_handler(request: web.Request) -> web.Response:
            # Proxy to Anthropic API with tracing
            return web.json_response({"message": "Anthropic proxy not fully implemented"})

        async def openai_handler(request: web.Request) -> web.Response:
            # Proxy to OpenAI API with tracing
            return web.json_response({"message": "OpenAI proxy not fully implemented"})

        app = web.Application()
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
