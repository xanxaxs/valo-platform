"""
Valorant Tracker Dashboard.

Streamlit-based UI for viewing match data and statistics.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from src.db.database import get_session, init_db
from src.db.models import AudioSegment, Match, PlayerMatchStats, Round

# Initialize database
init_db()


def main():
    """Main dashboard."""
    st.set_page_config(
        page_title="Valorant Tracker",
        page_icon="🎯",
        layout="wide",
    )
    
    st.title("🎯 Valorant Tracker")
    
    # Sidebar navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Matches", "Statistics", "Replay", "Settings"],
    )
    
    if page == "Dashboard":
        show_dashboard()
    elif page == "Matches":
        show_matches()
    elif page == "Statistics":
        show_statistics()
    elif page == "Replay":
        show_replay()
    elif page == "Settings":
        show_settings()


def show_dashboard():
    """Show main dashboard."""
    st.header("Dashboard")
    
    session = next(get_session())
    
    # Stats overview
    col1, col2, col3, col4 = st.columns(4)
    
    total_matches = session.query(Match).count()
    total_rounds = session.query(Round).count()
    total_audio = session.query(AudioSegment).count()
    
    with col1:
        st.metric("Total Matches", total_matches)
    with col2:
        st.metric("Total Rounds", total_rounds)
    with col3:
        st.metric("Audio Segments", total_audio)
    with col4:
        st.metric("Status", "Ready")
    
    # Recent matches
    st.subheader("Recent Matches")
    
    recent = session.query(Match).order_by(
        Match.created_at.desc()
    ).limit(10).all()
    
    if recent:
        for match in recent:
            with st.expander(f"{match.map_name} - {match.result.value if match.result else 'Unknown'}"):
                st.write(f"Match ID: {match.match_id}")
                st.write(f"Score: {match.ally_score} - {match.enemy_score}")
                
                # Show audio segments
                segments = session.query(AudioSegment).filter(
                    AudioSegment.match_id == match.match_id
                ).all()
                
                if segments:
                    st.write(f"Audio segments: {len(segments)}")
    else:
        st.info("No matches recorded yet. Start tracking to see data here!")


def show_matches():
    """Show matches list."""
    st.header("Matches")
    
    session = next(get_session())
    
    matches = session.query(Match).order_by(
        Match.created_at.desc()
    ).all()
    
    if not matches:
        st.info("No matches found.")
        return
    
    for match in matches:
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
        
        with col1:
            st.write(f"**{match.map_name}**")
        with col2:
            st.write(match.match_id[:8] + "...")
        with col3:
            result = match.result.value if match.result else "Unknown"
            color = "green" if result == "Win" else "red" if result == "Lose" else "gray"
            st.markdown(f":{color}[{result}]")
        with col4:
            st.write(f"{match.ally_score}-{match.enemy_score}")
        
        st.divider()


def show_statistics():
    """Show player statistics."""
    st.header("Statistics")
    
    session = next(get_session())
    
    # Get unique players
    players = session.query(PlayerMatchStats.puuid, PlayerMatchStats.player_name).distinct().all()
    
    if not players:
        st.info("No player data available.")
        return
    
    # Player selector
    player_options = {f"{p.player_name} ({p.puuid[:8]}...)": p.puuid for p in players}
    selected = st.selectbox("Select Player", list(player_options.keys()))
    
    if selected:
        puuid = player_options[selected]
        
        # Get stats
        stats = session.query(PlayerMatchStats).filter(
            PlayerMatchStats.puuid == puuid
        ).all()
        
        if stats:
            total_kills = sum(s.kills for s in stats)
            total_deaths = sum(s.deaths for s in stats)
            total_assists = sum(s.assists for s in stats)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Games", len(stats))
            with col2:
                st.metric("K/D", f"{total_kills / max(total_deaths, 1):.2f}")
            with col3:
                st.metric("Total Kills", total_kills)
            with col4:
                st.metric("Total Deaths", total_deaths)
            
            # Agent breakdown
            st.subheader("Agent Stats")
            
            agent_stats = {}
            for s in stats:
                if s.agent_name not in agent_stats:
                    agent_stats[s.agent_name] = {"games": 0, "kills": 0, "deaths": 0}
                agent_stats[s.agent_name]["games"] += 1
                agent_stats[s.agent_name]["kills"] += s.kills
                agent_stats[s.agent_name]["deaths"] += s.deaths
            
            for agent, data in agent_stats.items():
                st.write(f"**{agent}**: {data['games']} games, K/D: {data['kills'] / max(data['deaths'], 1):.2f}")


def show_replay():
    """Show 2D replay viewer."""
    st.header("2D Replay")
    
    session = next(get_session())
    
    # Match selector
    matches = session.query(Match).order_by(Match.created_at.desc()).all()
    
    if not matches:
        st.info("No matches available for replay.")
        return
    
    match_options = {f"{m.map_name} ({m.match_id[:8]}...)": m.match_id for m in matches}
    selected = st.selectbox("Select Match", list(match_options.keys()))
    
    if selected:
        match_id = match_options[selected]
        
        # Get audio segments
        segments = session.query(AudioSegment).filter(
            AudioSegment.match_id == match_id
        ).order_by(AudioSegment.round_number).all()
        
        st.subheader("Audio Segments")
        
        if segments:
            for seg in segments:
                round_text = f"Round {seg.round_number}" if seg.round_number else "Full Match"
                
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.write(round_text)
                with col2:
                    st.write(f"{seg.duration:.1f}s")
                with col3:
                    # Audio player
                    audio_path = Path(seg.file_path)
                    if audio_path.exists():
                        st.audio(str(audio_path))
                    else:
                        st.write("File not found")
        else:
            st.info("No audio segments for this match.")
        
        # TODO: Add actual 2D map visualization
        st.subheader("Map View")
        st.info("2D Map visualization coming soon...")


def show_settings():
    """Show settings page."""
    st.header("Settings")
    
    st.subheader("Audio Device")
    
    try:
        from src.sync.sync_recorder import SyncRecorder
        
        devices = SyncRecorder.list_audio_devices()
        default = SyncRecorder.get_default_device()
        
        if devices:
            st.write("Available devices:")
            for device in devices:
                marker = " ✓" if default and device["name"] == default["name"] else ""
                st.write(f"- {device['name']}{marker}")
        else:
            st.warning("No audio devices found.")
    except Exception as e:
        st.error(f"Could not list audio devices: {e}")
    
    st.subheader("Database")
    st.write(f"Path: `data/valorant_tracker.db`")
    
    if st.button("Reset Database"):
        if st.checkbox("I understand this will delete all data"):
            init_db()
            st.success("Database reset!")


if __name__ == "__main__":
    main()

