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

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from src.db.database import get_session, init_db
from src.db.models import AudioSegment, Match, PlayerMatchStats, Round, MatchEventSnapshot

# Initialize database
init_db()

# Asset paths
ASSETS_DIR = Path(__file__).parent / "assets"
AGENTS_DIR = ASSETS_DIR / "agents"
MAPS_DIR = ASSETS_DIR / "maps"

# Replay calibration persistence
REPLAY_CALIBRATION_PATH = Path(__file__).parent.parent / "config" / "replay_calibration.json"


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
            ["📊 Dashboard", "🎮 Matches", "📈 Statistics", "🎬 Replay", "🤖 Coach", "⚙️ Settings"],
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
    
    recent = session.query(Match).order_by(
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
    
    matches = session.query(Match).order_by(
        Match.created_at.desc()
    ).all()
    
    if not matches:
        st.info("No matches found.")
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
        })
    
    # Display as styled columns
    cols = st.columns([3, 1, 2, 1, 1, 1, 1, 1, 1, 1])
    headers = ["Player", "ACS", "K/D/A", "KD", "ADR", "FK", "FD", "±FK", "TFK", "HS%"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    
    for p in data:
        cols = st.columns([3, 1, 2, 1, 1, 1, 1, 1, 1, 1])
        
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
        
        # FK
        cols[5].write(str(p["fk"]))
        
        # FD
        cols[6].write(str(p["fd"]))
        
        # ±FK
        fk_color = "#0d9488" if p["fk_diff"] > 0 else "#ff4655" if p["fk_diff"] < 0 else "#94a3b8"
        cols[7].markdown(f'<span style="color:{fk_color};font-weight:600;">{p["fk_display"]}</span>', unsafe_allow_html=True)
        
        # TFK
        cols[8].write(str(p["tfk"]))
        
        # HS%
        hs_color = "#0d9488" if p["hs_pct"] >= 25 else "#d97706" if p["hs_pct"] >= 15 else "#94a3b8"
        cols[9].markdown(f'<span style="color:{hs_color};font-weight:600;">{p["hs_pct"]:.1f}%</span>', unsafe_allow_html=True)


def render_time_kd_table(players):
    """Render time-based K/D table."""
    st.caption("1st (0-20s) | 1.5th (20-40s) | 2nd (40-60s) | Late (60s+) | PP (Post Plant)")
    
    data = []
    for p in players:
        try:
            tkd = json.loads(p.time_based_kd) if p.time_based_kd else {}
        except:
            tkd = {}
        
        def fmt_zone(zone):
            z = tkd.get(zone, {})
            k, d = z.get("k", 0), z.get("d", 0)
            return f"{k}/{d}"
        
        data.append({
            "Player": p.player_name or "Unknown",
            "1st": fmt_zone("1st"),
            "1.5th": fmt_zone("1.5th"),
            "2nd": fmt_zone("2nd"),
            "Late": fmt_zone("Late"),
            "PP": fmt_zone("PP"),
        })
    
    # Check if there's any data
    has_data = any(
        row["1st"] != "0/0" or row["1.5th"] != "0/0" or 
        row["2nd"] != "0/0" or row["Late"] != "0/0" or row["PP"] != "0/0"
        for row in data
    )
    
    if has_data:
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("Time-based K/D data not available for this match.")


def _render_rib_style_map(
    map_name: str,
    positions: list,
    event_data: dict,
    calibration: dict,
    trace_points: list[dict] | None = None,
    show_names: bool = False,
    lock_view: bool = True,
):
    """
    rib.gg 風の2Dマップ描画（マップ画像 + プレイヤー位置 + キル線）。

    - positions: import_replay_events.py 形式 or replay_service.py 形式のどちらでも受ける
      - {"puuid","name","x","y",...} / {"puuid","player_name","x","y","team_id",...}
    - calibration: flip_y / offset_x / offset_y / scale
    """
    import base64
    import plotly.graph_objects as go

    # --- Map image (full SVG) ---
    map_svg_path = get_map_svg_path(map_name)
    if map_svg_path.exists():
        with open(map_svg_path, "rb") as f:
            map_b64 = base64.b64encode(f.read()).decode("utf-8")
        map_mime = "image/svg+xml"
    else:
        # Fallback to thumbnail if SVG not found
        thumb_path = get_map_thumbnail_path(map_name)
        map_b64 = image_to_base64(thumb_path) if thumb_path.exists() else ""
        map_mime = "image/webp"

    # --- Bounds (image placement + axis range) per map ---
    MAP_DEFAULT_BOUNDS = {
        "Abyss": {"x_min": -5000, "x_max": 5000, "y_min": -4000, "y_max": 2000},
        "Ascent": {"x_min": -6000, "x_max": 8000, "y_min": -6000, "y_max": 8000},
        "Bind": {"x_min": -5000, "x_max": 7500, "y_min": -5000, "y_max": 7000},
        "Haven": {"x_min": -6500, "x_max": 7500, "y_min": -5000, "y_max": 9000},
        "Split": {"x_min": -6000, "x_max": 7000, "y_min": -5500, "y_max": 7500},
        "Icebox": {"x_min": -5000, "x_max": 7000, "y_min": -5000, "y_max": 7000},
        "Breeze": {"x_min": -7000, "x_max": 9000, "y_min": -6000, "y_max": 9000},
        "Fracture": {"x_min": -7000, "x_max": 7000, "y_min": -7000, "y_max": 7000},
        "Pearl": {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000},
        "Lotus": {"x_min": -7000, "x_max": 8000, "y_min": -6000, "y_max": 8000},
        "Sunset": {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000},
        "Corrode": {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000},
    }
    fallback_bounds = {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000}
    default_bounds = MAP_DEFAULT_BOUNDS.get(map_name, fallback_bounds)
    b = {
        "x_min": float(calibration.get("x_min", default_bounds["x_min"])),
        "x_max": float(calibration.get("x_max", default_bounds["x_max"])),
        "y_min": float(calibration.get("y_min", default_bounds["y_min"])),
        "y_max": float(calibration.get("y_max", default_bounds["y_max"])),
    }

    # --- Calibration ---
    flip_x = bool(calibration.get("flip_x", False))
    flip_y = bool(calibration.get("flip_y", True))
    offset_x = float(calibration.get("offset_x", 0.0))
    offset_y = float(calibration.get("offset_y", 0.0))
    scale = float(calibration.get("scale", 1.0))

    def cal_xy(x: float, y: float) -> tuple[float, float]:
        xx = (x * scale) + offset_x
        yy = (y * scale) + offset_y
        if flip_x:
            xx = -xx
        if flip_y:
            yy = -yy
        return xx, yy

    killer_puuid = event_data.get("killer") or ""
    victim_puuid = event_data.get("victim") or ""

    # --- Normalize / split teams (暫定) ---
    # DBに team_id が無い場合があるので、見つからなければ indexで 5/5 に分割
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

        xx, yy = cal_xy(x, y)
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
            }
        )

    fig = go.Figure()

    # Background map image: stretch to bounds
    if map_b64:
        fig.add_layout_image(
            dict(
                source=f"data:{map_mime};base64,{map_b64}",
                x=b["x_min"],
                y=b["y_max"],
                xref="x",
                yref="y",
                sizex=b["x_max"] - b["x_min"],
                sizey=b["y_max"] - b["y_min"],
                sizing="stretch",
                opacity=1.0,
                layer="below",
            )
        )

    # Points
    def add_player(pt: dict):
        base_color = "#0ea5e9" if pt["team"] == "blue" else "#ff4655"
        color = base_color if pt["is_alive"] else "#94a3b8"
        symbol = "star" if pt["is_killer"] else ("x" if pt["is_victim"] else "circle")
        size = 18 if (pt["is_killer"] or pt["is_victim"]) else 14
        line_color = "#fbbf24" if pt["is_killer"] else ("#ff4655" if pt["is_victim"] else base_color)
        line_w = 3 if (pt["is_killer"] or pt["is_victim"]) else 2

        mode = "markers+text" if show_names else "markers"
        kwargs: dict[str, Any] = {}
        if show_names:
            kwargs.update(
                dict(
                    text=[pt["name"][:10]],
                    textposition="top center",
                    textfont=dict(size=10, color=base_color, family="Arial Black"),
                )
            )

        fig.add_trace(
            go.Scatter(
                x=[pt["x"]],
                y=[pt["y"]],
                mode=mode,
                marker=dict(size=size, color=color, symbol=symbol, line=dict(color=line_color, width=line_w)),
                hovertemplate=(
                    f"<b>{pt['name']}</b><br>"
                    f"team: {pt['team']}<br>"
                    f"x={pt['x']:.0f}, y={pt['y']:.0f}<extra></extra>"
                ),
                showlegend=False,
                **kwargs,
            )
        )

    # Trace layer (rib.ggっぽい “軌跡/分布”)
    if trace_points:
        tx = []
        ty = []
        tc = []
        for p in trace_points:
            try:
                x = float(p.get("x"))
                y = float(p.get("y"))
            except Exception:
                continue
            team = p.get("team_id") or "blue"
            xx, yy = cal_xy(x, y)
            tx.append(xx)
            ty.append(yy)
            tc.append("#0ea5e9" if team == "blue" else "#ff4655")

        if tx:
            fig.add_trace(
                go.Scatter(
                    x=tx,
                    y=ty,
                    mode="markers",
                    marker=dict(size=3, color=tc, opacity=0.10),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    for pt in norm:
        add_player(pt)

    # Kill line
    killer_pt = next((p for p in norm if p["is_killer"]), None)
    victim_pt = next((p for p in norm if p["is_victim"]), None)
    if killer_pt and victim_pt:
        fig.add_trace(
            go.Scatter(
                x=[killer_pt["x"], victim_pt["x"]],
                y=[killer_pt["y"], victim_pt["y"]],
                mode="lines",
                line=dict(color="#fbbf24", width=2, dash="dot"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.update_layout(
        height=520,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(
        range=[b["x_min"], b["x_max"]],
        showgrid=False,
        zeroline=False,
        showticklabels=False,
        fixedrange=lock_view,
    )
    fig.update_yaxes(
        range=[b["y_min"], b["y_max"]],
        showgrid=False,
        zeroline=False,
        showticklabels=False,
        scaleanchor="x",
        scaleratio=1,
        fixedrange=lock_view,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False, "scrollZoom": not lock_view},
    )


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
    
    # Match selector
    matches = session.query(Match).order_by(Match.created_at.desc()).all()
    if not matches:
        st.info("No matches available for replay.")
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

    ui1, ui2, ui3 = st.columns([1, 1, 1])
    with ui1:
        show_names = st.checkbox("Show names", value=False, key=f"replay_show_names_{match_id}")
    with ui2:
        show_traces = st.checkbox("Show traces", value=True, key=f"replay_show_traces_{match_id}_{selected_round}")
    with ui3:
        lock_view = st.checkbox("Lock view", value=True, key=f"replay_lock_view_{match_id}")

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

    # Calibration defaults/persistence per map
    saved = _load_replay_calibration().get(map_name, {}) if map_name else {}
    # Map-specific default bounds
    MAP_UI_DEFAULTS = {
        "Abyss": {"x_min": -5000, "x_max": 5000, "y_min": -4000, "y_max": 2000},
        "Ascent": {"x_min": -6000, "x_max": 8000, "y_min": -6000, "y_max": 8000},
        "Bind": {"x_min": -5000, "x_max": 7500, "y_min": -5000, "y_max": 7000},
        "Haven": {"x_min": -6500, "x_max": 7500, "y_min": -5000, "y_max": 9000},
        "Split": {"x_min": -6000, "x_max": 7000, "y_min": -5500, "y_max": 7500},
        "Icebox": {"x_min": -5000, "x_max": 7000, "y_min": -5000, "y_max": 7000},
        "Breeze": {"x_min": -7000, "x_max": 9000, "y_min": -6000, "y_max": 9000},
        "Fracture": {"x_min": -7000, "x_max": 7000, "y_min": -7000, "y_max": 7000},
        "Pearl": {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000},
        "Lotus": {"x_min": -7000, "x_max": 8000, "y_min": -6000, "y_max": 8000},
        "Sunset": {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000},
        "Corrode": {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000},
    }
    default_b = MAP_UI_DEFAULTS.get(map_name, {"x_min": -6000, "x_max": 8000, "y_min": -5000, "y_max": 8000})
    # Bounds (image placement + axis range) + affine (flip/offset/scale)
    # Start with saved values, else map-specific defaults.
    b_xmin = float(saved.get("x_min", default_b["x_min"]))
    b_xmax = float(saved.get("x_max", default_b["x_max"]))
    b_ymin = float(saved.get("y_min", default_b["y_min"]))
    b_ymax = float(saved.get("y_max", default_b["y_max"]))
    flip_x = bool(saved.get("flip_x", False))
    flip_y = bool(saved.get("flip_y", True))
    offset_x = float(saved.get("offset_x", 0.0))
    offset_y = float(saved.get("offset_y", 0.0))
    scale = float(saved.get("scale", 1.0))

    with st.expander("🧭 Abyss キャリブレーション（rib.gg合わせ込み）", expanded=(map_name == "Abyss")):
        st.caption("まずは Abyss を合わせて、合ったら Save で固定化してください。")
        st.caption("✨ Auto-fit: この試合の座標分布からboundsを推定して、点群がマップ全体に収まる初期値を自動生成します。")
        cA, cB, cC, cD = st.columns(4)
        with cA:
            b_xmin = st.number_input("x_min", value=b_xmin, step=100.0, key=f"cal_xmin_{map_name}")
            b_ymin = st.number_input("y_min", value=b_ymin, step=100.0, key=f"cal_ymin_{map_name}")
        with cB:
            b_xmax = st.number_input("x_max", value=b_xmax, step=100.0, key=f"cal_xmax_{map_name}")
            b_ymax = st.number_input("y_max", value=b_ymax, step=100.0, key=f"cal_ymax_{map_name}")
        with cC:
            flip_x = st.checkbox("Flip X", value=flip_x, key=f"cal_flipx_{map_name}")
            flip_y = st.checkbox("Flip Y", value=flip_y, key=f"cal_flipy_{map_name}")
        with cD:
            scale = st.number_input("Scale", value=scale, step=0.05, key=f"cal_scale_{map_name}")
            offset_x = st.number_input("Offset X", value=offset_x, step=100.0, key=f"cal_offx_{map_name}")
            offset_y = st.number_input("Offset Y", value=offset_y, step=100.0, key=f"cal_offy_{map_name}")

        cS, cR = st.columns([1, 1])
        with cS:
            if st.button("💾 Save calibration", type="primary", key=f"cal_save_{map_name}"):
                _save_replay_calibration(
                    map_name,
                    {
                        "x_min": b_xmin,
                        "x_max": b_xmax,
                        "y_min": b_ymin,
                        "y_max": b_ymax,
                        "flip_x": flip_x,
                        "flip_y": flip_y,
                        "offset_x": offset_x,
                        "offset_y": offset_y,
                        "scale": scale,
                    },
                )
                st.success("Saved. 次回から自動で適用されます。")
        with cR:
            if st.button("↩️ Reset (unsaved)", key=f"cal_reset_{map_name}"):
                b_xmin = float(default_b["x_min"])
                b_xmax = float(default_b["x_max"])
                b_ymin = float(default_b["y_min"])
                b_ymax = float(default_b["y_max"])
                flip_x, flip_y = False, True
                offset_x, offset_y, scale = 0.0, 0.0, 1.0

        if st.button("✨ Auto-fit bounds from replay data", key=f"cal_autofit_{map_name}"):
            xs, ys = _collect_xy_from_events(events)
            if len(xs) < 100:
                st.warning("座標サンプルが少ないため、自動推定が荒い可能性があります（イベントが少ない/欠損の可能性）。")
            if xs and ys:
                xs_s = sorted(xs)
                ys_s = sorted(ys)
                # robust range to avoid outliers
                x_lo = _percentile(xs_s, 0.02)
                x_hi = _percentile(xs_s, 0.98)
                y_lo = _percentile(ys_s, 0.02)
                y_hi = _percentile(ys_s, 0.98)
                # pad 12%
                x_pad = (x_hi - x_lo) * 0.12
                y_pad = (y_hi - y_lo) * 0.12
                b_xmin = float(x_lo - x_pad)
                b_xmax = float(x_hi + x_pad)
                b_ymin = float(y_lo - y_pad)
                b_ymax = float(y_hi + y_pad)
                # keep current flip/offset/scale; if nothing saved, keep typical defaults
                if not saved:
                    flip_x, flip_y = False, True
                    offset_x, offset_y, scale = 0.0, 0.0, 1.0
                st.success(f"Auto-fit完了: x[{b_xmin:.0f},{b_xmax:.0f}] y[{b_ymin:.0f},{b_ymax:.0f}]")
        else:
                st.error("座標データを抽出できませんでした（player_positionsが空/壊れている可能性）。")

    with col_map:
        _render_rib_style_map(
            map_name=map_name,
            positions=positions,
            event_data=event_data,
            trace_points=trace_points,
            show_names=show_names,
            lock_view=lock_view,
            calibration={
                "x_min": b_xmin,
                "x_max": b_xmax,
                "y_min": b_ymin,
                "y_max": b_ymax,
                "flip_x": flip_x,
                "flip_y": flip_y,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "scale": scale,
            },
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
    matches = session.query(Match).order_by(Match.created_at.desc()).all()
    
    if not matches:
        st.info("No matches available for analysis.")
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
