"""Main CLI entry point."""

import asyncio
from functools import wraps
from typing import Any, Callable

import click
from rich.console import Console

from trustmodel.version import __version__

console = Console()


def async_command(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to run async functions in Click commands."""
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@click.group()
@click.version_option(__version__, prog_name="trustmodel")
@click.option(
    "--api-key",
    envvar="TRUSTMODEL_API_KEY",
    help="TrustModel API key",
)
@click.option(
    "--server",
    envvar="TRUSTMODEL_SERVER_URL",
    default="https://api.trustmodel.dev",
    help="TrustModel server URL",
)
@click.pass_context
def cli(ctx: click.Context, api_key: str, server: str) -> None:
    """TrustModel CLI - Trust infrastructure for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key
    ctx.obj["server"] = server


# Import and register command groups
from trustmodel.cli.commands.agent import agent
from trustmodel.cli.commands.evaluate import evaluate
from trustmodel.cli.commands.cert import cert
from trustmodel.cli.commands.proxy import proxy

cli.add_command(agent)
cli.add_command(evaluate)
cli.add_command(cert)
cli.add_command(proxy)


if __name__ == "__main__":
    cli()
