# 🛰️ ISS Live Tracker

A real-time dashboard that tracks the International Space Station: live position on an interactive map, orbital telemetry, predicted ground track, and the crew currently aboard. Built with Python and Streamlit, with **no API keys required**.

## Features

- **Live map** with a pinned ISS marker (Folium), visibility footprint, past track (dashed) and predicted track (solid)
- **Telemetry cards**: latitude, longitude, altitude, speed, country below, daylight/eclipse status
- **Auto-refresh** every 3 to 30 seconds using `st.fragment`, without reloading the whole page
- **Session history charts** for altitude and speed, with CSV export
- **Crew list** of astronauts currently on the ISS
- **Settings**: kilometers/miles, map style, toggles for orbit path and footprint
- Raw API response viewer

## Data sources (free, keyless)

| Purpose | Endpoint |
|---|---|
| Position and telemetry | `https://api.wheretheiss.at/v1/satellites/25544` |
| Orbit path | `https://api.wheretheiss.at/v1/satellites/25544/positions` |
| Country / timezone below | `https://api.wheretheiss.at/v1/coordinates/{lat},{lon}` |
| Crew | `http://api.open-notify.org/astros.json` |

The wheretheiss.at API allows roughly one request per second. The app caches responses briefly to stay well within that limit, even with multiple visitors.

## Run locally

```bash
git clone https://github.com/<your-username>/iss-tracker.git
cd iss-tracker
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push `app.py`, `requirements.txt` and `README.md` to a public GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **Create app**, choose your repository and branch, and set the main file path to `app.py`.
4. Click **Deploy**. The app will be live at `https://<your-app-name>.streamlit.app`.

## Project structure

```
iss-tracker/
├── app.py              # Streamlit application
├── requirements.txt    # Python dependencies
└── README.md
```

## Notes

- Requires Streamlit 1.37 or newer (for `st.fragment(run_every=...)`).
- Open Notify is served over HTTP only. This is fine for server-side requests from Streamlit.
- The crew list includes only people whose craft is listed as "ISS".

## Credits

Built with [Streamlit](https://streamlit.io), [Folium](https://python-visualization.github.io/folium/), [streamlit-folium](https://github.com/randyzwitch/streamlit-folium), [wheretheiss.at](https://wheretheiss.at) and [Open Notify](http://open-notify.org).

## License

MIT
