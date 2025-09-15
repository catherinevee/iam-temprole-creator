"""
Command-line interface for the IAM Role Vending Machine.
"""

import json
import os
import sys
from datetime import datetime
from typing import Optional, List

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .models import RoleRequest, PermissionTier, SessionStatus
from .role_vendor import role_vendor
from .config import settings

console = Console()


@click.group()
@click.version_option()
def main():
    """IAM Role Vending Machine - Secure temporary AWS access for contractors."""
    pass


@main.command()
@click.option('--project-id', required=True, help='Project identifier')
@click.option('--user-id', required=True, help='Your user ID')
@click.option('--permission-tier', 
              type=click.Choice([tier.value for tier in PermissionTier]),
              required=True,
              help='Permission tier (read-only, developer, admin, break-glass)')
@click.option('--duration-hours', 
              type=int, 
              default=4,
              help='Session duration in hours (1-36)')
@click.option('--reason', 
              required=True,
              help='Business justification for access')
@click.option('--mfa-used', 
              is_flag=True,
              help='Indicate if MFA was used for authentication')
@click.option('--output-format',
              type=click.Choice(['env', 'aws-config', 'json']),
              default='env',
              help='Output format for credentials')
@click.option('--save-to-file',
              help='Save credentials to file instead of stdout')
def request_role(project_id: str, user_id: str, permission_tier: str, 
                duration_hours: int, reason: str, mfa_used: bool,
                output_format: str, save_to_file: Optional[str]):
    """Request a temporary IAM role."""
    
    # Validate inputs
    if duration_hours < 1 or duration_hours > 36:
        console.print("[red]Error: Duration must be between 1 and 36 hours[/red]")
        sys.exit(1)
    
    if len(reason) < 10:
        console.print("[red]Error: Reason must be at least 10 characters[/red]")
        sys.exit(1)
    
    # Create role request
    request = RoleRequest(
        project_id=project_id,
        user_id=user_id,
        permission_tier=PermissionTier(permission_tier),
        duration_hours=duration_hours,
        reason=reason,
        ip_address=_get_client_ip(),
        mfa_used=mfa_used
    )
    
    # Show request summary
    console.print(Panel.fit(
        f"[bold]Requesting Role[/bold]\n"
        f"Project: {project_id}\n"
        f"User: {user_id}\n"
        f"Tier: {permission_tier}\n"
        f"Duration: {duration_hours} hours\n"
        f"MFA Used: {'Yes' if mfa_used else 'No'}",
        title="Role Request"
    ))
    
    # Request role
    with console.status("[bold green]Requesting temporary role..."):
        session = role_vendor.request_role(request)
    
    if not session:
        console.print("[red]Error: Failed to create role session[/red]")
        sys.exit(1)
    
    # Assume role and get credentials
    with console.status("[bold green]Assuming role and generating credentials..."):
        credentials = role_vendor.assume_role(session)
    
    if not credentials:
        console.print("[red]Error: Failed to assume role[/red]")
        sys.exit(1)
    
    # Output credentials
    _output_credentials(credentials, output_format, save_to_file)
    
    # Show session info
    console.print(f"\n[green]✓[/green] Role session created: {session.session_id}")
    console.print(f"[green]✓[/green] Expires at: {session.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")


@main.command()
@click.option('--project-id', required=True, help='Project identifier')
@click.option('--session-id', required=True, help='Session ID to check')
def check_status(project_id: str, session_id: str):
    """Check status of a role session."""
    
    status = role_vendor.get_session_status(project_id, session_id)
    
    if not status:
        console.print("[red]Error: Session not found[/red]")
        sys.exit(1)
    
    # Create status table
    table = Table(title="Session Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Session ID", status["session_id"])
    table.add_row("Project ID", status["project_id"])
    table.add_row("User ID", status["user_id"])
    table.add_row("Permission Tier", status["permission_tier"])
    table.add_row("Status", status["status"])
    table.add_row("Requested At", status["requested_at"])
    table.add_row("Expires At", status["expires_at"])
    table.add_row("Time Remaining", f"{status['time_remaining']:.0f} seconds")
    
    console.print(table)


@main.command()
@click.option('--user-id', required=True, help='User ID to list sessions for')
@click.option('--status', 
              type=click.Choice([status.value for status in SessionStatus]),
              help='Filter by session status')
