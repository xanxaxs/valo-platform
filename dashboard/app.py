"""
Valorant Tracker Dashboard.

Streamlit-based UI with enhanced visuals using official assets.
"""

import sys
from pathlib import Path
import json
import base64
from typing import Any
import math
import urllib.request
import urllib.parse

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

from sqlalchemy import or_
from src.db.database import get_session, init_db
from src.db.models import AudioSegment, Match, PlayerMatchStats, Round, MatchEventSnapshot


def _custom_match_filter():
    """Filter for custom matches only (queue_id is empty or 'custom')."""
    return or_(
        Match.queue_id == "",
        Match.queue_id == "custom",
        Match.queue_id.is_(None),
    )

# Initialize database
init_db()

# Asset paths
ASSETS_DIR = Path(__file__).parent / "assets"
AGENTS_DIR = ASSETS_DIR / "agents"
MAPS_DIR = ASSETS_DIR / "maps"

# Replay calibration persistence
REPLAY_CALIBRATION_PATH = Path(__file__).parent.parent / "config" / "replay_calibration.json"
MAP_TRANSFORMS_PATH = Path(__file__).parent.parent / "config" / "map_transforms.json"


def _load_replay_calibration() -> dict[str, Any]:
    """Load per-map replay calibration settings from disk."""
    try:
        if REPLAY_CALIBRATION_PATH.exists():
            with open(REPLAY_CALIBRATION_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def _save_replay_calibration(map_name: str, calibration: dict[str, Any]) -> None:
    """Persist per-map replay calibration settings to disk."""
    try:
        REPLAY_CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = _load_replay_calibration()
        data[map_name] = calibration
        with open(REPLAY_CALIBRATION_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # best-effort; UI will still work without persistence
        pass


def _load_map_transforms() -> dict[str, Any]:
    """Load map transform params (xMultiplier, yMultiplier, xScalarToAdd, yScalarToAdd) keyed by mapName."""
    try:
        if MAP_TRANSFORMS_PATH.exists():
            with open(MAP_TRANSFORMS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def _save_map_transforms(data: dict[str, Any]) -> None:
    try:
        MAP_TRANSFORMS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MAP_TRANSFORMS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def _fetch_map_transforms_from_valorant_api() -> dict[str, Any]:
    """
    Fetch map transforms and displayIcon URLs from public content API.
    Uses fields: xMultiplier, yMultiplier, xScalarToAdd, yScalarToAdd, displayIcon.
    Also stores UUID for reverse lookup.
    """
    url = "https://valorant-api.com/v1/maps"
    with urllib.request.urlopen(url, timeout=10) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    payload = json.loads(raw)
    out: dict[str, Any] = {}
    for m in payload.get("data", []) or []:
        name = m.get("displayName")
        if not name:
            continue
        # Some maps may omit these; keep only complete records
        xm = m.get("xMultiplier")
        ym = m.get("yMultiplier")
        xs = m.get("xScalarToAdd")
        ys = m.get("yScalarToAdd")
        display_icon = m.get("displayIcon")
        uuid = m.get("uuid")
        if xm is None or ym is None or xs is None or ys is None:
            continue
        out[name] = {
            "xMultiplier": xm,
            "yMultiplier": ym,
            "xScalarToAdd": xs,
            "yScalarToAdd": ys,
            "displayIcon": display_icon,
            "uuid": uuid,
        }
    return out


def _find_transform_by_display_icon(transforms: dict[str, Any], display_icon_url: str | None) -> dict | None:
    """Find transform by matching displayIcon URL or UUID extracted from it."""
    if not display_icon_url or not transforms:
        return None
    # Extract UUID from URL: https://media.valorant-api.com/maps/{uuid}/displayicon.png
    import re
    match = re.search(r'/maps/([a-f0-9-]+)/', display_icon_url)
    if match:
        target_uuid = match.group(1)
        for map_name, t in transforms.items():
            if t.get("uuid") == target_uuid:
                return t
    # Fallback: match by full URL
    for map_name, t in transforms.items():
        if t.get("displayIcon") == display_icon_url:
            return t
    return None

# Agent name mapping for folder names
AGENT_FOLDER_MAP = {
    "KAY/O": "Kayo",
    "Waylay": "Waylay",
}


def get_agent_icon_path(agent_name: str) -> Path:
    """Get agent icon path."""
    folder_name = AGENT_FOLDER_MAP.get(agent_name, agent_name)
    return AGENTS_DIR / folder_name / "icon.webp"


def get_map_svg_path(map_name: str) -> Path:
    """Get map SVG path."""
    map_key = map_name.lower()
    return MAPS_DIR / f"{map_key}_map.svg"


def get_map_thumbnail_path(map_name: str) -> Path:
    """Get map thumbnail path."""
    map_key = map_name.lower()
    return MAPS_DIR / "thumbnails" / f"{map_key}_thumbnail.webp"


def image_to_base64(image_path: Path) -> str:
    """Convert image to base64 for inline display."""
    if image_path.exists():
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def load_svg(svg_path: Path) -> str:
    """Load SVG content."""
    if svg_path.exists():
        with open(svg_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


# Custom CSS for Valorant-inspired LIGHT theme
CUSTOM_CSS = """
<style>
/* Valorant-inspired color scheme - LIGHT */
:root {
    --val-red: #ff4655;
    --val-blue: #0ea5e9;
    --val-light: #f8fafc;
    --val-gold: #d97706;
    --val-teal: #0d9488;
    --val-dark-text: #1e293b;
}

/* Light theme background */
.stApp {
    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
}

/* Stat cards */
.stat-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 15px;
    margin: 5px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

/* Player row with agent icon */
.player-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background: white;
    border-radius: 10px;
    margin: 6px 0;
    border-left: 4px solid transparent;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    transition: transform 0.2s, box-shadow 0.2s;
}

.player-row:hover {
    transform: translateX(4px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.player-row.blue {
    border-left-color: #0ea5e9;
    background: linear-gradient(90deg, rgba(14, 165, 233, 0.08) 0%, white 100%);
}

.player-row.red {
    border-left-color: #ff4655;
    background: linear-gradient(90deg, rgba(255, 70, 85, 0.08) 0%, white 100%);
}

.agent-icon {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid #e2e8f0;
}

.player-name {
    font-weight: 600;
    color: #1e293b;
    flex: 1;
    font-size: 1.05em;
}

.player-stats {
    display: flex;
    gap: 20px;
    color: #64748b;
}

.stat-value {
    font-weight: bold;
    color: #1e293b;
}

.stat-label {
    font-size: 0.8em;
    color: #94a3b8;
}

/* KDA display */
.kda {
    font-size: 1.1em;
    font-weight: bold;
    font-family: 'Segoe UI', monospace;
}

.kills { color: #0d9488; }
.deaths { color: #ff4655; }
.assists { color: #d97706; }

/* Match header */
.match-header {
    background: linear-gradient(90deg, rgba(14, 165, 233, 0.15) 0%, white 50%, rgba(255, 70, 85, 0.15) 100%);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.match-score {
    font-size: 3.5em;
    font-weight: 800;
    letter-spacing: -0.02em;
}

.score-blue { color: #0ea5e9; }
.score-red { color: #ff4655; }

/* Table styling */
.stats-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0 4px;
}

.stats-table th {
    background: #f1f5f9;
    color: #475569;
    padding: 12px;
    text-align: left;
    font-weight: 600;
}

.stats-table td {
    background: white;
    padding: 10px 12px;
    color: #1e293b;
}

/* FK/FD highlight */
.fk-positive { color: #0d9488; font-weight: bold; }
.fk-negative { color: #ff4655; }
.fk-neutral { color: #94a3b8; }

/* Map container */
.map-container {
    background: white;
    border-radius: 12px;
    padding: 12px;
    position: relative;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
}

/* Headers */
h1, h2, h3 {
    color: #1e293b !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: white;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
}

/* Metrics */
[data-testid="stMetricValue"] {
    color: #1e293b;
}

/* Match card in dashboard */
.match-card {
    background: white;
    border-radius: 12px;
    padding: 16px;
    margin: 10px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
}

/* Timeline events */
.timeline-event {
    background: white;
    padding: 12px;
    border-radius: 8px;
    margin: 6px 0;
    border-left: 3px solid #ff4655;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

/* Agent card in statistics */
.agent-card {
    background: white;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
}
</style>
"""


def main():
    """Main dashboard."""
    st.set_page_config(
        page_title="VALORANT Tracker",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # Inject custom CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    # Header with logo style
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h1 style="font-size: 2.5em; letter-spacing: 0.15em; color: #ff4655; margin: 0; font-weight: 800;">
            VALORANT <span style="color: #1e293b;">TRACKER</span>
        </h1>
        <p style="color: #64748b; margin-top: 8px; font-size: 1.1em;">Match Analysis & Replay System</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("### Navigation")
        page = st.radio(
            "",
            ["📊 Dashboard", "🎮 Matches", "📈 Statistics", "🎬 Replay", "🤖 Coach", "🛠️ Manage", "⚙️ Settings"],
            label_visibility="collapsed",
        )
    
    if "Dashboard" in page:
        show_dashboard()
    elif "Matches" in page:
        show_matches()
    elif "Statistics" in page:
        show_statistics()
    elif "Replay" in page:
        show_replay()
    elif "Coach" in page:
        show_coach()
    elif "Manage" in page:
        show_manage()
    elif "Settings" in page:
        show_settings()


def show_dashboard():
    """Show main dashboard."""
    session = next(get_session())
    
    # Stats overview
    col1, col2, col3, col4 = st.columns(4)
    
    total_matches = session.query(Match).count()
    total_rounds = session.query(Round).count()
    total_kills = session.query(PlayerMatchStats).with_entities(
        PlayerMatchStats.kills
    ).all()
    total_kills_sum = sum(k[0] or 0 for k in total_kills)
    
    with col1:
        st.metric("Total Matches", total_matches)
    with col2:
        st.metric("Total Rounds", total_rounds)
    with col3:
        st.metric("Total Kills Tracked", total_kills_sum)
    with col4:
        st.metric("Status", "🟢 Ready")
    
    st.divider()
    
    # Recent matches with visual cards
    st.subheader("Recent Matches")

    recent = session.query(Match).filter(
        Match.is_hidden == False,  # noqa: E712
        _custom_match_filter(),
    ).order_by(
        Match.created_at.desc()
    ).limit(5).all()
    
    if recent:
        for match in recent:
            # Get map thumbnail
            thumb_path = get_map_thumbnail_path(match.map_name)
            thumb_b64 = image_to_base64(thumb_path)
            
            result_color = "#0d9488" if match.result and match.result.value == "Win" else "#ff4655"
            result_text = match.result.value if match.result else "Unknown"
            
            with st.container():
                col_map, col_info, col_score = st.columns([1, 2, 1])
                
                with col_map:
                    if thumb_b64:
                        st.markdown(f"""
                        <img src="data:image/webp;base64,{thumb_b64}" 
                             style="width: 100%; border-radius: 8px; opacity: 0.9;">
                        """, unsafe_allow_html=True)
                    else:
                        st.write(f"🗺️ {match.map_name}")
                
                with col_info:
                    st.markdown(f"""
                    <div style="padding: 10px;">
                        <h3 style="margin: 0; color: #1e293b;">{match.map_name}</h3>
                        <p style="color: {result_color}; font-weight: bold; margin: 5px 0;">{result_text}</p>
                        <p style="color: #64748b; font-size: 0.9em;">
                            {"🎓 Coach View" if match.is_coach_view else "🎮 Player View"}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_score:
                    st.markdown(f"""
                    <div style="text-align: center; padding: 15px;">
                        <span style="color: #0ea5e9; font-size: 2em; font-weight: bold;">{match.ally_score}</span>
                        <span style="color: #94a3b8; font-size: 1.5em;"> - </span>
                        <span style="color: #ff4655; font-size: 2em; font-weight: bold;">{match.enemy_score}</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.divider()
    else:
        st.info("No matches recorded yet. Start tracking to see data here!")


def show_matches():
    """Show matches list with detailed stats."""
    st.header("Match History")

    session = next(get_session())

    # Filter out hidden matches and non-custom matches
    matches = session.query(Match).filter(
        Match.is_hidden == False,  # noqa: E712
        _custom_match_filter(),
    ).order_by(
        Match.created_at.desc()
    ).all()

    if not matches:
        st.info("No custom matches found. (Manage in 🛠️ Manage)")
        return

    for match in matches:
        result = match.result.value if match.result else "Unknown"
        result_emoji = "✅" if result == "Win" else "❌" if result == "Lose" else "➖"
        
        # Map thumbnail
        thumb_path = get_map_thumbnail_path(match.map_name)
        thumb_b64 = image_to_base64(thumb_path)
        
        with st.expander(f"{result_emoji} {match.map_name} | {match.ally_score}-{match.enemy_score}"):
            # Match header
            st.markdown(f"""
            <div class="match-header">
                <div class="match-score">
                    <span class="score-blue">{match.ally_score}</span>
                    <span style="color: #94a3b8;"> : </span>
                    <span class="score-red">{match.enemy_score}</span>
                </div>
                <p style="color: #64748b; margin-top: 10px;">{match.map_name} • {"Coach Mode" if match.is_coach_view else "Player Mode"}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Get player stats for this match
            player_stats = session.query(PlayerMatchStats).filter(
                PlayerMatchStats.match_id == match.match_id
            ).order_by(PlayerMatchStats.score.desc()).all()
            
            if player_stats:
                # Separate teams
                blue_team = [p for p in player_stats if p.is_ally]
                red_team = [p for p in player_stats if not p.is_ally]
                
                col_blue, col_red = st.columns(2)
                
                with col_blue:
                    st.markdown("#### 🔵 Blue Team")
                    render_team_stats(blue_team, "blue")
                
                with col_red:
                    st.markdown("#### 🔴 Red Team")
                    render_team_stats(red_team, "red")
                
                st.divider()
                
                # Full stats table
                st.markdown("#### 📊 Detailed Stats")
                render_stats_table(player_stats)
                
                # Time-based KD
                st.markdown("#### ⏱️ Time-Based K/D")
                render_time_kd_table(player_stats)
            else:
                st.info("No player stats recorded for this match.")


def render_team_stats(players, team_color):
    """Render team stats with agent icons."""
    for p in players:
        icon_path = get_agent_icon_path(p.agent_name)
        icon_b64 = image_to_base64(icon_path)
        
        rounds = max(p.rounds_played or 1, 1)
        acs = round((p.score or 0) / rounds, 0)
        kd = round((p.kills or 0) / max(p.deaths or 1, 1), 2)
        
        icon_html = f'<img src="data:image/webp;base64,{icon_b64}" class="agent-icon">' if icon_b64 else "🎯"
        
        st.markdown(f"""
        <div class="player-row {team_color}">
            {icon_html}
            <div class="player-name">{p.player_name or "Unknown"}</div>
            <div class="kda">
                <span class="kills">{p.kills or 0}</span> / 
                <span class="deaths">{p.deaths or 0}</span> / 
                <span class="assists">{p.assists or 0}</span>
            </div>
            <div style="color: #d97706; font-weight: bold;">{acs:.0f} ACS</div>
        </div>
        """, unsafe_allow_html=True)


def render_stats_table(players):
    """Render detailed stats table with agent icons."""
    
    # Use pandas dataframe for better rendering
    data = []
    for p in players:
        rounds = max(p.rounds_played or 1, 1)
        total_shots = (p.headshots or 0) + (p.bodyshots or 0) + (p.legshots or 0)
        hs_pct = round((p.headshots or 0) / max(total_shots, 1) * 100, 1) if total_shots > 0 else 0
        fk_diff = (p.first_kills or 0) - (p.first_deaths or 0)
        acs = round((p.score or 0) / rounds, 0)
        kd = round((p.kills or 0) / max(p.deaths or 1, 1), 2)
        adr = round((p.damage_dealt or 0) / rounds, 1)
        
        # Get agent icon
        icon_path = get_agent_icon_path(p.agent_name)
        icon_b64 = image_to_base64(icon_path)
        
        # FK diff display
        fk_display = f"+{fk_diff}" if fk_diff > 0 else str(fk_diff)
                    
        # KAST calculation
        kast_rounds = p.kast_rounds or 0
        kast_pct = round(kast_rounds / rounds * 100, 0) if rounds > 0 else 0

        data.append({
            "icon_b64": icon_b64,
            "player_name": p.player_name or "Unknown",
            "agent_name": p.agent_name or "Unknown",
            "acs": int(acs),
            "kills": p.kills or 0,
            "deaths": p.deaths or 0,
            "assists": p.assists or 0,
            "kd": kd,
            "adr": adr,
            "fk": p.first_kills or 0,
            "fd": p.first_deaths or 0,
            "fk_diff": fk_diff,
            "fk_display": fk_display,
            "tfk": p.true_first_kills or 0,
            "hs_pct": hs_pct,
            "kast_pct": kast_pct,
        })
    
    # Display as styled columns
    cols = st.columns([3, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1])
    headers = ["Player", "ACS", "K/D/A", "KD", "ADR", "KAST", "FK", "FD", "±FK", "TFK", "HS%"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    
    for p in data:
        cols = st.columns([3, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1])

        # Player with icon
        with cols[0]:
            icon_html = f'<img src="data:image/webp;base64,{p["icon_b64"]}" style="width:28px;height:28px;border-radius:50%;vertical-align:middle;margin-right:8px;">' if p["icon_b64"] else ""
            st.markdown(f'{icon_html}<span style="font-weight:600;">{p["player_name"]}</span><br><span style="font-size:0.8em;color:#64748b;">{p["agent_name"]}</span>', unsafe_allow_html=True)

        # ACS
        cols[1].markdown(f'<span style="color:#7c3aed;font-weight:bold;">{p["acs"]}</span>', unsafe_allow_html=True)

        # K/D/A
        cols[2].markdown(f'<span style="color:#0d9488;">{p["kills"]}</span> / <span style="color:#ff4655;">{p["deaths"]}</span> / <span style="color:#d97706;">{p["assists"]}</span>', unsafe_allow_html=True)

        # KD
        cols[3].write(f'{p["kd"]:.2f}')

        # ADR
        cols[4].write(f'{p["adr"]:.1f}')

        # KAST
        kast_color = "#0d9488" if p["kast_pct"] >= 70 else "#d97706" if p["kast_pct"] >= 50 else "#ff4655"
        cols[5].markdown(f'<span style="color:{kast_color};font-weight:600;">{int(p["kast_pct"])}%</span>', unsafe_allow_html=True)

        # FK
        cols[6].write(str(p["fk"]))

        # FD
        cols[7].write(str(p["fd"]))

        # ±FK
        fk_color = "#0d9488" if p["fk_diff"] > 0 else "#ff4655" if p["fk_diff"] < 0 else "#94a3b8"
        cols[8].markdown(f'<span style="color:{fk_color};font-weight:600;">{p["fk_display"]}</span>', unsafe_allow_html=True)

        # TFK
        cols[9].write(str(p["tfk"]))

        # HS%
        hs_color = "#0d9488" if p["hs_pct"] >= 25 else "#d97706" if p["hs_pct"] >= 15 else "#94a3b8"
        cols[10].markdown(f'<span style="color:{hs_color};font-weight:600;">{p["hs_pct"]:.1f}%</span>', unsafe_allow_html=True)


def render_time_kd_table(players):
    """Render time-based K/D with visual bars using components.html."""
    
    # Time zone labels
    zones = ["1st", "1.5th", "2nd", "Late", "PP"]
    zone_labels = {
        "1st": "0-20s",
        "1.5th": "20-40s",
        "2nd": "40-60s",
        "Late": "60s+",
        "PP": "Post Plant",
    }
    
    # Collect data
    player_data = []
    max_kills = 1
    max_deaths = 1
    
    for p in players:
        try:
            tkd = json.loads(p.time_based_kd) if p.time_based_kd else {}
        except Exception:
            tkd = {}
        
        zone_data = {}
        for zone_key in zones:
            z = tkd.get(zone_key, {})
            k, d = z.get("k", 0), z.get("d", 0)
            zone_data[zone_key] = {"k": k, "d": d}
            max_kills = max(max_kills, k)
            max_deaths = max(max_deaths, d)
        
        # Get agent icon
        icon_path = get_agent_icon_path(p.agent_name)
        icon_b64 = image_to_base64(icon_path)
        
        player_data.append({
            "name": (p.player_name or "Unknown")[:12],
            "agent": p.agent_name or "Unknown",
            "icon_b64": icon_b64,
            "is_ally": p.is_ally,
            "zones": zone_data,
        })
    
    # Check if there's any data
    has_data = any(
        any(pd["zones"][z]["k"] > 0 or pd["zones"][z]["d"] > 0 for z in zones)
        for pd in player_data
    )
    
    if not has_data:
        st.info("Time-based K/D data not available for this match.")
        return
    
    # Build complete HTML
    rows_html = ""
    for pd in player_data:
        team_color = "#0ea5e9" if pd["is_ally"] else "#ff4655"
        
        # Build zone cells
        zone_cells = ""
        for zone_key in zones:
            z = pd["zones"][zone_key]
            k, d = z["k"], z["d"]
            
            # Calculate bar widths (percentage of max)
            k_width = int(k / max_kills * 100) if max_kills > 0 else 0
            d_width = int(d / max_deaths * 100) if max_deaths > 0 else 0
            
            zone_cells += f'''
            <div class="zone-cell">
                <div class="bar-row">
                    <span class="bar-label kill">K</span>
                    <div class="bar-bg"><div class="bar-fill kill" style="width:{k_width}%"></div></div>
                    <span class="bar-value kill">{k}</span>
                </div>
                <div class="bar-row">
                    <span class="bar-label death">D</span>
                    <div class="bar-bg"><div class="bar-fill death" style="width:{d_width}%"></div></div>
                    <span class="bar-value death">{d}</span>
                </div>
            </div>
            '''
        
        # Player icon
        icon_html = f'<img src="data:image/webp;base64,{pd["icon_b64"]}" class="player-icon" style="border-color:{team_color};">' if pd["icon_b64"] else '<div class="player-icon-placeholder"></div>'
        
        rows_html += f'''
        <div class="player-row">
            <div class="player-info">
                {icon_html}
                <div class="player-name-wrap">
                    <div class="player-name">{pd["name"]}</div>
                    <div class="player-agent">{pd["agent"]}</div>
                </div>
            </div>
            {zone_cells}
        </div>
        '''
    
    # Zone headers
    zone_headers = "".join(f'<div class="zone-header"><div class="zone-title">{z}</div><div class="zone-subtitle">{zone_labels[z]}</div></div>' for z in zones)
    
    html = f'''
    <style>
        .tkd-container {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}
        .zone-header-row {{ display:flex; gap:8px; margin-bottom:8px; padding-left:160px; }}
        .zone-header {{ flex:1; text-align:center; }}
        .zone-title {{ font-size:12px; font-weight:600; color:#475569; }}
        .zone-subtitle {{ font-size:10px; color:#94a3b8; }}
        .player-row {{ display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid #e2e8f0; }}
        .player-info {{ width:150px; display:flex; align-items:center; gap:8px; }}
        .player-icon {{ width:32px; height:32px; border-radius:50%; border:2px solid; }}
        .player-icon-placeholder {{ width:32px; height:32px; border-radius:50%; background:#e2e8f0; }}
        .player-name-wrap {{ overflow:hidden; }}
        .player-name {{ font-size:13px; font-weight:600; color:#1e293b; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
        .player-agent {{ font-size:10px; color:#64748b; }}
        .zone-cell {{ flex:1; padding:2px 4px; }}
        .bar-row {{ display:flex; align-items:center; gap:4px; margin:2px 0; }}
        .bar-label {{ width:14px; font-size:10px; font-weight:600; }}
        .bar-label.kill {{ color:#0d9488; }}
        .bar-label.death {{ color:#ef4444; }}
        .bar-bg {{ flex:1; height:6px; background:#e2e8f0; border-radius:3px; overflow:hidden; }}
        .bar-fill {{ height:100%; border-radius:3px; }}
        .bar-fill.kill {{ background:#0d9488; }}
        .bar-fill.death {{ background:#ef4444; }}
        .bar-value {{ width:14px; font-size:11px; font-weight:600; text-align:right; }}
        .bar-value.kill {{ color:#0d9488; }}
        .bar-value.death {{ color:#ef4444; }}
    </style>
    <div class="tkd-container">
        <div class="zone-header-row">{zone_headers}</div>
        {rows_html}
    </div>
    '''
    
    # Calculate height based on number of players
    height = 60 + len(player_data) * 52
    components.html(html, height=height, scrolling=False)


def _render_rib_style_map(
    map_name: str,
    positions: list,
    event_data: dict,
    trace_points: list[dict] | None = None,
    show_names: bool = False,
    lock_view: bool = True,
    calibration: dict | None = None,  # kept for backwards compat, but ignored
):
    """
    rib.gg / tracker heatmap 風の2Dマップ描画（マップ画像 + プレイヤー位置 + キル線）。

    座標変換は valorant-api.com の公式 transform (xMultiplier/yMultiplier/xScalarToAdd/yScalarToAdd) を使用。
    マップ画像は valorant-api.com の displayIcon を使用。
    これにより tracker の heatmap-generator.ts と完全に同じ座標変換が実現される。
    """

    # --- Load map transforms (with displayIcon URL) ---
    transforms = _load_map_transforms()
    if not transforms:
        try:
            fetched = _fetch_map_transforms_from_valorant_api()
            if fetched:
                transforms = fetched
                _save_map_transforms(fetched)
        except Exception:
            transforms = {}

    t = transforms.get(map_name)
    
    # If map_name is Unknown or not found, try to find a default transform
    # We'll use the first displayIcon and try to match later
    if not t and transforms:
        # Use Pearl as a reasonable default for Unknown maps
        t = transforms.get("Pearl") or next(iter(transforms.values()), None)

    # --- Map image: use valorant-api.com displayIcon (same as tracker heatmap) ---
    display_icon_url = t.get("displayIcon") if t else None
    
    # If we found a displayIcon, try to find the correct transform by UUID
    if display_icon_url and (not t or map_name == "Unknown"):
        found_t = _find_transform_by_display_icon(transforms, display_icon_url)
        if found_t:
            t = found_t
            display_icon_url = t.get("displayIcon")
    if display_icon_url:
        img_tag = f'<img id="vt-map" src="{display_icon_url}" crossorigin="anonymous" style="display:block; width:100%; max-width:900px; height:auto;" />'
    else:
        # Fallback to local thumbnail if API URL not available
        thumb_path = get_map_thumbnail_path(map_name)
        thumb_b64 = image_to_base64(thumb_path) if thumb_path.exists() else ""
        if thumb_b64:
            img_tag = f'<img id="vt-map" src="data:image/webp;base64,{thumb_b64}" style="display:block; width:100%; max-width:900px; height:auto;" />'
        else:
            img_tag = '<div style="width:900px;height:520px;background:#f1f5f9;border-radius:12px;"></div>'

    # --- Coordinate transform (tracker heatmap-generator.ts formula) ---
    # x_map = victimLocationY * xMultiplier + xScalarToAdd
    # y_map = victimLocationX * yMultiplier + yScalarToAdd
    # No flip, no offset, no scale - just pure transform like tracker
    def _game_to_norm(game_x: float, game_y: float) -> tuple[float, float]:
        if t:
            # Note: X and Y are swapped in the formula (this is correct per tracker)
            nx = (game_y * float(t["xMultiplier"])) + float(t["xScalarToAdd"])
            ny = (game_x * float(t["yMultiplier"])) + float(t["yScalarToAdd"])
            nx = max(0.0, min(1.0, nx))
            ny = max(0.0, min(1.0, ny))
            return nx, ny
        # Fallback: simple bounds-based normalization
        return 0.5, 0.5

    killer_puuid = event_data.get("killer") or ""
    victim_puuid = event_data.get("victim") or ""

    # --- Normalize / split teams ---
    norm = []
    for idx, p in enumerate(positions or []):
        puuid = p.get("puuid") or p.get("subject") or ""
        name = p.get("name") or p.get("player_name") or puuid[:8] or "Unknown"
        x = p.get("x")
        y = p.get("y")
        if x is None or y is None:
            continue
        try:
            x = float(x)
            y = float(y)
        except Exception:
            continue

        team = p.get("team_id") or ("blue" if idx < 5 else "red")
        is_alive = bool(p.get("is_alive", True))

        is_killer = (puuid == killer_puuid) or (killer_puuid and puuid and puuid.startswith(killer_puuid[:8]))
        is_victim = (puuid == victim_puuid) or (victim_puuid and puuid and puuid.startswith(victim_puuid[:8]))

        # Get agent info from position data
        agent_name = p.get("agent_name") or "Unknown"
        
        # Get agent icon as base64
        agent_icon_path = get_agent_icon_path(agent_name)
        agent_icon_b64 = image_to_base64(agent_icon_path) if agent_icon_path.exists() else ""

        xx, yy = _game_to_norm(x, y)
        norm.append(
            {
                "idx": idx,
                "puuid": puuid,
                "name": name,
                "team": team,
                "x": xx,
                "y": yy,
                "is_alive": is_alive,
                "is_killer": is_killer,
                "is_victim": is_victim,
                "agent_name": agent_name,
                "agent_icon_b64": agent_icon_b64,
            }
        )

    # Convert trace_points to normalized list
    trace_norm = []
    if trace_points:
        for p in trace_points:
            try:
                x = float(p.get("x"))
                y = float(p.get("y"))
            except Exception:
                continue
            team = p.get("team_id") or "blue"
            xx, yy = _game_to_norm(x, y)
            trace_norm.append({"x": xx, "y": yy, "team": team})

    killer_pt = next((p for p in norm if p["is_killer"]), None)
    victim_pt = next((p for p in norm if p["is_victim"]), None)

    payload = {
        "players": [
            {
                "name": p["name"],
                "team": p["team"],
                "x": p["x"],
                "y": p["y"],
                "alive": p["is_alive"],
                "killer": p["is_killer"],
                "victim": p["is_victim"],
                "agent_name": p.get("agent_name", "Unknown"),
                "agent_icon": p.get("agent_icon_b64", ""),
            }
            for p in norm
        ],
        "traces": trace_norm[:2500],
        "kill_line": {
            "x1": killer_pt["x"],
            "y1": killer_pt["y"],
            "x2": victim_pt["x"],
            "y2": victim_pt["y"],
        }
        if killer_pt and victim_pt
        else None,
        "show_names": bool(show_names),
        "lock_view": bool(lock_view),
    }

    html = f"""
    <div id="vt-wrap" style="width:100%; display:flex; justify-content:center;">
      <div id="vt-stage" style="position:relative; display:inline-block; max-width:100%; user-select:none;">
        {img_tag}
        <canvas id="vt-canvas" style="position:absolute; left:0; top:0; width:100%; height:100%; pointer-events:none;"></canvas>
        <div id="vt-overlay" style="position:absolute; left:0; top:0; width:100%; height:100%; pointer-events:none;"></div>
      </div>
    </div>
    <script>
      const DATA = {json.dumps(payload)};

      const stage = document.getElementById('vt-stage');
      const img = document.getElementById('vt-map');
      const canvas = document.getElementById('vt-canvas');
      const overlay = document.getElementById('vt-overlay');

      function resizeCanvas() {{
        if (!img) return;
        const rect = img.getBoundingClientRect();
        canvas.width = Math.round(rect.width);
        canvas.height = Math.round(rect.height);
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';
      }}

      function draw() {{
        if (!img) return;
        resizeCanvas();
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.clearRect(0,0,canvas.width,canvas.height);

        // traces (very light)
        for (const p of (DATA.traces || [])) {{
          const x = p.x * canvas.width;
          const y = p.y * canvas.height;
          ctx.fillStyle = (p.team === 'blue') ? 'rgba(14,165,233,0.08)' : 'rgba(255,70,85,0.08)';
          ctx.beginPath();
          ctx.arc(x, y, 2, 0, Math.PI*2);
          ctx.fill();
        }}

        // kill line
        if (DATA.kill_line) {{
          ctx.strokeStyle = 'rgba(251,191,36,0.9)';
          ctx.setLineDash([6,4]);
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(DATA.kill_line.x1 * canvas.width, DATA.kill_line.y1 * canvas.height);
          ctx.lineTo(DATA.kill_line.x2 * canvas.width, DATA.kill_line.y2 * canvas.height);
          ctx.stroke();
          ctx.setLineDash([]);
        }}

        // players
        overlay.innerHTML = '';
        for (const p of (DATA.players || [])) {{
          const base = (p.team === 'blue') ? '#0ea5e9' : '#ff4655';
          const borderColor = p.killer ? '#fbbf24' : (p.victim ? '#ff4655' : base);
          const iconSize = (p.killer || p.victim) ? 32 : 28;
          
          // Container for icon
          const el = document.createElement('div');
          el.style.position = 'absolute';
          el.style.left = (p.x * 100) + '%';
          el.style.top  = (p.y * 100) + '%';
          el.style.transform = 'translate(-50%,-50%)';
          
          if (p.agent_icon) {{
            // Use agent icon
            const img = document.createElement('img');
            img.src = 'data:image/webp;base64,' + p.agent_icon;
            img.style.width = iconSize + 'px';
            img.style.height = iconSize + 'px';
            img.style.borderRadius = '50%';
            img.style.border = '2px solid ' + borderColor;
            img.style.boxShadow = p.killer ? '0 0 12px rgba(251,191,36,0.6)' : '0 2px 4px rgba(0,0,0,0.3)';
            img.style.opacity = p.alive ? '1' : '0.4';
            img.style.filter = p.alive ? 'none' : 'grayscale(100%)';
            el.appendChild(img);
          }} else {{
            // Fallback to colored circle
            const circle = document.createElement('div');
            const color = p.alive ? base : '#94a3b8';
            const r = (p.killer || p.victim) ? 8 : 6;
            circle.style.width = (r*2) + 'px';
            circle.style.height = (r*2) + 'px';
            circle.style.borderRadius = '999px';
            circle.style.background = color;
            circle.style.border = '2px solid ' + borderColor;
            circle.style.boxShadow = p.killer ? '0 0 12px rgba(251,191,36,0.6)' : 'none';
            el.appendChild(circle);
          }}
          overlay.appendChild(el);

          if (DATA.show_names) {{
            const label = document.createElement('div');
            label.textContent = (p.name || '').slice(0,10);
            label.style.position='absolute';
            label.style.left = (p.x * 100) + '%';
            label.style.top  = (p.y * 100) + '%';
            label.style.transform='translate(-50%,-160%)';
            label.style.fontSize='11px';
            label.style.fontWeight='700';
            label.style.color=base;
            label.style.textShadow='0 1px 2px rgba(0,0,0,0.15)';
            overlay.appendChild(label);
          }}
        }}
      }}

      if (img && img.complete) {{
        draw();
      }} else if (img) {{
        img.onload = draw;
      }}
      window.addEventListener('resize', () => draw());
    </script>
    """

    components.html(html, height=950, scrolling=False)


def show_statistics():
    """Show player statistics."""
    st.header("Player Statistics")
    
    session = next(get_session())
    
    # Get unique players
    players = session.query(
        PlayerMatchStats.puuid, 
        PlayerMatchStats.player_name,
        PlayerMatchStats.agent_name
    ).distinct().all()
    
    if not players:
        st.info("No player data available.")
        return
    
    # Player selector
    player_options = {f"{p.player_name}": p.puuid for p in players if p.player_name}
    selected = st.selectbox("Select Player", list(player_options.keys()))
    
    if selected:
        puuid = player_options[selected]
        
        # Get stats
        stats = session.query(PlayerMatchStats).filter(
            PlayerMatchStats.puuid == puuid
        ).all()
        
        if stats:
            total_kills = sum(s.kills or 0 for s in stats)
            total_deaths = sum(s.deaths or 0 for s in stats)
            total_assists = sum(s.assists or 0 for s in stats)
            total_fk = sum(s.first_kills or 0 for s in stats)
            total_fd = sum(s.first_deaths or 0 for s in stats)
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Games", len(stats))
            with col2:
                st.metric("K/D", f"{total_kills / max(total_deaths, 1):.2f}")
            with col3:
                st.metric("Total Kills", total_kills)
            with col4:
                st.metric("FK/FD", f"{total_fk}/{total_fd}")
            with col5:
                st.metric("±FK", f"{total_fk - total_fd:+d}")
            
            st.divider()
            
            # Agent breakdown
            st.subheader("Agent Stats")
            
            agent_stats = {}
            for s in stats:
                if s.agent_name not in agent_stats:
                    agent_stats[s.agent_name] = {"games": 0, "kills": 0, "deaths": 0, "fk": 0}
                agent_stats[s.agent_name]["games"] += 1
                agent_stats[s.agent_name]["kills"] += s.kills or 0
                agent_stats[s.agent_name]["deaths"] += s.deaths or 0
                agent_stats[s.agent_name]["fk"] += s.first_kills or 0
            
            cols = st.columns(min(len(agent_stats), 4))
            for i, (agent, data) in enumerate(agent_stats.items()):
                with cols[i % len(cols)]:
                    icon_path = get_agent_icon_path(agent)
                    icon_b64 = image_to_base64(icon_path)
                    
                    if icon_b64:
                        st.markdown(f"""
                        <div class="agent-card">
                            <img src="data:image/webp;base64,{icon_b64}" style="width: 64px; border-radius: 50%; border: 3px solid #e2e8f0;">
                            <h4 style="color: #1e293b; margin: 12px 0 5px 0;">{agent}</h4>
                            <p style="color: #64748b; margin: 0;">{data['games']} games</p>
                            <p style="color: #0d9488; font-weight: bold; margin: 8px 0;">
                                K/D: {data['kills'] / max(data['deaths'], 1):.2f}
                            </p>
                            <p style="color: #d97706; font-weight: 600; margin: 0;">FK: {data['fk']}</p>
                        </div>
                        """, unsafe_allow_html=True)


def show_replay():
    """Show 2D replay viewer (rib.gg-inspired)."""
    st.header("🎬 2D Replay")

    session = next(get_session())

    # Match selector (filter out hidden matches and non-custom matches)
    matches = session.query(Match).filter(
        Match.is_hidden == False,  # noqa: E712
        _custom_match_filter(),
    ).order_by(Match.created_at.desc()).all()
    if not matches:
        st.info("No custom matches available for replay. (Manage in 🛠️ Manage)")
        return

    match_options = {f"{m.map_name} | {m.ally_score}-{m.enemy_score}": m.match_id for m in matches}
    selected = st.selectbox("Select Match", list(match_options.keys()))
    if not selected:
        return
    
    match_id = match_options[selected]
    match = session.query(Match).filter(Match.match_id == match_id).first()
    map_name = match.map_name if match else "Unknown"

    # For team coloring / name resolution (rib.ggっぽく)
    puuid_to_team: dict[str, str] = {}
    puuid_to_name: dict[str, str] = {}
    try:
        stats_rows = session.query(PlayerMatchStats).filter(PlayerMatchStats.match_id == match_id).all()
        for s in stats_rows:
            if s.puuid:
                puuid_to_team[s.puuid] = "blue" if s.is_ally else "red"
                if s.player_name:
                    puuid_to_name[s.puuid] = s.player_name
    except Exception:
        pass

    # Replay data
    from src.db.models import MatchEventSnapshot, EventType

    events = session.query(MatchEventSnapshot).filter(
        MatchEventSnapshot.match_id == match_id
    ).order_by(MatchEventSnapshot.round_number, MatchEventSnapshot.round_time).all()

    if not events:
        st.warning("⚠️ No replay data available for this match.")
        return

    # --- Auto-fit helpers (data-driven bounds suggestion) ---
    def _collect_xy_from_events(evts: list[MatchEventSnapshot]) -> tuple[list[float], list[float]]:
        xs: list[float] = []
        ys: list[float] = []
        for e in evts:
            positions = e.player_positions or []
            if isinstance(positions, str):
                try:
                    positions = json.loads(positions)
                except Exception:
                    continue
            if not isinstance(positions, list):
                continue
            for p in positions:
                try:
                    x = float(p.get("x"))
                    y = float(p.get("y"))
                except Exception:
                    continue
                if math.isfinite(x) and math.isfinite(y):
                    xs.append(x)
                    ys.append(y)
        return xs, ys

    def _percentile(sorted_vals: list[float], q: float) -> float:
        """q in [0,1]. Linear interpolation on sorted list."""
        if not sorted_vals:
            return 0.0
        if q <= 0:
            return float(sorted_vals[0])
        if q >= 1:
            return float(sorted_vals[-1])
        idx = (len(sorted_vals) - 1) * q
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        if lo == hi:
            return float(sorted_vals[lo])
        w = idx - lo
        return float(sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w)

    # We drive the replay from kill events (they include playerLocations)
    kill_events = [e for e in events if e.event_type == EventType.KILL]
    if not kill_events:
        st.warning("No kill events recorded for this match.")
        return

    # Controls: round + event slider
    rounds = sorted(set(e.round_number for e in kill_events))

    c1, c2 = st.columns([1, 4])
    with c1:
        selected_round = st.selectbox(
            "Round",
            rounds,
            format_func=lambda r: f"Round {r + 1}",
            key=f"replay_round_{match_id}",
        )
    round_events = [e for e in kill_events if e.round_number == selected_round]
    if not round_events:
        st.info("No events for this round.")
        return

    with c2:
        event_idx = st.slider(
            "Event",
            0,
            len(round_events) - 1,
            0,
            key=f"replay_event_{match_id}_{selected_round}",
        )

    ui1, ui2, ui3, ui4 = st.columns([1, 1, 1, 2])
    with ui1:
        show_names = st.checkbox("Show names", value=False, key=f"replay_show_names_{match_id}")
    with ui2:
        show_traces = st.checkbox("Show traces", value=True, key=f"replay_show_traces_{match_id}_{selected_round}")
    with ui3:
        lock_view = st.checkbox("Lock view", value=True, key=f"replay_lock_view_{match_id}")
    
    # Map override selector (for Unknown maps or correction)
    with ui4:
        # Get available map names from transforms
        transforms = _load_map_transforms()
        if not transforms:
            try:
                transforms = _fetch_map_transforms_from_valorant_api()
                if transforms:
                    _save_map_transforms(transforms)
            except Exception:
                transforms = {}
        
        available_maps = ["(Auto)"] + sorted([k for k, v in transforms.items() if v.get("displayIcon")])
        
        # Default to current map_name if it's valid, otherwise "(Auto)"
        default_idx = 0
        if map_name in available_maps:
            default_idx = available_maps.index(map_name)
        
        selected_map_override = st.selectbox(
            "Map",
            available_maps,
            index=default_idx,
            key=f"replay_map_override_{match_id}",
        )
        
        # Use override if selected, otherwise use original map_name
        effective_map_name = map_name if selected_map_override == "(Auto)" else selected_map_override

    current_event = round_events[event_idx]

    # Parse event data (db might store dict or json string)
    event_data = current_event.event_data or {}
    if isinstance(event_data, str):
        try:
            event_data = json.loads(event_data)
        except Exception:
            event_data = {}

    # Parse player positions (db might store list/dict or json string)
    positions = current_event.player_positions or []
    if isinstance(positions, str):
        try:
            positions = json.loads(positions)
        except Exception:
            positions = []

    # Patch in names/teams when missing
    patched_positions = []
    for i, p in enumerate(positions or []):
        puuid = p.get("puuid") or p.get("subject") or ""
        name = p.get("name") or p.get("player_name") or puuid_to_name.get(puuid) or (puuid[:8] if puuid else f"P{i+1}")
        team_id = p.get("team_id") or puuid_to_team.get(puuid) or ("blue" if i < 5 else "red")
        patched = dict(p)
        patched["puuid"] = puuid
        patched["name"] = name
        patched["team_id"] = team_id
        patched_positions.append(patched)
    positions = patched_positions

    # Build trace points for the selected round (rib.ggっぽい “軌跡/分布” レイヤー)
    trace_points = None
    if show_traces:
        trace_points = []
        max_points = 2000
        for ev in round_events:
            pos = ev.player_positions or []
            if isinstance(pos, str):
                try:
                    pos = json.loads(pos)
                except Exception:
                    continue
            if not isinstance(pos, list):
                continue
            for i, p in enumerate(pos):
                try:
                    x = float(p.get("x"))
                    y = float(p.get("y"))
                except Exception:
                    continue
                puuid = p.get("puuid") or p.get("subject") or ""
                team_id = p.get("team_id") or puuid_to_team.get(puuid) or ("blue" if i < 5 else "red")
                trace_points.append({"x": x, "y": y, "team_id": team_id})
                if len(trace_points) >= max_points:
                    break
            if len(trace_points) >= max_points:
                break

    killer = event_data.get("killer_name", (event_data.get("killer") or "?")[:8])
    victim = event_data.get("victim_name", (event_data.get("victim") or "?")[:8])
    rt = int((current_event.round_time or 0) // 1000)
    time_display = f"{rt // 60}:{rt % 60:02d}"

    st.markdown(
        f"""
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 14px; margin-bottom: 12px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="font-weight:700; color:#1e293b;">Round {selected_round + 1} • {time_display}</div>
            <div style="font-weight:800;">
              <span style="color:#0d9488;">{killer}</span>
              <span style="color:#94a3b8;"> → </span>
              <span style="color:#ff4655;">{victim}</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Layout: map + kill feed
    col_map, col_feed = st.columns([2, 1])

    # Note: Calibration UI removed - now using valorant-api.com official transforms
    # which match the tracker heatmap-generator.ts exactly.

    with col_map:
        _render_rib_style_map(
            map_name=effective_map_name,
            positions=positions,
            event_data=event_data,
            trace_points=trace_points,
            show_names=show_names,
            lock_view=lock_view,
        )

    with col_feed:
        st.subheader("📋 Kill Feed")
        for i, e in enumerate(round_events):
            d = e.event_data or {}
            if isinstance(d, str):
                try:
                    d = json.loads(d)
                except Exception:
                    d = {}
            k = d.get("killer_name", (d.get("killer") or "?")[:8])
            v = d.get("victim_name", (d.get("victim") or "?")[:8])
            t = int((e.round_time or 0) // 1000)
            is_current = i == event_idx
            bg = "#fef3c7" if is_current else "white"
            border = "2px solid #f59e0b" if is_current else "1px solid #e2e8f0"
            st.markdown(
                f"""
                <div style="background:{bg}; border:{border}; border-radius:10px; padding:10px; margin:8px 0;">
                  <div style="color:#94a3b8; font-size:0.85em;">{t // 60}:{t % 60:02d}</div>
                  <div><span style="color:#0d9488; font-weight:700;">{k}</span> <span style="color:#94a3b8;">→</span> <span style="color:#ff4655; font-weight:700;">{v}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Audio section (unchanged)
    st.divider()
    st.subheader("🎙️ Audio Recording")

    segments = session.query(AudioSegment).filter(AudioSegment.match_id == match_id).all()
    if segments:
        for seg in segments:
            audio_path = Path(seg.file_path)
            if audio_path.exists():
                st.audio(str(audio_path))
    else:
        st.info("No audio recorded for this match.")


def show_coach():
    """Show AI coaching page."""
    st.header("🤖 RAG Coach")
    st.info("AI Coaching feature - Connect to LLM for match analysis")
    
    # Simplified coach page
    session = next(get_session())
    matches = session.query(Match).filter(
        Match.is_hidden == False,  # noqa: E712
        _custom_match_filter(),
    ).order_by(Match.created_at.desc()).all()

    if not matches:
        st.info("No custom matches available for analysis. (Manage in 🛠️ Manage)")
        return

    match_options = {f"{m.map_name} | {m.ally_score}-{m.enemy_score}": m.match_id for m in matches}
    selected = st.selectbox("Select Match to Analyze", list(match_options.keys()))
    
    if selected:
        st.markdown("""
        ### Analysis Options
        - **Quick Analysis**: Pattern-based analysis without LLM
        - **Full AI Analysis**: Deep analysis using connected LLM
        
        Configure LLM settings in the sidebar to enable AI analysis.
        """)


def show_manage():
    """Show match management page."""
    st.header("🛠️ Match Management")
    
    session = next(get_session())
    
    # Get all matches (including hidden)
    all_matches = session.query(Match).order_by(Match.created_at.desc()).all()
    
    if not all_matches:
        st.info("No matches to manage.")
        return
    
    # Filter options
    col1, col2 = st.columns([1, 3])
    with col1:
        filter_option = st.selectbox(
            "Show",
            ["All", "Visible only", "Hidden only"],
            key="manage_filter"
        )
    
    if filter_option == "Visible only":
        matches = [m for m in all_matches if not m.is_hidden]
    elif filter_option == "Hidden only":
        matches = [m for m in all_matches if m.is_hidden]
    else:
        matches = all_matches
    
    st.caption(f"Showing {len(matches)} of {len(all_matches)} matches")
    
    if not matches:
        st.info("No matches match the current filter.")
        return
    
    # Match table with actions
    for match in matches:
        created = match.created_at.strftime('%Y-%m-%d %H:%M') if match.created_at else 'N/A'
        status_icon = "🙈" if match.is_hidden else "👁️"
        
        with st.container():
            cols = st.columns([0.5, 2, 1.5, 1, 1, 1, 1])
            
            with cols[0]:
                st.write(status_icon)
            with cols[1]:
                st.write(f"**{match.map_name}**")
            with cols[2]:
                st.write(f"`{match.match_id[:20]}...`")
            with cols[3]:
                st.write(f"{match.ally_score} - {match.enemy_score}")
            with cols[4]:
                st.write(created)
            with cols[5]:
                # Toggle visibility button
                btn_label = "Show" if match.is_hidden else "Hide"
                if st.button(btn_label, key=f"toggle_{match.match_id}", use_container_width=True):
                    match.is_hidden = not match.is_hidden
                    session.commit()
                    st.rerun()
            with cols[6]:
                # Delete button
                if st.button("🗑️", key=f"delete_{match.match_id}", use_container_width=True):
                    st.session_state[f"confirm_delete_{match.match_id}"] = True
            
            # Delete confirmation
            if st.session_state.get(f"confirm_delete_{match.match_id}"):
                st.warning(f"⚠️ Delete match {match.match_id[:12]}... permanently?")
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    if st.button("Yes, delete", key=f"confirm_yes_{match.match_id}", type="primary"):
                        session.delete(match)
                        session.commit()
                        del st.session_state[f"confirm_delete_{match.match_id}"]
                        st.rerun()
                with c2:
                    if st.button("Cancel", key=f"confirm_no_{match.match_id}"):
                        del st.session_state[f"confirm_delete_{match.match_id}"]
                        st.rerun()
            
            st.divider()
    
    # Bulk actions
    st.subheader("Bulk Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Hide All Visible", use_container_width=True):
            for m in all_matches:
                if not m.is_hidden:
                    m.is_hidden = True
            session.commit()
            st.rerun()
    
    with col2:
        if st.button("Show All Hidden", use_container_width=True):
            for m in all_matches:
                if m.is_hidden:
                    m.is_hidden = False
            session.commit()
            st.rerun()
    
    with col3:
        if st.button("🗑️ Delete All Hidden", type="secondary", use_container_width=True):
            st.session_state["confirm_delete_all_hidden"] = True
    
    if st.session_state.get("confirm_delete_all_hidden"):
        hidden_count = len([m for m in all_matches if m.is_hidden])
        st.warning(f"⚠️ Delete {hidden_count} hidden matches permanently?")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("Yes, delete all", key="confirm_delete_all_yes", type="primary"):
                for m in all_matches:
                    if m.is_hidden:
                        session.delete(m)
                session.commit()
                del st.session_state["confirm_delete_all_hidden"]
                st.rerun()
        with c2:
            if st.button("Cancel", key="confirm_delete_all_no"):
                del st.session_state["confirm_delete_all_hidden"]
                st.rerun()


def show_settings():
    """Show settings page."""
    st.header("⚙️ Settings")
    
    st.subheader("Database")
    st.write(f"Path: `data/valorant_tracker.db`")
    
    session = next(get_session())
    matches = session.query(Match).count()
    players = session.query(PlayerMatchStats).count()
    rounds = session.query(Round).count()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Matches", matches)
    with col2:
        st.metric("Player Records", players)
    with col3:
        st.metric("Rounds", rounds)
    
    st.divider()
    
    st.subheader("Assets")
    st.write(f"Agents: `{AGENTS_DIR}`")
    st.write(f"Maps: `{MAPS_DIR}`")
    
    # Check assets
    agents_count = len(list(AGENTS_DIR.glob("*/icon.webp"))) if AGENTS_DIR.exists() else 0
    maps_count = len(list(MAPS_DIR.glob("*_map.svg"))) if MAPS_DIR.exists() else 0
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Agent Icons", agents_count)
    with col2:
        st.metric("Map SVGs", maps_count)


if __name__ == "__main__":
    main()
