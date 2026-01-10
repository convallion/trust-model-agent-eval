"""Evaluation CLI commands."""

import asyncio
from typing import List, Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from trustmodel.api.client import TrustModelClient
from trustmodel.core.config import configure
from trustmodel.evaluate.client import EvaluationClient

console = Console()


@click.group()
def evaluate() -> None:
    """Run and manage evaluations."""
    pass


@evaluate.command("run")
@click.argument("agent")
@click.option(
    "--suite", "-s",
    "suites",
    multiple=True,
    type=click.Choice(["capability", "safety", "reliability", "communication"]),
    help="Suites to run (can specify multiple)",
)
@click.option("--wait/--no-wait", default=True, help="Wait for completion")
@click.option("--timeout", "-t", default=600, help="Timeout in seconds")
@click.pass_context
def run_evaluation(
    ctx: click.Context,
    agent: str,
    suites: tuple,
    wait: bool,
    timeout: int,
) -> None:
    """Run an evaluation on an agent."""
    async def _run() -> None:
        from uuid import UUID
        from trustmodel.models.evaluation import EvaluationSuite, EvaluationStatus

        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()
        eval_client = EvaluationClient(client)

        try:
            # Resolve agent ID
            try:
                agent_id = UUID(agent)
            except ValueError:
                agents = await client.list_agents()
                agent_id = None
                for a in agents.get("items", []):
                    if a["name"] == agent:
                        agent_id = UUID(a["id"])
                        break
                if not agent_id:
                    console.print(f"[red]Agent not found:[/red] {agent}")
                    raise click.Abort()

            # Determine suites
            suite_list = list(suites) if suites else ["capability", "safety", "reliability", "communication"]

            console.print(f"Starting evaluation for agent: [cyan]{agent}[/cyan]")
            console.print(f"Suites: {', '.join(suite_list)}")

            # Start evaluation
            evaluation = await eval_client.start(
                agent_id=agent_id,
                suites=[EvaluationSuite(s) for s in suite_list],
            )

            console.print(f"Evaluation ID: {evaluation.id}")

            if wait:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Running evaluation...", total=None)

                    evaluation = await eval_client.wait_for_completion(
                        evaluation.id,
                        timeout=timeout,
                    )

                    progress.update(task, completed=True)

                # Display results
                console.print(f"\n[bold green]Evaluation Complete![/bold green]")
                console.print(f"Grade: [bold]{evaluation.grade}[/bold]")

                if evaluation.scores:
                    console.print(f"\n[bold]Scores:[/bold]")
                    console.print(f"  Overall: {evaluation.scores.overall:.1f}")
                    if evaluation.scores.capability is not None:
                        console.print(f"  Capability: {evaluation.scores.capability:.1f}")
                    if evaluation.scores.safety is not None:
                        console.print(f"  Safety: {evaluation.scores.safety:.1f}")
                    if evaluation.scores.reliability is not None:
                        console.print(f"  Reliability: {evaluation.scores.reliability:.1f}")
                    if evaluation.scores.communication is not None:
                        console.print(f"  Communication: {evaluation.scores.communication:.1f}")

                if evaluation.certified_capabilities:
                    console.print(f"\n[bold]Certified Capabilities:[/bold]")
                    for cap in evaluation.certified_capabilities:
                        console.print(f"  [green]✓[/green] {cap}")

                if evaluation.not_certified:
                    console.print(f"\n[bold]Not Certified:[/bold]")
                    for cap in evaluation.not_certified:
                        console.print(f"  [red]✗[/red] {cap}")

                if evaluation.is_certifiable:
                    console.print(f"\n[green]Agent is eligible for certification![/green]")
                else:
                    console.print(f"\n[yellow]Agent does not meet certification requirements.[/yellow]")

            else:
                console.print(f"Evaluation started. Check status with: trustmodel evaluate status {evaluation.id}")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_run())


@evaluate.command("status")
@click.argument("evaluation_id")
@click.pass_context
def get_status(ctx: click.Context, evaluation_id: str) -> None:
    """Get evaluation status."""
    async def _status() -> None:
        from uuid import UUID

        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()
        eval_client = EvaluationClient(client)

        try:
            evaluation = await eval_client.get(UUID(evaluation_id))

            console.print(f"[bold]Evaluation Status[/bold]")
            console.print(f"  ID: {evaluation.id}")
            console.print(f"  Status: {evaluation.status.value}")
            console.print(f"  Started: {evaluation.started_at}")

            if evaluation.completed_at:
                console.print(f"  Completed: {evaluation.completed_at}")
                console.print(f"  Grade: {evaluation.grade}")

            if evaluation.error_message:
                console.print(f"  Error: [red]{evaluation.error_message}[/red]")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_status())


@evaluate.command("list")
@click.option("--agent", "-a", help="Filter by agent name or ID")
@click.option("--status", "-s", type=click.Choice(["pending", "running", "completed", "failed", "cancelled"]))
@click.option("--page", "-p", default=1, help="Page number")
@click.option("--limit", "-l", default=20, help="Results per page")
@click.pass_context
def list_evaluations(
    ctx: click.Context,
    agent: Optional[str],
    status: Optional[str],
    page: int,
    limit: int,
) -> None:
    """List evaluations."""
    async def _list() -> None:
        from uuid import UUID
        from trustmodel.models.evaluation import EvaluationStatus

        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()
        eval_client = EvaluationClient(client)

        try:
            # Resolve agent ID if provided
            agent_id = None
            if agent:
                try:
                    agent_id = UUID(agent)
                except ValueError:
                    agents = await client.list_agents()
                    for a in agents.get("items", []):
                        if a["name"] == agent:
                            agent_id = UUID(a["id"])
                            break

            status_enum = EvaluationStatus(status) if status else None

            evaluations, total = await eval_client.list(
                agent_id=agent_id,
                status=status_enum,
                page=page,
                page_size=limit,
            )

            table = Table(title="Evaluations")
            table.add_column("ID", style="dim")
            table.add_column("Agent")
            table.add_column("Status")
            table.add_column("Grade")
            table.add_column("Score")
            table.add_column("Started")

            for eval in evaluations:
                score = f"{eval.scores.overall:.1f}" if eval.scores else "-"
                table.add_row(
                    str(eval.id)[:8] + "...",
                    str(eval.agent_id)[:8] + "...",
                    eval.status.value,
                    eval.grade or "-",
                    score,
                    str(eval.started_at)[:10],
                )

            console.print(table)
            console.print(f"\nTotal: {total} evaluations")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_list())