def list_sessions(user_id: str, status: Optional[str]):
    """List role sessions for a user."""
    
    session_status = SessionStatus(status) if status else None
    sessions = role_vendor.list_user_sessions(user_id, session_status)
    
    if not sessions:
        console.print("[yellow]No sessions found[/yellow]")
        return
    
    # Create sessions table
    table = Table(title=f"Sessions for {user_id}")
    table.add_column("Session ID", style="cyan")
    table.add_column("Project", style="white")
    table.add_column("Tier", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Expires At", style="yellow")
    table.add_column("Time Remaining", style="blue")
    
    for session in sessions:
        time_remaining = f"{session['time_remaining']:.0f}s"
        if session['time_remaining'] > 3600:
            time_remaining = f"{session['time_remaining']/3600:.1f}h"
        
        table.add_row(
            session["session_id"][:8] + "...",
            session["project_id"],
            session["permission_tier"],
            session["status"],
            session["expires_at"][:19],
            time_remaining
        )
    
    console.print(table)


@main.command()
@click.option('--project-id', required=True, help='Project identifier')
@click.option('--session-id', required=True, help='Session ID to revoke')
def revoke_session(project_id: str, session_id: str):
    """Revoke a role session."""
    
    if role_vendor.revoke_session(project_id, session_id):
        console.print(f"[green]✓[/green] Session {session_id} revoked successfully")
    else:
        console.print("[red]Error: Failed to revoke session[/red]")
        sys.exit(1)


@main.command()
def list_available_roles():
    """List available permission tiers and their capabilities."""
    
    roles_table = Table(title="Available Permission Tiers")
    roles_table.add_column("Tier", style="cyan")
    roles_table.add_column("Description", style="white")
    roles_table.add_column("Max Duration", style="yellow")
    roles_table.add_column("MFA Required", style="green")
    
    roles_table.add_row(
        "read-only",
        "Read-only access to S3, EC2, and IAM (view only)",
        "36 hours",
        "Yes"
    )
    roles_table.add_row(
        "developer",
        "Full access to S3, EC2, Lambda (no IAM modifications)",
        "8 hours",
        "Yes"
    )
    roles_table.add_row(
        "admin",
        "Full AWS access (with restrictions)",
        "8 hours",
        "Yes"
    )
    roles_table.add_row(
        "break-glass",
        "Emergency access (triggers alerts)",
        "1 hour",
        "Yes"
    )
    
    console.print(roles_table)


@main.command()
def cleanup():
    """Clean up expired sessions (admin only)."""
    
    with console.status("[bold green]Cleaning up expired sessions..."):
        cleaned_count = role_vendor.cleanup_expired_sessions()
    
    console.print(f"[green]✓[/green] Cleaned up {cleaned_count} expired sessions")


def _get_client_ip() -> Optional[str]:
    """Get client IP address."""
    # In a real implementation, this would get the actual client IP
    # For now, return None to use default validation
    return None


def _output_credentials(credentials, output_format: str, save_to_file: Optional[str]):
    """Output credentials in the specified format."""
    
    if output_format == "env":
        output = f"""export AWS_ACCESS_KEY_ID={credentials.access_key_id}
export AWS_SECRET_ACCESS_KEY={credentials.secret_access_key}
export AWS_SESSION_TOKEN={credentials.session_token}
export AWS_DEFAULT_REGION={settings.aws_region}"""
    
    elif output_format == "aws-config":
        output = f"""[default]
aws_access_key_id = {credentials.access_key_id}
aws_secret_access_key = {credentials.secret_access_key}
aws_session_token = {credentials.session_token}
region = {settings.aws_region}"""
    
    elif output_format == "json":
        output = json.dumps({
            "AccessKeyId": credentials.access_key_id,
            "SecretAccessKey": credentials.secret_access_key,
            "SessionToken": credentials.session_token,
            "Region": settings.aws_region,
            "Expiration": credentials.expiration.isoformat()
        }, indent=2)
    
    if save_to_file:
        with open(save_to_file, 'w') as f:
            f.write(output)
        console.print(f"[green]✓[/green] Credentials saved to {save_to_file}")
    else:
        console.print("\n[bold]Temporary Credentials:[/bold]")
        console.print(Panel(output, title="Credentials", border_style="green"))


if __name__ == "__main__":
    main()
