"""
Valorant Tracker Dashboard.

Streamlit-based UI with enhanced visuals using official assets.
"""

import sys
from pathlib import Path
import json
import base64

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
    """Show 2D replay viewer."""
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
    
    # Check for replay data
    from src.db.models import MatchEventSnapshot
    events = session.query(MatchEventSnapshot).filter(
        MatchEventSnapshot.match_id == match_id
    ).all()
    
    # Layout
    col_map, col_timeline = st.columns([2, 1])
    
    with col_map:
        st.subheader(f"🗺️ {match.map_name if match else 'Map'}")
        
        # Load map SVG
        map_svg_path = get_map_svg_path(match.map_name)
        map_svg = load_svg(map_svg_path)
        
        if map_svg:
            # Display SVG map
            st.markdown(f"""
            <div class="map-container">
                {map_svg}
            </div>
            """, unsafe_allow_html=True)
        else:
            # Fallback to thumbnail
            thumb_path = get_map_thumbnail_path(match.map_name)
            if thumb_path.exists():
                st.image(str(thumb_path), use_container_width=True)
            else:
                st.info(f"Map image not found for {match.map_name}")
        
        if not events:
            st.warning("⚠️ No replay data available for this match.")
            st.caption("Replay snapshots are recorded when full match details are available from the API.")
    
    with col_timeline:
        st.subheader("📋 Timeline")
        
        if events:
            kill_events = [e for e in events if e.event_type == "kill"]
            
            # Round filter
            rounds = sorted(set(e.round_number for e in events if e.round_number))
            selected_round = st.selectbox(
                "Round", 
                ["All"] + [f"Round {r}" for r in rounds],
            )
            
            if selected_round != "All":
                round_num = int(selected_round.replace("Round ", ""))
                filtered = [e for e in kill_events if e.round_number == round_num]
            else:
                filtered = kill_events[:20]  # Limit
            
            for event in filtered:
                data = event.event_data or {}
                killer = data.get("killer_name", data.get("killer", "?")[:8])
                victim = data.get("victim_name", data.get("victim", "?")[:8])
                
                st.markdown(f"""
                <div class="timeline-event">
                    <strong style="color: #1e293b;">R{event.round_number}</strong> 
                    <span style="color: #94a3b8;">{event.round_time_display or ''}</span><br>
                    <span style="color: #0d9488; font-weight: 600;">{killer}</span> 
                    <span style="color: #94a3b8;">→</span> 
                    <span style="color: #ff4655; font-weight: 600;">{victim}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No events recorded.")
    
    # Audio section
    st.divider()
    st.subheader("🎙️ Audio Recording")
    
    segments = session.query(AudioSegment).filter(
        AudioSegment.match_id == match_id
    ).all()
    
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
