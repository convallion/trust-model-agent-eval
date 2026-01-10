"""Certificate CLI commands."""

import asyncio
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trustmodel.api.client import TrustModelClient
from trustmodel.certify.certificates import CertificateClient
from trustmodel.core.config import configure

console = Console()


@click.group()
def cert() -> None:
    """Manage trust certificates."""
    pass


@cert.command("issue")
@click.argument("agent")
@click.option("--evaluation", "-e", required=True, help="Evaluation ID to base certificate on")
@click.option("--validity", "-v", default=365, help="Validity in days")
@click.pass_context
def issue_certificate(
    ctx: click.Context,
    agent: str,
    evaluation: str,
    validity: int,
) -> None:
    """Issue a trust certificate."""
    async def _issue() -> None:
        from uuid import UUID

        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()
        cert_client = CertificateClient(client)

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

            certificate = await cert_client.issue(
                agent_id=agent_id,
                evaluation_id=UUID(evaluation),
                validity_days=validity,
            )

            console.print(Panel.fit(
                f"[bold green]Certificate Issued![/bold green]\n\n"
                f"ID: {certificate.id}\n"
                f"Agent: {certificate.agent_name}\n"
                f"Grade: [bold]{certificate.grade}[/bold]\n"
                f"Overall Score: {certificate.scores.overall:.1f}\n"
                f"Valid Until: {certificate.expires_at.date()}",
                title="Trust Certificate",
            ))

            if certificate.capabilities:
                console.print("\n[bold]Certified Capabilities:[/bold]")
                for cap in certificate.capabilities:
                    console.print(f"  [green]✓[/green] {cap}")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_issue())


@cert.command("verify")
@click.argument("certificate_id")
@click.pass_context
def verify_certificate(ctx: click.Context, certificate_id: str) -> None:
    """Verify a certificate."""
    async def _verify() -> None:
        from uuid import UUID

        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()
        cert_client = CertificateClient(client)

        try:
            verification = await cert_client.verify(UUID(certificate_id))

            if verification.is_fully_valid:
                console.print(Panel.fit(
                    f"[bold green]Certificate Valid[/bold green]\n\n"
                    f"Agent: {verification.agent_name}\n"
                    f"Grade: {verification.grade}\n"
                    f"Expires: {verification.expires_at.date()}",
                    title="Verification Result",
                ))
            else:
                errors = "\n".join(f"  - {e}" for e in verification.errors)
                console.print(Panel.fit(
                    f"[bold red]Certificate Invalid[/bold red]\n\n"
                    f"Errors:\n{errors}",
                    title="Verification Result",
                ))

            console.print(f"\n[bold]Verification Details:[/bold]")
            console.print(f"  Signature Valid: {'[green]✓[/green]' if verification.signature_valid else '[red]✗[/red]'}")
            console.print(f"  Not Expired: {'[green]✓[/green]' if verification.not_expired else '[red]✗[/red]'}")
            console.print(f"  Not Revoked: {'[green]✓[/green]' if verification.not_revoked else '[red]✗[/red]'}")

            if verification.capabilities:
                console.print(f"\n[bold]Capabilities:[/bold]")
                for cap in verification.capabilities:
                    console.print(f"  • {cap}")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_verify())


@cert.command("revoke")
@click.argument("certificate_id")
@click.option("--reason", "-r", required=True, help="Reason for revocation")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def revoke_certificate(
    ctx: click.Context,
    certificate_id: str,
    reason: str,
    force: bool,
) -> None:
    """Revoke a certificate."""
    if not force:
        if not click.confirm(f"Are you sure you want to revoke certificate {certificate_id}?"):
            raise click.Abort()

    async def _revoke() -> None:
        from uuid import UUID

        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()
        cert_client = CertificateClient(client)

        try:
            certificate = await cert_client.revoke(UUID(certificate_id), reason)

            console.print(f"[yellow]Certificate revoked:[/yellow] {certificate.id}")
            console.print(f"Reason: {reason}")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_revoke())


@cert.command("get")
@click.argument("certificate_id")
@click.pass_context
def get_certificate(ctx: click.Context, certificate_id: str) -> None:
    """Get certificate details."""
    async def _get() -> None:
        from uuid import UUID

        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()
        cert_client = CertificateClient(client)

        try:
            certificate = await cert_client.get(UUID(certificate_id))

            console.print(Panel.fit(
                f"[bold]Certificate Details[/bold]\n\n"
                f"ID: {certificate.id}\n"
                f"Agent: {certificate.agent_name}\n"
                f"Organization: {certificate.organization_name}\n"
                f"Grade: [bold]{certificate.grade}[/bold]\n"
                f"Status: {certificate.status.value}\n"
                f"Issued: {certificate.issued_at.date()}\n"
                f"Expires: {certificate.expires_at.date()}\n"
                f"Days Remaining: {certificate.days_until_expiry}",
                title="Trust Certificate",
            ))

            console.print(f"\n[bold]Scores:[/bold]")
            console.print(f"  Overall: {certificate.scores.overall:.1f}")
            if certificate.scores.capability is not None:
                console.print(f"  Capability: {certificate.scores.capability:.1f}")
            if certificate.scores.safety is not None:
                console.print(f"  Safety: {certificate.scores.safety:.1f}")
            if certificate.scores.reliability is not None:
                console.print(f"  Reliability: {certificate.scores.reliability:.1f}")
            if certificate.scores.communication is not None:
                console.print(f"  Communication: {certificate.scores.communication:.1f}")

            if certificate.capabilities:
                console.print(f"\n[bold]Certified Capabilities:[/bold]")
                for cap in certificate.capabilities:
                    console.print(f"  [green]✓[/green] {cap}")

            if certificate.not_certified:
                console.print(f"\n[bold]Not Certified:[/bold]")
                for cap in certificate.not_certified:
                    console.print(f"  [red]✗[/red] {cap}")

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_get())


@cert.command("list")
@click.option("--agent", "-a", help="Filter by agent")
@click.option("--status", "-s", type=click.Choice(["active", "expired", "revoked"]))
@click.option("--page", "-p", default=1, help="Page number")
@click.option("--limit", "-l", default=20, help="Results per page")
@click.pass_context
def list_certificates(
    ctx: click.Context,
    agent: Optional[str],
    status: Optional[str],
    page: int,
    limit: int,
) -> None:
    """List certificates."""
    async def _list() -> None:
        configure(
            api_key=ctx.obj.get("api_key"),
            server_url=ctx.obj.get("server"),
        )

        client = TrustModelClient()

        try:
            result = await client.search_registry()

            table = Table(title="Certificates")
            table.add_column("ID", style="dim")
            table.add_column("Agent")
            table.add_column("Grade")
            table.add_column("Status")
            table.add_column("Expires")

            for item in result.get("items", []):
                table.add_row(
                    str(item.get("certificate_id", ""))[:8] + "...",
                    item.get("agent_name", ""),
                    item.get("grade", ""),
                    item.get("status", ""),
                    str(item.get("expires_at", ""))[:10],
                )

            console.print(table)

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        finally:
            await client.close()

    asyncio.run(_list())
