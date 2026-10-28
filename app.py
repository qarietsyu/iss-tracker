"""
ISS Live Tracker
----------------
Real-time International Space Station dashboard built with Streamlit.

Data sources (free, no API keys):
  * https://api.wheretheiss.at   -> live position, telemetry, orbit path
  * http://api.open-notify.org   -> astronauts currently in space
"""

import time
from datetime import datetime, timezone

import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
st.set_page_config(page_title="ISS Live Tracker", page_icon="🛰️", layout="wide")

ISS_ID = 25544
API_BASE = "https://api.wheretheiss.at/v1"
CREW_URL = "http://api.open-notify.org/astros.json"
HEADERS = {"User-Agent": "iss-tracker-streamlit/1.0"}
KM_TO_MI = 0.621371
HISTORY_LIMIT = 120
ORBIT_STEP_SEC = 300  # one orbit-path point every 5 minutes

MAP_STYLES = {
    "Dark": "CartoDB dark_matter",
    "Light": "CartoDB positron",
    "Street": "OpenStreetMap",
}


# --------------------------------------------------------------------------
# Data layer
# --------------------------------------------------------------------------
def fetch_json(url: str, params: dict | None = None, timeout: int = 10):
    response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=3, show_spinner=False)
def get_position() -> dict:
    """Current ISS telemetry (cached briefly to respect the ~1 req/sec limit)."""
    return fetch_json(f"{API_BASE}/satellites/{ISS_ID}", {"units": "kilometers"})


@st.cache_data(ttl=300, show_spinner=False)
def get_orbit_path() -> dict:
    """Past and future ground track, sampled every 5 minutes (~45 min each way)."""
    now = int(time.time())
    past_ts = [now - ORBIT_STEP_SEC * i for i in range(9, 0, -1)]
    future_ts = [now + ORBIT_STEP_SEC * i for i in range(1, 10)]

    def query(timestamps):
        data = fetch_json(
            f"{API_BASE}/satellites/{ISS_ID}/positions",
            {"timestamps": ",".join(map(str, timestamps)), "units": "kilometers"},
        )
        return [(p["latitude"], p["longitude"]) for p in data]

    return {"past": query(past_ts), "future": query(future_ts)}


@st.cache_data(ttl=10, show_spinner=False)
def get_location_info(lat: float, lon: float) -> dict:
    """Reverse lookup of what the ISS is flying over (country code / timezone)."""
    return fetch_json(f"{API_BASE}/coordinates/{lat:.4f},{lon:.4f}")


@st.cache_data(ttl=3600, show_spinner=False)
def get_crew() -> list[dict]:
    data = fetch_json(CREW_URL)
    return [p for p in data.get("people", []) if p.get("craft") == "ISS"]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def split_antimeridian(points: list[tuple]) -> list[list[tuple]]:
    """Split a path wherever it wraps around +/-180 longitude so lines don't cross the map."""
    if not points:
        return []
    segments = [[points[0]]]
    for prev, cur in zip(points, points[1:]):
        if abs(cur[1] - prev[1]) > 180:
            segments.append([cur])
        else:
            segments[-1].append(cur)
    return segments


def build_map(pos: dict, orbit: dict | None, style: str, show_footprint: bool) -> folium.Map:
    lat, lon = pos["latitude"], pos["longitude"]
    fmap = folium.Map(
        location=[lat, lon],
        zoom_start=3,
        tiles=MAP_STYLES[style],
        world_copy_jump=True,
    )

    if orbit:
        current = (lat, lon)
        for segment in split_antimeridian(orbit["past"] + [current]):
            if len(segment) > 1:
                folium.PolyLine(
                    segment, color="#9aa0a6", weight=3, opacity=0.8, dash_array="6 8",
                    tooltip="Past track (last ~45 min)",
                ).add_to(fmap)
        for segment in split_antimeridian([current] + orbit["future"]):
            if len(segment) > 1:
                folium.PolyLine(
                    segment, color="#1e88e5", weight=3, opacity=0.9,
                    tooltip="Predicted track (next ~45 min)",
                ).add_to(fmap)

    if show_footprint:
        folium.Circle(
            [lat, lon],
            radius=pos["footprint"] * 1000 / 2,  # footprint is a diameter in km
            color="#e53935", weight=1, fill=True, fill_opacity=0.08,
            tooltip="Visibility footprint",
        ).add_to(fmap)

    folium.Marker(
        [lat, lon],
        icon=folium.Icon(color="red", icon="satellite", prefix="fa"),
        tooltip="International Space Station",
        popup=f"ISS<br>Lat {lat:.4f}, Lon {lon:.4f}",
    ).add_to(fmap)
    return fmap


