"""
Windows Toast Notification utility.

Uses PowerShell to display notifications without additional dependencies.
"""

import subprocess
import sys
from typing import Optional


def show_notification(
    title: str,
    message: str,
    icon: str = "info",  # info, warning, error
    duration: str = "short",  # short (5s) or long (25s)
) -> bool:
    """
    Show a Windows toast notification.
    
    Args:
        title: Notification title
        message: Notification body text
        icon: Icon type (info, warning, error)
        duration: Duration (short or long)
    
    Returns:
        True if notification was shown successfully
    """
    if sys.platform != "win32":
        # Fallback for non-Windows: just print
        print(f"[{icon.upper()}] {title}: {message}")
        return True
    
    # Escape for PowerShell
    title_escaped = title.replace("'", "''").replace('"', '`"')
    message_escaped = message.replace("'", "''").replace('"', '`"')
    
    # Map icon to Windows notification icon
    icon_map = {
        "info": "Information",
        "warning": "Warning",
        "error": "Error",
    }
    icon_type = icon_map.get(icon, "Information")
    
    # Build PowerShell script for toast notification
    ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
$notification = New-Object System.Windows.Forms.NotifyIcon
$notification.Icon = [System.Drawing.SystemIcons]::{icon_type}
$notification.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::{icon_type}
$notification.BalloonTipTitle = "{title_escaped}"
$notification.BalloonTipText = "{message_escaped}"
$notification.Visible = $true
$notification.ShowBalloonTip({5000 if duration == "short" else 25000})
Start-Sleep -Milliseconds 100
$notification.Dispose()
'''
    
    try:
        # Run PowerShell script
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        print(f"Notification error: {e}")
        return False


def notify_valorant_connected(player_name: Optional[str] = None) -> bool:
    """Notify that Valorant connection was established."""
    msg = f"プレイヤー: {player_name}" if player_name else "接続完了"
    return show_notification(
        title="🎮 VALORANT Tracker",
        message=f"Valorant に接続しました\n{msg}",
        icon="info",
    )


def notify_valorant_disconnected() -> bool:
    """Notify that Valorant connection was lost."""
    return show_notification(
        title="🎮 VALORANT Tracker",
        message="Valorant との接続が切断されました",
        icon="warning",
    )


def notify_match_found(map_name: str, match_id: str) -> bool:
    """Notify that a new match was found."""
    return show_notification(
        title="🎮 新しい試合を検出",
        message=f"マップ: {map_name}\nID: {match_id[:12]}...",
        icon="info",
    )


def notify_match_imported(map_name: str, score: str) -> bool:
    """Notify that a match was imported."""
    return show_notification(
        title="✅ 試合データを保存",
        message=f"マップ: {map_name}\nスコア: {score}",
        icon="info",
    )


def notify_no_new_matches() -> bool:
    """Notify that no new matches were found."""
    return show_notification(
        title="🎮 VALORANT Tracker",
        message="新しい試合はありません",
        icon="info",
    )


def notify_error(message: str) -> bool:
    """Notify an error occurred."""
    return show_notification(
        title="❌ VALORANT Tracker Error",
        message=message,
        icon="error",
    )


# Test
if __name__ == "__main__":
    print("Testing notification...")
    show_notification(
        title="🎮 VALORANT Tracker",
        message="通知テスト\nこれはテストメッセージです",
        icon="info",
    )
    print("Done!")
