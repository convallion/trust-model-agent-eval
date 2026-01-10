"""Agent management CLI commands."""

import asyncio
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from trustmodel.api.client import TrustModelClient
from trustmodel.core.config import configure

console = Console()


@click.group()
def agent() -> None:
    """Manage agents."""
    pass


@agent.command("register")
@click.option("--name", "-n", required=True, help="Agent name")
@click.option(
    "--type",
    "-t",
    "agent_type",
    default="custom",
    type=click.Choice(["coding", "research", "assistant", "orchestrator", "specialist", "custom"]),
    help="Agent type",
)
@click.option("--framework", "-f", help="Framework used (e.g., langchain, autogen)")
@click.option("--description", "-d", help="Agent description")
@click.option("--version", "-v", "agent_version", help="Agent version")
@click.pass_context
def register(
    ctx: click.Context,
    name: str,
    agent_type: str,
    framework: Optional[str],
    description: Optional[str],
    agent_version: Optional[str],
) -> None:
    """Register a new agent."""
    async def _register() -> None:
        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()

        try:
            data = {
                "name": name,
                "agent_type": agent_type,
            }
            if framework:
                data["framework"] = framework
            if description:
                data["description"] = description
            if agent_version:
                data["version"] = agent_version

            result = await client.register_agent(data)

            console.print(f"[green]Agent registered successfully![/green]")
            console.print(f"  ID: {result['id']}")
            console.print(f"  Name: {result['name']}")
            console.print(f"  Type: {result['agent_type']}")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_register())


@agent.command("list")
@click.option("--status", "-s", type=click.Choice(["active", "inactive", "suspended"]))
@click.option("--page", "-p", default=1, help="Page number")
@click.option("--limit", "-l", default=20, help="Results per page")
@click.pass_context
def list_agents(
    ctx: click.Context,
    status: Optional[str],
    page: int,
    limit: int,
) -> None:
    """List registered agents."""
    async def _list() -> None:
        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()

        try:
            result = await client.list_agents(page=page, page_size=limit, status=status)

            table = Table(title="Registered Agents")
            table.add_column("ID", style="dim")
            table.add_column("Name", style="cyan")
            table.add_column("Type")
            table.add_column("Status")
            table.add_column("Framework")
            table.add_column("Created")

            for agent in result.get("items", []):
                table.add_row(
                    agent["id"][:8] + "...",
                    agent["name"],
                    agent["agent_type"],
                    agent["status"],
                    agent.get("framework") or "-",
                    agent["created_at"][:10],
                )

            console.print(table)
            console.print(f"\nTotal: {result.get('total', 0)} agents")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_list())


@agent.command("get")
@click.argument("agent_id")
@click.pass_context
def get_agent(ctx: click.Context, agent_id: str) -> None:
    """Get agent details."""
    async def _get() -> None:
        from uuid import UUID

        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()

        try:
            result = await client.get_agent(UUID(agent_id))

            console.print(f"[bold]Agent Details[/bold]")
            console.print(f"  ID: {result['id']}")
            console.print(f"  Name: {result['name']}")
            console.print(f"  Type: {result['agent_type']}")
            console.print(f"  Status: {result['status']}")
            console.print(f"  Framework: {result.get('framework') or 'N/A'}")
            console.print(f"  Description: {result.get('description') or 'N/A'}")
            console.print(f"  Version: {result.get('version') or 'N/A'}")
            console.print(f"  Created: {result['created_at']}")

            if result.get("stats"):
                stats = result["stats"]
                console.print(f"\n[bold]Statistics[/bold]")
                console.print(f"  Total Traces: {stats.get('total_traces', 0)}")
                console.print(f"  Total Evaluations: {stats.get('total_evaluations', 0)}")
                if stats.get("latest_certificate_grade"):
                    console.print(f"  Latest Grade: {stats['latest_certificate_grade']}")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_get())


@agent.command("delete")
@click.argument("agent_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete_agent(ctx: click.Context, agent_id: str, force: bool) -> None:
    """Delete an agent."""
    if not force:
        if not click.confirm(f"Are you sure you want to delete agent {agent_id}?"):
            raise click.Abort()

    async def _delete() -> None:
        from uuid import UUID

        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()

        try:
            await client.delete_agent(UUID(agent_id))
            console.print(f"[green]Agent deleted successfully![/green]")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_delete())
