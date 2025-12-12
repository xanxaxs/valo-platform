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
from src.utils.notify import (
    notify_valorant_connected,
    notify_valorant_disconnected,
    notify_match_found,
    notify_match_imported,
    notify_error,
)

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
                # Desktop notification
                notify_valorant_connected(self.client.puuid[:8] if self.client.puuid else None)
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
        map_name = "Unknown"
        if match_info:
            map_name = getattr(match_info, 'map_id', 'Unknown')
            if '/' in map_name:
                map_name = map_name.split('/')[-1]
            console.print(f"  Map: {map_name}")
            console.print(f"  Players: {len(match_info.players)}")
        console.print("  [green]Recording audio...[/green]")
        
        # Desktop notification
        notify_match_found(map_name, match_id)
    
    async def _on_match_end(self, match_id: str) -> None:
        """Handle match end."""
        console.print(f"\n[bold yellow]Match Ended![/bold yellow]")
        console.print(f"  Match ID: {match_id}")
        console.print("  [green]Data saved.[/green]")
        
        # Desktop notification
        notify_match_imported("Unknown", "Data saved")
    
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


@cli.command()
def check():
    """Check Valorant connection and new matches (with desktop notification)."""
    from src.db.models import Match
    from src.utils.notify import show_notification, notify_no_new_matches
    
    console.print("[bold]Checking Valorant connection...[/bold]")
    
    async def run_check():
        client = ValorantClient()
        session = next(get_session())
        
        # Try to connect
        connected = await client.connect()
        
        if not connected:
            show_notification(
                title="🎮 VALORANT Tracker",
                message="Valorant が起動していません",
                icon="warning",
            )
            console.print("[yellow]Valorant is not running.[/yellow]")
            return
        
        console.print(f"[green]Connected![/green] PUUID: {client.puuid[:12]}...")
        
        # Get match history
        try:
            history_data = await client.get_match_history()
            if not history_data:
                show_notification(
                    title="🎮 VALORANT Tracker",
                    message="Valorant に接続しました\n新しい試合はありません",
                    icon="info",
                )
                console.print("No match history available.")
                return
            
            # Extract match IDs from history (handle different response formats)
            match_ids = []
            if isinstance(history_data, list):
                for item in history_data:
                    if isinstance(item, str):
                        match_ids.append(item)
                    elif isinstance(item, dict) and "MatchID" in item:
                        match_ids.append(item["MatchID"])
            elif isinstance(history_data, dict) and "History" in history_data:
                for item in history_data.get("History", []):
                    if isinstance(item, dict) and "MatchID" in item:
                        match_ids.append(item["MatchID"])
            
            if not match_ids:
                show_notification(
                    title="🎮 VALORANT Tracker",
                    message="Valorant に接続しました\n新しい試合はありません",
                    icon="info",
                )
                console.print("No matches found in history.")
                return
            
            console.print(f"Found {len(match_ids)} matches in history")
            
            # Check which matches are new (not in DB)
            existing_ids = set(m.match_id for m in session.query(Match.match_id).all())
            new_matches = [mid for mid in match_ids if mid not in existing_ids]
            
            if new_matches:
                # Get details of first new match
                details = await client.get_match_details(new_matches[0])
                map_name = "Unknown"
                if details:
                    map_url = details.get("matchInfo", {}).get("mapId", "")
                    map_name = map_url.split("/")[-1] if "/" in map_url else map_url
                
                show_notification(
                    title="🎮 新しい試合を発見",
                    message=f"{len(new_matches)} 件の新しい試合があります\n最新: {map_name}",
                    icon="info",
                )
                console.print(f"[cyan]Found {len(new_matches)} new matches![/cyan]")
                for mid in new_matches[:5]:
                    console.print(f"  - {mid[:30]}...")
            else:
                notify_no_new_matches()
                console.print("No new matches found.")
                
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            show_notification(
                title="❌ VALORANT Tracker",
                message=f"エラー: {str(e)[:50]}",
                icon="error",
            )
        
        await client.disconnect()
    
    asyncio.run(run_check())


@cli.command(name="import")
@click.option("--all", "import_all", is_flag=True, help="Import all new matches")
@click.option("--limit", default=5, help="Max matches to import")
def import_matches(import_all: bool, limit: int):
    """Import new matches from Valorant API."""
    from src.db.models import Match
    from src.utils.notify import show_notification
    from scripts.import_match_json import import_match, get_map_name
    import tempfile
    import json
    
    console.print("[bold]Importing matches from Valorant API...[/bold]")
    
    async def run_import():
        client = ValorantClient()
        session = next(get_session())
        
        # Connect
        connected = await client.connect()
        if not connected:
            show_notification("❌ VALORANT Tracker", "Valorant が起動していません", "error")
            console.print("[red]Valorant is not running.[/red]")
            return
        
        console.print(f"[green]Connected![/green]")
        
        # Get history
        history_data = await client.get_match_history()
        if not history_data:
            console.print("[yellow]No match history available.[/yellow]")
            return
        
        # Extract match IDs
        match_ids = []
        if isinstance(history_data, list):
            for item in history_data:
                if isinstance(item, str):
                    match_ids.append(item)
                elif isinstance(item, dict) and "MatchID" in item:
                    match_ids.append(item["MatchID"])
        elif isinstance(history_data, dict) and "History" in history_data:
            for item in history_data.get("History", []):
                if isinstance(item, dict) and "MatchID" in item:
                    match_ids.append(item["MatchID"])
        
        if not match_ids:
            console.print("[yellow]No matches found.[/yellow]")
            return
        
        # Filter new matches
        existing_ids = set(m.match_id for m in session.query(Match.match_id).all())
        new_match_ids = [mid for mid in match_ids if mid not in existing_ids]
        
        if not new_match_ids:
            console.print("[green]All matches already imported![/green]")
            show_notification("🎮 VALORANT Tracker", "新しい試合はありません", "info")
            return
        
        console.print(f"Found {len(new_match_ids)} new matches")
        
        # Limit if not importing all
        to_import = new_match_ids if import_all else new_match_ids[:limit]
        
        imported_count = 0
        for i, match_id in enumerate(to_import):
            console.print(f"\n[{i+1}/{len(to_import)}] Importing {match_id[:20]}...")
            
            try:
                # Get match details
                details = await client.get_match_details(match_id)
                if not details:
                    console.print(f"  [yellow]Could not get details, skipping[/yellow]")
                    continue
                
                # Save to temp file and import
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                    json.dump(details, f, ensure_ascii=False)
                    temp_path = f.name
                
                try:
                    import_match(temp_path)
                    imported_count += 1
                except Exception as e:
                    console.print(f"  [red]Import error: {e}[/red]")
                finally:
                    Path(temp_path).unlink(missing_ok=True)
                    
            except Exception as e:
                console.print(f"  [red]Error: {e}[/red]")
        
        await client.disconnect()
        
        # Notification
        if imported_count > 0:
            show_notification(
                "✅ インポート完了",
                f"{imported_count} 件の試合をインポートしました",
                "info"
            )
            console.print(f"\n[bold green]Imported {imported_count} matches![/bold green]")
        else:
            console.print("\n[yellow]No matches were imported.[/yellow]")
    
    asyncio.run(run_import())


def main():
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