def update_history(pos: dict) -> pd.DataFrame:
    history = st.session_state.setdefault("history", [])
    if not history or history[-1]["timestamp"] != pos["timestamp"]:
        history.append(
            {
                "timestamp": pos["timestamp"],
                "time": datetime.fromtimestamp(pos["timestamp"], tz=timezone.utc),
                "latitude": pos["latitude"],
                "longitude": pos["longitude"],
                "altitude_km": pos["altitude"],
                "velocity_kmh": pos["velocity"],
            }
        )
        del history[:-HISTORY_LIMIT]
    return pd.DataFrame(history)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")
    unit = st.radio("Units", ["Kilometers", "Miles"], horizontal=True)
    refresh_secs = st.select_slider("Refresh interval (seconds)", [3, 5, 10, 15, 30], value=5)
    map_style = st.selectbox("Map style", list(MAP_STYLES))
    show_path = st.toggle("Show orbit path", value=True)
    show_footprint = st.toggle("Show visibility footprint", value=True)
    st.divider()
    st.caption(
        "Data: [wheretheiss.at](https://wheretheiss.at/w/developer) · "
        "[Open Notify](http://open-notify.org/)"
    )

use_miles = unit == "Miles"
dist_label = "mi" if use_miles else "km"
dist_factor = KM_TO_MI if use_miles else 1.0

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("🛰️ ISS Live Tracker")
st.caption("Real-time position, telemetry and orbit path of the International Space Station.")


# --------------------------------------------------------------------------
# Live section (auto-refreshing fragment)
# --------------------------------------------------------------------------
@st.fragment(run_every=refresh_secs)
def live_view():
    try:
        pos = get_position()
    except requests.RequestException as exc:
        st.warning(f"Could not reach the ISS position API. Retrying shortly. ({exc})")
        return

    orbit = None
    if show_path:
        try:
            orbit = get_orbit_path()
        except requests.RequestException:
            st.info("Orbit path temporarily unavailable.")

    try:
        info = get_location_info(pos["latitude"], pos["longitude"])
        country = info.get("country_code", "??")
        over = "Open ocean / remote" if country in ("??", "", None) else country
        tz_name = info.get("timezone_id", "n/a")
    except requests.RequestException:
        over, tz_name = "n/a", "n/a"

    history_df = update_history(pos)
    updated = datetime.fromtimestamp(pos["timestamp"], tz=timezone.utc).strftime("%H:%M:%S UTC")

    map_col, stats_col = st.columns([2, 1], gap="large")

    with map_col:
        fmap = build_map(pos, orbit, map_style, show_footprint)
        st_folium(fmap, height=520, use_container_width=True, returned_objects=[], key="iss_map")

    with stats_col:
        st.subheader("Live telemetry")
        c1, c2 = st.columns(2)
        c1.metric("Latitude", f"{pos['latitude']:.4f}°")
        c2.metric("Longitude", f"{pos['longitude']:.4f}°")
        c3, c4 = st.columns(2)
        c3.metric("Altitude", f"{pos['altitude'] * dist_factor:,.1f} {dist_label}")
        c4.metric("Speed", f"{pos['velocity'] * dist_factor:,.0f} {dist_label}/h")
        c5, c6 = st.columns(2)
        c5.metric("Over", over)
        c6.metric("Visibility", str(pos["visibility"]).title())

        st.markdown("**Details**")
        st.dataframe(
            pd.DataFrame(
                {
                    "Field": ["Last update", "Local timezone below ISS", "Footprint diameter", "Solar lat / lon"],
                    "Value": [
                        updated,
                        tz_name,
                        f"{pos['footprint'] * dist_factor:,.0f} {dist_label}",
                        f"{pos['solar_lat']:.2f}° / {pos['solar_lon']:.2f}°",
                    ],
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    st.subheader("Session telemetry history")
    chart_df = history_df.set_index("time")
    chart_df["altitude"] = chart_df["altitude_km"] * dist_factor
    chart_df["speed"] = chart_df["velocity_kmh"] * dist_factor
    h1, h2 = st.columns(2)
    h1.caption(f"Altitude ({dist_label})")
    h1.line_chart(chart_df[["altitude"]], height=200)
    h2.caption(f"Speed ({dist_label}/h)")
    h2.line_chart(chart_df[["speed"]], height=200)

    with st.expander("🔎 Raw API data"):
        st.json(pos)
        st.download_button(
            "Download session history (CSV)",
            history_df.drop(columns=["time"]).to_csv(index=False),
            file_name="iss_history.csv",
            mime="text/csv",
        )


live_view()

# --------------------------------------------------------------------------
# Crew (static, cached for an hour)
# --------------------------------------------------------------------------
st.divider()
st.subheader("👩‍🚀 Crew currently aboard the ISS")
try:
    crew = get_crew()
    if crew:
        st.dataframe(
            pd.DataFrame(crew).rename(columns={"name": "Astronaut", "craft": "Spacecraft"}),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No crew data available right now.")
except requests.RequestException:
    st.info("Crew data temporarily unavailable.")

st.caption("Built with Streamlit, Folium and free public APIs. No API keys required.")
