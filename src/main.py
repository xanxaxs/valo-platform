"""
Valorant Tracker - Main Entry Point

Orchestrates match tracking with synchronized audio recording.
"""

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.api.client import ValorantClient, ValorantClientManager
from src.db.database import get_session, init_db
from src.services.match_tracker import MatchTrackerService

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger(__name__)
console = Console()


class ValorantTracker:
    """
    Main application class.
    
    Coordinates all tracking components.
    """
    
    def __init__(self):
        """Initialize tracker."""
        # Ensure directories
        settings.ensure_directories()
        
        # Initialize database
        init_db()
        
        # Components
        self.client = ValorantClient()
        self.session = next(get_session())
        self.match_tracker: MatchTrackerService | None = None
    
    async def start(self) -> None:
        """Start the tracker."""
        console.print("[bold green]Valorant Tracker[/bold green]")
        console.print("Waiting for Valorant to start...")
        
        # Connect to Valorant
        while True:
            if await self.client.connect():
                console.print(f"[green]Connected![/green] Playing as: {self.client.puuid}")
                break
            await asyncio.sleep(3.0)
        
        # Initialize match tracker
        self.match_tracker = MatchTrackerService(
            client=self.client,
            session=self.session,
            recordings_dir=settings.recordings_path,
        )
        
        # Set up callbacks
        self.match_tracker.on_match_start(self._on_match_start)
        self.match_tracker.on_match_end(self._on_match_end)
        
        # Start tracking
        await self.match_tracker.start()
        
        console.print("[bold]Tracking started.[/bold] Press Ctrl+C to stop.")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
    
    async def stop(self) -> None:
        """Stop the tracker."""
        console.print("\n[yellow]Stopping...[/yellow]")
        
        if self.match_tracker:
            await self.match_tracker.stop()
        
        await self.client.disconnect()
        
        console.print("[green]Stopped.[/green]")
    
    async def _on_match_start(self, match_id: str, match_info) -> None:
        """Handle match start."""
        console.print(f"\n[bold cyan]Match Started![/bold cyan]")
        console.print(f"  Match ID: {match_id}")
        if match_info:
            console.print(f"  Map: {match_info.map_id}")
            console.print(f"  Players: {len(match_info.players)}")
        console.print("  [green]Recording audio...[/green]")
    
    async def _on_match_end(self, match_id: str) -> None:
        """Handle match end."""
        console.print(f"\n[bold yellow]Match Ended![/bold yellow]")
        console.print(f"  Match ID: {match_id}")
        console.print("  [green]Data saved.[/green]")
    
    def health_check(self) -> dict:
        """Check system health."""
        from src.sync.sync_recorder import SyncRecorder
        
        return {
            "database": "OK",
            "recordings_dir": str(settings.recordings_path),
            "audio_devices": SyncRecorder.list_audio_devices(),
            "default_device": SyncRecorder.get_default_device(),
        }


@click.group()
def cli():
    """Valorant Tracker - Match tracking with VC sync."""
    pass


@cli.command()
def track():
    """Start match tracking."""
    tracker = ValorantTracker()
    
    async def run():
        try:
            await tracker.start()
        except KeyboardInterrupt:
            pass
        finally:
            await tracker.stop()
    
    asyncio.run(run())


@cli.command()
def health():
    """Check system health."""
    tracker = ValorantTracker()
    status = tracker.health_check()
    
    console = Console()
    console.print("\n[bold]System Health Check[/bold]\n")
    
    for key, value in status.items():
        if key == "audio_devices":
            console.print(f"[cyan]{key}:[/cyan]")
            for device in value:
                console.print(f"  - {device['name']} (ch: {device['channels']})")
        else:
            console.print(f"[cyan]{key}:[/cyan] {value}")


@cli.command()
def init():
    """Initialize database."""
    init_db()
    console = Console()
    console.print("[green]Database initialized![/green]")


@cli.command()
def dashboard():
    """Launch Streamlit dashboard."""
    import subprocess
    
    dashboard_path = Path(__file__).parent.parent / "dashboard" / "app.py"
    subprocess.run(["streamlit", "run", str(dashboard_path)])


def main():
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
