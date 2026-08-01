"""
AQI Data Warehouse — Interactive Dashboard (Streamlit)

Air quality monitoring console: robust connection to the PostgreSQL warehouse
(Neon), tab-based navigation, advanced filters, dark technical design
(Inter + JetBrains Mono). Mirrors the exploratory analysis notebook.
"""
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy.stats import norm, pearsonr
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ---------- Page configuration ----------
st.set_page_config(
    page_title="AQI Data Warehouse",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Global Plotly theme: all px.* figures inherit this dark template
px.defaults.template = "plotly_dark"

# ---------- Constants ----------
AQI_LABELS = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
AQI_COLORS = {
    "Good": "#22c55e",
    "Fair": "#84cc16",
    "Moderate": "#eab308",
    "Poor": "#f97316",
    "Very Poor": "#ef4444",
}
AQI_ORDER = ["Good", "Fair", "Moderate", "Poor", "Very Poor"]
POLLUTANTS = ["co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3"]

# ---------- Style: dark technical console ----------
CUSTOM_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: #0f1115;
        --surface: #161922;
        --border: #262b36;
        --text: #e6e8eb;
        --text-muted: #868d9a;
        --accent: #5b8def;
        --accent-dim: rgba(91, 141, 239, 0.12);
        --good: #22c55e;
        --fair: #84cc16;
        --moderate: #eab308;
        --poor: #f97316;
        --very-poor: #ef4444;
        --radius: 8px;
    }

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
    .stApp { background: var(--bg); }

    /* Header */
    .app-header {
        border-bottom: 1px solid var(--border);
        padding: 0 0 1.25rem 0;
        margin-bottom: 1.5rem;
    }
    .app-header .eyebrow {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--accent);
        margin-bottom: 0.4rem;
    }
    .app-header h1 {
        font-size: 1.6rem;
        font-weight: 600;
        color: var(--text);
        margin: 0;
        letter-spacing: -0.01em;
    }
    .app-header p {
        font-size: 0.88rem;
        color: var(--text-muted);
        margin: 0.35rem 0 0 0;
    }

    /* Section labels */
    .section-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin: 0.5rem 0 0.75rem 0;
        border-left: 2px solid var(--accent);
        padding-left: 0.5rem;
    }

    /* Metric cards */
    .metric-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-left: 2px solid var(--accent);
        border-radius: 6px;
        padding: 1rem 1.1rem;
        margin-bottom: 0.75rem;
    }
    .metric-card .label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .metric-card .value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.55rem;
        font-weight: 600;
        color: var(--text);
        margin: 0.3rem 0 0 0;
        line-height: 1.1;
    }
    .metric-card .change {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        color: var(--text-muted);
        margin-top: 0.25rem;
    }

    /* AQI badges (outline, no fill) */
    .aqi-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.15rem 0.55rem;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 500;
        font-size: 0.72rem;
        border: 1px solid currentColor;
    }
    .aqi-good { color: #22c55e; }
    .aqi-fair { color: #84cc16; }
    .aqi-moderate { color: #eab308; }
    .aqi-poor { color: #f97316; }
    .aqi-very-poor { color: #ef4444; }

    /* Ranking rows */
    .rank-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0;
        border-bottom: 1px solid var(--border);
        font-size: 0.85rem;
        color: var(--text);
    }
    .rank-row .rank-value {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 600;
        font-size: 0.82rem;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 0.25rem; border-bottom: 1px solid var(--border); }
    .stTabs [data-baseweb="tab"] {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        color: var(--text-muted);
        padding: 0.5rem 1rem;
    }
    .stTabs [aria-selected="true"] { 
        color: var(--accent) !important;
        border-bottom: 2px solid var(--accent);
    }

    /* Native Streamlit dataframes / metrics */
    [data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; }

    /* Footer */
    .footer {
        padding: 1.25rem 0 0.5rem 0;
        border-top: 1px solid var(--border);
        margin-top: 2rem;
        color: var(--text-muted);
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        text-align: center;
    }

    /* ===== SIDEBAR ===== */
    section[data-testid="stSidebar"] {
        background: var(--surface);
        border-right: 1px solid var(--border);
        min-width: 280px;
    }
    section[data-testid="stSidebar"] > div { padding-top: 0.5rem; }

    /* Brand */
    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        padding: 0 0 1.25rem 0;
        margin-bottom: 1.25rem;
        border-bottom: 1px solid var(--border);
    }
    .sidebar-brand .dot {
        width: 10px; height: 10px;
        border-radius: 50%;
        background: var(--accent);
        box-shadow: 0 0 12px var(--accent);
        flex-shrink: 0;
    }
    .sidebar-brand .brand-text { display: flex; flex-direction: column; line-height: 1.2; }
    .sidebar-brand .brand-title {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--text);
        letter-spacing: 0.02em;
    }
    .sidebar-brand .brand-sub {
        font-size: 0.68rem;
        color: var(--text-muted);
    }

    /* Filter sections */
    .filter-section {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 0.85rem 1rem;
        margin-bottom: 0.85rem;
        transition: border-color 0.2s ease;
    }
    .filter-section:hover {
        border-color: var(--accent);
    }
    .filter-section .filter-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.6rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    .filter-section .filter-label .icon {
        font-size: 0.85rem;
    }
    .filter-section .filter-label .badge-count {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.55rem;
        background: var(--accent-dim);
        color: var(--accent);
        padding: 0.1rem 0.5rem;
        border-radius: 10px;
        margin-left: auto;
    }

    /* Active filter indicator */
    .filter-active {
        border-left: 2px solid var(--accent);
        padding-left: 0.75rem;
    }

    /* Quick stats row in sidebar */
    .sidebar-stats {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.5rem;
        margin-top: 0.25rem;
    }
    .sidebar-stat {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 0.4rem 0.6rem;
        text-align: center;
    }
    .sidebar-stat .stat-num {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text);
    }
    .sidebar-stat .stat-label {
        font-size: 0.55rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-muted);
    }

    /* Status bar at bottom of sidebar */
    .sidebar-status {
        border-top: 1px solid var(--border);
        padding-top: 0.85rem;
        margin-top: 0.5rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.6rem;
        color: var(--text-muted);
        line-height: 1.6;
    }
    .sidebar-status .status-dot {
        display: inline-block;
        width: 6px; height: 6px;
        border-radius: 50%;
        background: #22c55e;
        margin-right: 0.4rem;
        box-shadow: 0 0 8px #22c55e;
    }
    .sidebar-status .status-row {
        display: flex;
        justify-content: space-between;
        padding: 0.15rem 0;
    }

    /* Widget overrides */
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] [data-baseweb="input"] input {
        background: var(--surface) !important;
        border-color: var(--border) !important;
        color: var(--text) !important;
        font-family: 'Inter', sans-serif;
        font-size: 0.82rem;
        border-radius: 4px;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"]:focus-within,
    section[data-testid="stSidebar"] input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px var(--accent-dim) !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="tag"] {
        background: var(--accent-dim) !important;
        border: 1px solid var(--accent) !important;
        border-radius: 3px;
    }
    section[data-testid="stSidebar"] [data-baseweb="tag"] span { 
        color: var(--text) !important;
        font-size: 0.75rem;
    }

    /* Slider */
    section[data-testid="stSidebar"] [data-testid="stSlider"] div[role="slider"] {
        background-color: var(--accent) !important;
        box-shadow: 0 0 0 4px var(--accent-dim);
    }
    section[data-testid="stSidebar"] [data-testid="stSlider"] div[role="slider"]:hover {
        box-shadow: 0 0 0 6px var(--accent-dim);
    }

    /* Expander */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
    }
    section[data-testid="stSidebar"] summary {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: var(--text-muted);
        padding: 0.25rem 0;
    }
    section[data-testid="stSidebar"] summary:hover {
        color: var(--text);
    }

    /* Date inputs */
    section[data-testid="stSidebar"] [data-testid="stDateInput"] input {
        font-size: 0.78rem;
        padding: 0.4rem 0.5rem;
    }

    /* Scrollbar */
    section[data-testid="stSidebar"] ::-webkit-scrollbar { width: 4px; }
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
        background: var(--border); border-radius: 2px;
    }
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover {
        background: var(--accent);
    }

    @media (max-width: 768px) {
        .app-header h1 { font-size: 1.3rem; }
        .metric-card .value { font-size: 1.3rem; }
        section[data-testid="stSidebar"] { min-width: 240px; }
        .sidebar-stats { grid-template-columns: 1fr 1fr; }
    }
</style>
"""


# ---------- Database connection ----------
def get_database_url():
    """Looks for DATABASE_URL in st.secrets (deployment), then in .env (local)."""
    os.environ.pop("DATABASE_URL", None)
    env_path = find_dotenv()
    load_dotenv(env_path, override=True)

    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    return os.environ.get("DATABASE_URL")


def create_robust_engine(database_url):
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        connect_args={
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    )


@st.cache_resource
def get_engine():
    database_url = get_database_url()
    if not database_url:
        return None
    return create_robust_engine(database_url)


# ---------- Data loading ----------
SAFETY_ROW_CAP = 100_000


@st.cache_data(ttl=600, show_spinner="Loading warehouse data...")
def load_data():
    engine = get_engine()
    if engine is None:
        return None, "DATABASE_URL not found (neither in st.secrets nor in .env).", False

    query = f"""
        SELECT
            c.city_name, c.country, c.latitude, c.longitude,
            t.timestamp_utc, t.date, t.hour, t.day_of_week, t.day_name, t.is_weekend,
            f.aqi, f.co, f.no, f.no2, f.o3, f.so2, f.pm2_5, f.pm10, f.nh3
        FROM fact_air_quality f
        JOIN dim_city c ON c.city_key = f.city_key
        JOIN dim_time t ON t.time_key = f.time_key
        ORDER BY c.city_name, t.timestamp_utc
        LIMIT {SAFETY_ROW_CAP + 1};
    """

    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            df = pd.read_sql(query, engine)
            if df.empty:
                return df, None, False

            truncated = len(df) > SAFETY_ROW_CAP
            if truncated:
                df = df.iloc[:SAFETY_ROW_CAP]

            df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
            df["aqi_label"] = df["aqi"].map(AQI_LABELS)
            return df, None, truncated

        except SQLAlchemyError as e:
            last_error = str(e)
            if "SSL" in last_error or "closed" in last_error or "timeout" in last_error.lower():
                time.sleep(2 * (attempt + 1))
                continue
            break
        except Exception as e:
            last_error = str(e)
            time.sleep(2 * (attempt + 1))
            continue

    return None, last_error or "Loading failed after several attempts.", False


# ---------- AQI helper functions ----------
def get_aqi_color(aqi_value: float) -> str:
    if aqi_value <= 1:
        return AQI_COLORS["Good"]
    elif aqi_value <= 2:
        return AQI_COLORS["Fair"]
    elif aqi_value <= 3:
        return AQI_COLORS["Moderate"]
    elif aqi_value <= 4:
        return AQI_COLORS["Poor"]
    return AQI_COLORS["Very Poor"]


# ---------- Application ----------
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

df, load_error, truncated = load_data()

st.markdown(
    """
    <div class="app-header">
        <div class="eyebrow">DataGreen · MangaRivotra</div>
        <h1>AQI Data Warehouse</h1>
        <p>Air quality monitoring — Airflow pipeline / Postgres warehouse</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if load_error is not None:
    st.error(f"**Unable to load data**\n\n{load_error}")
    st.info(
        "Check that:\n"
        "- `DATABASE_URL` is defined in `.env` (local) or `.streamlit/secrets.toml` (deployment)\n"
        "- The Neon warehouse is reachable from your network\n"
        "- The `fact_air_quality`, `dim_city`, `dim_time` tables contain data"
    )
    st.stop()

if df is None or df.empty:
    st.warning("No data available in the warehouse at this time.")
    st.stop()

if truncated:
    st.warning(
        f"The warehouse contains more than {SAFETY_ROW_CAP:,} rows: "
        f"only the first {SAFETY_ROW_CAP:,} were loaded to stay responsive. "
        "Narrow the period in the sidebar if you want to refine the results."
    )

# ---------- SIDEBAR (completely redesigned) ----------
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="dot"></div>
            <div class="brand-text">
                <div class="brand-title">DATAGREEN</div>
                <div class="brand-sub">AQI Warehouse Console</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cities = sorted(df["city_name"].unique())
    date_min = df["timestamp_utc"].min().date()
    date_max = df["timestamp_utc"].max().date()

    # === FILTER 1: Cities ===
    st.markdown(
        f"""
        <div class="filter-section">
            <div class="filter-label">
                <span class="icon">🏙️</span> Cities
                <span class="badge-count">{len(df['city_name'].unique())} available</span>
            </div>
        """,
        unsafe_allow_html=True,
    )
    selected_cities = st.multiselect(
        "Select cities to display",
        cities,
        default=cities,
        label_visibility="collapsed",
        help="Filter data by one or more cities",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # === FILTER 2: Period ===
    st.markdown(
        f"""
        <div class="filter-section">
            <div class="filter-label">
                <span class="icon">📅</span> Period
                <span class="badge-count">{date_min} → {date_max}</span>
            </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", date_min, min_value=date_min, max_value=date_max, label_visibility="collapsed")
    with col2:
        end_date = st.date_input("To", date_max, min_value=date_min, max_value=date_max, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    # === FILTER 3: AQI Range ===
    aqi_lo, aqi_hi = float(df["aqi"].min()), float(df["aqi"].max())
    if aqi_lo == aqi_hi:
        aqi_lo, aqi_hi = aqi_lo - 0.5, aqi_hi + 0.5

    st.markdown(
        f"""
        <div class="filter-section">
            <div class="filter-label">
                <span class="icon">📊</span> AQI Range
                <span class="badge-count">{aqi_lo:.1f} – {aqi_hi:.1f}</span>
            </div>
        """,
        unsafe_allow_html=True,
    )
    aqi_min, aqi_max = st.slider(
        "Select AQI range",
        min_value=aqi_lo,
        max_value=aqi_hi,
        value=(aqi_lo, aqi_hi),
        label_visibility="collapsed",
        help="Filter readings by AQI value",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # === FILTER 4: Pollutants (collapsible) ===
    st.markdown(
        f"""
        <div class="filter-section">
            <div class="filter-label">
                <span class="icon">🧪</span> Pollutants
                <span class="badge-count">{len(POLLUTANTS)} available</span>
            </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Select pollutants to display", expanded=False):
        selected_pollutants = st.multiselect(
            "Pollutants",
            POLLUTANTS,
            default=["pm2_5", "pm10", "no2", "o3"],
            label_visibility="collapsed",
            help="Choose which pollutants to include in tables and charts",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # === Apply filters ===
    filtered = df[df["city_name"].isin(selected_cities)]
    filtered = filtered[
        (filtered["timestamp_utc"].dt.date >= start_date) & 
        (filtered["timestamp_utc"].dt.date <= end_date)
    ]
    filtered = filtered[(filtered["aqi"] >= aqi_min) & (filtered["aqi"] <= aqi_max)]

    # === SIDEBAR: Quick stats (compact) ===
    if not filtered.empty:
        avg_aqi = filtered["aqi"].mean()
        max_aqi = filtered["aqi"].max()
        avg_color = get_aqi_color(avg_aqi)
        max_color = get_aqi_color(max_aqi)

        st.markdown(
            f"""
            <div style="background:var(--bg); border:1px solid var(--border); border-radius:8px; padding:0.85rem 1rem; margin-top:0.25rem;">
                <div style="font-family:'JetBrains Mono',monospace; font-size:0.6rem; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-muted); margin-bottom:0.6rem;">
                    ⚡ Quick stats
                </div>
                <div class="sidebar-stats">
                    <div class="sidebar-stat">
                        <div class="stat-num">{len(filtered):,}</div>
                        <div class="stat-label">Readings</div>
                    </div>
                    <div class="sidebar-stat">
                        <div class="stat-num">{filtered['city_name'].nunique()}</div>
                        <div class="stat-label">Cities</div>
                    </div>
                    <div class="sidebar-stat" style="border-left:2px solid {avg_color};">
                        <div class="stat-num" style="color:{avg_color};">{avg_aqi:.2f}</div>
                        <div class="stat-label">Avg AQI</div>
                    </div>
                    <div class="sidebar-stat" style="border-left:2px solid {max_color};">
                        <div class="stat-num" style="color:{max_color};">{max_aqi:.2f}</div>
                        <div class="stat-label">Max AQI</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # === SIDEBAR: Status bar ===
    last_update = df["timestamp_utc"].max()
    total_rows = len(df)
    total_cities = df["city_name"].nunique()

    st.markdown(
        f"""
        <div class="sidebar-status">
            <div class="status-row">
                <span><span class="status-dot"></span>Warehouse online</span>
                <span>{total_rows:,} rows</span>
            </div>
            <div class="status-row">
                <span>🌍 {total_cities} cities</span>
                <span>📡 {last_update.strftime('%d/%m/%Y %H:%M')} UTC</span>
            </div>
            <div class="status-row" style="color:var(--accent); font-size:0.55rem; margin-top:0.2rem;">
                <span>◆ {start_date} → {end_date}</span>
                <span>{len(selected_cities)}/{total_cities} cities</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------- Check filtered data ----------
if filtered.empty:
    st.warning("No data matches the selected filters.")
    st.stop()

# ---------- Key metrics ----------
st.markdown('<div class="section-label">Overview</div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(
        f"""<div class="metric-card"><div class="label">Total readings</div>
        <div class="value">{len(filtered):,}</div></div>""",
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""<div class="metric-card"><div class="label">Cities</div>
        <div class="value">{filtered['city_name'].nunique()}</div></div>""",
        unsafe_allow_html=True,
    )

with col3:
    avg_aqi = filtered["aqi"].mean()
    color = get_aqi_color(avg_aqi)
    st.markdown(
        f"""<div class="metric-card" style="border-left-color: {color};">
        <div class="label">Avg AQI</div>
        <div class="value" style="color: {color};">{avg_aqi:.2f}</div></div>""",
        unsafe_allow_html=True,
    )

with col4:
    max_aqi = filtered["aqi"].max()
    color = get_aqi_color(max_aqi)
    st.markdown(
        f"""<div class="metric-card" style="border-left-color: {color};">
        <div class="label">Max AQI</div>
        <div class="value" style="color: {color};">{max_aqi:.2f}</div></div>""",
        unsafe_allow_html=True,
    )

with col5:
    best_city = filtered.groupby("city_name")["aqi"].mean().idxmin()
    best_aqi = filtered.groupby("city_name")["aqi"].mean().min()
    color = get_aqi_color(best_aqi)
    st.markdown(
        f"""<div class="metric-card" style="border-left-color: {color};">
        <div class="label">Cleanest city</div>
        <div class="value" style="font-size: 1.15rem;">{best_city}</div>
        <div class="change">AQI {best_aqi:.2f}</div></div>""",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ---------- Tabs ----------
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Overview",
    "🏙️ Cities",
    "📈 Time Trends",
    "🔗 Correlations",
    "📅 Seasonal",
    "⚠️ Anomalies",
    "✅ Data Quality",
    "📋 Raw Data"
])

with tab1:
    """Overview: geographic map and AQI distribution"""
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown('<div class="section-label">City map</div>', unsafe_allow_html=True)
        city_points = filtered.dropna(subset=["latitude", "longitude"]).drop_duplicates("city_name")[
            ["city_name", "latitude", "longitude"]
        ]
        city_avg = filtered.groupby("city_name")["aqi"].mean().reset_index()
        city_points = city_points.merge(city_avg, on="city_name")

        if city_points.empty:
            st.info("No geographic coordinates available for the selected cities.")
        else:
            fig_map = px.scatter_geo(
                city_points, lat="latitude", lon="longitude", hover_name="city_name",
                size="aqi", color="aqi", color_continuous_scale="RdYlGn_r",
                projection="natural earth",
            )
            fig_map.update_layout(height=480, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_map, use_container_width=True)

    with col2:
        st.markdown('<div class="section-label">AQI distribution</div>', unsafe_allow_html=True)
        aqi_dist = filtered["aqi_label"].value_counts().reset_index()
        aqi_dist.columns = ["Category", "Count"]

        fig_pie = px.pie(
            aqi_dist, values="Count", names="Category", color="Category",
            color_discrete_map=AQI_COLORS, hole=0.55,
        )
        fig_pie.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown('<div class="section-label">Top 5 cleanest cities</div>', unsafe_allow_html=True)
        best_cities = filtered.groupby("city_name")["aqi"].mean().sort_values().head(5)
        for city, aqi in best_cities.items():
            st.markdown(
                f"""<div class="rank-row"><span>{city}</span>
                <span class="rank-value" style="color:{get_aqi_color(aqi)};">{aqi:.2f}</span></div>""",
                unsafe_allow_html=True,
            )

with tab2:
    """Detailed city comparison"""
    st.markdown('<div class="section-label">City comparison</div>', unsafe_allow_html=True)

    city_stats = filtered.groupby("city_name").agg(
        {"aqi": ["mean", "min", "max", "std"], "timestamp_utc": "count"}
    ).round(2)
    city_stats.columns = ["Avg AQI", "Min AQI", "Max AQI", "Std dev", "Readings"]
    city_stats = city_stats.sort_values("Avg AQI")

    st.dataframe(city_stats, use_container_width=True)

    fig_city_bar = px.bar(
        city_stats.reset_index(), x="city_name", y="Avg AQI",
        color="Avg AQI", color_continuous_scale="RdYlGn_r",
        title="Average AQI by city",
    )
    st.plotly_chart(fig_city_bar, use_container_width=True)

    fig_box = px.box(filtered, x="city_name", y="aqi", color="city_name",
                     title="AQI distribution by city")
    st.plotly_chart(fig_box, use_container_width=True)

with tab3:
    """Time trends: time series, hourly profiles, weekday vs weekend"""
    st.markdown('<div class="section-label">Time trends</div>', unsafe_allow_html=True)

    trend_cities = st.multiselect(
        "Cities for trends", selected_cities,
        default=selected_cities[:3] if len(selected_cities) > 3 else selected_cities,
        key="trend_cities"
    )

    if trend_cities:
        trend_data = filtered[filtered["city_name"].isin(trend_cities)]

        daily = (
            trend_data.set_index("timestamp_utc")
            .groupby("city_name")["aqi"]
            .resample("1D").mean()
            .reset_index()
        )
        daily["aqi_smooth"] = daily.groupby("city_name")["aqi"].transform(
            lambda s: s.rolling(7, min_periods=1).mean()
        )

        fig_trend = px.line(
            daily, x="timestamp_utc", y="aqi_smooth", color="city_name",
            labels={"aqi_smooth": "AQI (7-day rolling avg)", "timestamp_utc": "Date"},
            title="AQI trend (7-day rolling average)"
        )
        fig_trend.update_layout(height=380)
        st.plotly_chart(fig_trend, use_container_width=True)

        st.markdown('<div class="section-label">Hourly profile (day/night cycle)</div>', unsafe_allow_html=True)
        hourly_pivot = trend_data.pivot_table(index="hour", columns="city_name", values="aqi", aggfunc="mean")
        fig_heatmap = px.imshow(
            hourly_pivot, 
            labels=dict(x="City", y="Hour (UTC)", color="AQI"),
            color_continuous_scale="RdYlGn_r",
            title="Average AQI by hour of day"
        )
        fig_heatmap.update_layout(height=380)
        st.plotly_chart(fig_heatmap, use_container_width=True)

        st.markdown('<div class="section-label">Weekday vs Weekend</div>', unsafe_allow_html=True)
        wk = trend_data.groupby(["city_name", "is_weekend"])["aqi"].mean().reset_index()
        wk["period"] = wk["is_weekend"].map({True: "Weekend", False: "Weekday", 1: "Weekend", 0: "Weekday"})

        fig_wk = px.bar(
            wk, x="city_name", y="aqi", color="period", barmode="group",
            title="Average AQI: weekday vs weekend"
        )
        st.plotly_chart(fig_wk, use_container_width=True)
    else:
        st.info("Select at least one city to see the trends.")

with tab4:
    """Pollutant correlations"""
    st.markdown('<div class="section-label">Pollutant correlations</div>', unsafe_allow_html=True)

    variables = ["aqi"] + POLLUTANTS
    corr_pollutants = st.multiselect(
        "Pollutants for the correlation matrix", variables,
        default=["aqi", "pm2_5", "pm10", "no2", "o3", "co"],
        key="corr_pollutants"
    )

    if len(corr_pollutants) >= 2:
        corr_data = filtered[corr_pollutants].corr()
        fig_corr = px.imshow(
            corr_data, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
            title="Correlation matrix"
        )
        fig_corr.update_layout(height=480)
        st.plotly_chart(fig_corr, use_container_width=True)

        if "aqi" in corr_pollutants:
            st.markdown('<div class="section-label">Correlation with AQI — significance</div>', unsafe_allow_html=True)
            sig_rows = []
            for col in [c for c in corr_pollutants if c != "aqi"]:
                valid = filtered[["aqi", col]].dropna()
                if len(valid) >= 3:
                    r, p = pearsonr(valid["aqi"], valid[col])
                    sig_rows.append({"pollutant": col, "r": r, "p_value": p, "significant (p<0.05)": p < 0.05})
            if sig_rows:
                sig_df = pd.DataFrame(sig_rows).assign(abs_r=lambda d: d["r"].abs()) \
                    .sort_values("abs_r", ascending=False).drop(columns="abs_r").set_index("pollutant")
                st.dataframe(sig_df.round(4), use_container_width=True)
            st.caption(
                "With this many readings, p-values are almost always significant even for weak "
                "correlations — judge relevance from |r|, not from significance alone. Also note "
                "the AQI index is itself derived from a subset of these pollutants (mainly PM2.5/PM10), "
                "so a strong correlation partly reflects the index's own formula rather than an "
                "independent finding."
            )

        st.markdown('<div class="section-label">Bivariate analysis</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            x_var = st.selectbox("X variable", variables, index=0, key="x_var")
        with col2:
            default_idx = min(5, len(variables) - 1)
            y_var = st.selectbox("Y variable", variables, index=default_idx, key="y_var")

        fig_scatter = px.scatter(
            filtered, x=x_var, y=y_var, color="city_name", opacity=0.55, trendline="ols",
            title=f"Relationship between {x_var} and {y_var}"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Select at least 2 pollutants to see the correlations.")

with tab5:
    """Seasonal and monthly trends"""
    st.markdown('<div class="section-label">Seasonal & monthly trends</div>', unsafe_allow_html=True)
    st.caption(
        "Hourly data is noisy — we smooth it with a 7-day rolling average and aggregate by month to see the underlying trend."
    )

    seasonal_cities = st.multiselect(
        "Cities for seasonal view", selected_cities,
        default=selected_cities, key="seasonal_cities",
    )

    if seasonal_cities:
        seasonal_data = filtered[filtered["city_name"].isin(seasonal_cities)].copy()
        seasonal_data["month"] = seasonal_data["timestamp_utc"].dt.tz_localize(None).dt.to_period("M").astype(str)

        daily_season = seasonal_data.groupby(["city_name", "date"])["aqi"].mean().reset_index()
        daily_season = daily_season.sort_values("date")
        daily_season["aqi_smooth"] = daily_season.groupby("city_name")["aqi"].transform(
            lambda s: s.rolling(7, min_periods=1).mean()
        )

        fig_rolling = px.line(
            daily_season, x="date", y="aqi_smooth", color="city_name",
            labels={"aqi_smooth": "AQI (7-day rolling avg)", "date": "Date"},
            title="Daily AQI trend (7-day rolling average)"
        )
        fig_rolling.update_layout(height=380)
        st.plotly_chart(fig_rolling, use_container_width=True)

        st.markdown('<div class="section-label">Monthly average AQI</div>', unsafe_allow_html=True)
        monthly = seasonal_data.groupby(["city_name", "month"])["aqi"].mean().reset_index()
        fig_monthly = px.bar(
            monthly, x="month", y="aqi", color="city_name", barmode="group",
            title="Monthly average AQI"
        )
        fig_monthly.update_layout(height=380)
        st.plotly_chart(fig_monthly, use_container_width=True)

        monthly_pivot = monthly.pivot(index="month", columns="city_name", values="aqi").round(1)
        st.dataframe(monthly_pivot, use_container_width=True)
    else:
        st.info("Select at least one city to see seasonal trends.")

with tab6:
    """Multivariate anomaly detection"""
    st.markdown('<div class="section-label">Anomaly detection</div>', unsafe_allow_html=True)
    st.caption(
        "A real pollution event usually moves several pollutants together, so scoring PM2.5 alone "
        "misses spikes that show up mainly in NO2, O3 or CO — and can flag a single noisy sensor as "
        "a \"real\" event. We compute a rolling z-score per pollutant and flag a reading when any one "
        "of them crosses the threshold; 'pollutants in agreement' shows how many moved together, "
        "which is a stronger signal than a single-pollutant flag."
    )

    ANOMALY_COLUMNS = ["pm2_5", "pm10", "no2", "o3", "co"]

    col1, col2, col3 = st.columns([1, 1, 1.4])
    with col1:
        anomaly_window = st.slider(
            "Rolling window (hours)", min_value=6, max_value=72, value=24, step=6,
            help="Window duration for z-score calculation"
        )
    with col2:
        anomaly_threshold = st.slider(
            "Z-score threshold", min_value=1.5, max_value=5.0, value=3.0, step=0.5,
            help="Threshold above which a value is considered anomalous"
        )
    with col3:
        anomaly_columns = st.multiselect(
            "Pollutants included", ANOMALY_COLUMNS, default=ANOMALY_COLUMNS,
            help="Pollutants to monitor for anomaly detection"
        )

    chance_pct = 2 * norm.sf(anomaly_threshold) * 100
    st.caption(
        f"For a roughly normal distribution, |z| > {anomaly_threshold:.1f} flags about {chance_pct:.2f}% "
        "of points by chance on a single pollutant — testing several independently raises the odds of "
        "at least one false flag, which is why 'pollutants in agreement ≥ 2' is a more trustworthy filter "
        "than any single flagged pollutant."
    )

    def flag_anomalies_multivariate(g, columns, window=24, threshold=3):
        g = g.sort_values("timestamp_utc").copy()
        z_cols = []
        for col in columns:
            rolling_mean = g[col].rolling(window, min_periods=5).mean()
            rolling_std = g[col].rolling(window, min_periods=5).std()
            z = (g[col] - rolling_mean) / rolling_std
            z = z.replace([np.inf, -np.inf], np.nan)
            g[f"z_{col}"] = z
            z_cols.append(f"z_{col}")
        g["z_max"] = g[z_cols].abs().max(axis=1) if z_cols else np.nan
        g["n_pollutants_flagged"] = (g[z_cols].abs() > threshold).sum(axis=1) if z_cols else 0
        g["is_anomaly"] = g["z_max"] > threshold if z_cols else False
        return g

    if not anomaly_columns:
        st.info("Select at least one pollutant to run anomaly detection.")
    else:
        df_anomalies = filtered.groupby("city_name", group_keys=False)[filtered.columns].apply(
            lambda g: flag_anomalies_multivariate(g, anomaly_columns, window=anomaly_window, threshold=anomaly_threshold)
        )
        anomalies = df_anomalies[df_anomalies["is_anomaly"]].sort_values("timestamp_utc")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(
                f"""<div class="metric-card"><div class="label">Anomalies flagged</div>
                <div class="value">{len(anomalies):,}</div></div>""",
                unsafe_allow_html=True,
            )
        with m2:
            pct = len(anomalies) / len(filtered) * 100 if len(filtered) else 0
            st.markdown(
                f"""<div class="metric-card"><div class="label">Share of readings</div>
                <div class="value">{pct:.2f}%</div></div>""",
                unsafe_allow_html=True,
            )
        with m3:
            agree_2plus = int((anomalies["n_pollutants_flagged"] >= 2).sum()) if len(anomalies) else 0
            st.markdown(
                f"""<div class="metric-card"><div class="label">Flagged on 2+ pollutants</div>
                <div class="value">{agree_2plus:,}</div></div>""",
                unsafe_allow_html=True,
            )
        with m4:
            worst_city = anomalies["city_name"].value_counts().idxmax() if len(anomalies) else "—"
            st.markdown(
                f"""<div class="metric-card"><div class="label">Most affected city</div>
                <div class="value" style="font-size: 1.15rem;">{worst_city}</div></div>""",
                unsafe_allow_html=True,
            )

        display_col = "pm2_5" if "pm2_5" in anomaly_columns else anomaly_columns[0]
        fig_anom = go.Figure()
        for city in df_anomalies["city_name"].unique():
            sub = df_anomalies[df_anomalies["city_name"] == city].sort_values("timestamp_utc")
            fig_anom.add_trace(go.Scatter(
                x=sub["timestamp_utc"], y=sub[display_col], mode="lines",
                name=city, opacity=0.5,
            ))
            anom_high = sub[(sub["is_anomaly"]) & (sub[f"z_{display_col}"] > 0)]
            anom_low = sub[(sub["is_anomaly"]) & (sub[f"z_{display_col}"] <= 0)]
            if len(anom_high):
                fig_anom.add_trace(go.Scatter(
                    x=anom_high["timestamp_utc"], y=anom_high[display_col], mode="markers",
                    marker=dict(color="#ef4444", size=6 + 4 * anom_high["n_pollutants_flagged"], symbol="triangle-up"),
                    name=f"{city} spike", showlegend=False,
                ))
            if len(anom_low):
                fig_anom.add_trace(go.Scatter(
                    x=anom_low["timestamp_utc"], y=anom_low[display_col], mode="markers",
                    marker=dict(color="#f97316", size=6 + 4 * anom_low["n_pollutants_flagged"], symbol="triangle-down"),
                    name=f"{city} dip", showlegend=False,
                ))
        fig_anom.update_layout(
            height=420, 
            yaxis_title=f"{display_col.upper()} (marker size = pollutants in agreement)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            title=f"Anomaly detection on {display_col.upper()}"
        )
        st.plotly_chart(fig_anom, use_container_width=True)

        st.markdown('<div class="section-label">Anomalies by city</div>', unsafe_allow_html=True)
        if len(anomalies):
            counts = anomalies["city_name"].value_counts()
            totals = df_anomalies["city_name"].value_counts()
            summary = pd.DataFrame({"anomalies": counts, "total_points": totals})
            summary["pct"] = (summary["anomalies"] / summary["total_points"] * 100).round(2)
            summary = summary.sort_values("pct", ascending=False)
            st.dataframe(summary, use_container_width=True)

            with st.expander("View flagged readings"):
                display_cols = ["city_name", "timestamp_utc"] + anomaly_columns + ["aqi", "z_max", "n_pollutants_flagged"]
                st.dataframe(
                    anomalies[display_cols],
                    use_container_width=True, height=300,
                )
        else:
            st.info("No anomalies detected at the current window/threshold.")

with tab7:
    """Data quality checks"""
    st.markdown('<div class="section-label">Data quality</div>', unsafe_allow_html=True)
    st.caption(
        "What's actually in the warehouse for the current filters: missing values, duplicates, gaps in the hourly cadence, and out-of-range readings."
    )

    q1, q2, q3 = st.columns(3)

    missing = filtered[POLLUTANTS + ["aqi"]].isna().sum()
    missing_pct_total = (missing.sum() / (len(filtered) * (len(POLLUTANTS) + 1)) * 100) if len(filtered) else 0
    dupes = filtered.duplicated(subset=["city_name", "timestamp_utc"]).sum()
    dupes_pct = (dupes / len(filtered) * 100) if len(filtered) else 0
    negatives = int((filtered[POLLUTANTS + ["aqi"]] < 0).sum().sum())

    with q1:
        st.markdown(
            f"""<div class="metric-card"><div class="label">Missing values</div>
            <div class="value">{missing_pct_total:.2f}%</div></div>""",
            unsafe_allow_html=True,
        )
    with q2:
        st.markdown(
            f"""<div class="metric-card"><div class="label">Duplicate (city, timestamp)</div>
            <div class="value">{dupes:,}</div></div>""",
            unsafe_allow_html=True,
        )
    with q3:
        st.markdown(
            f"""<div class="metric-card"><div class="label">Negative pollutant values</div>
            <div class="value">{negatives:,}</div></div>""",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-label">Missing values per column</div>', unsafe_allow_html=True)
    missing_df = pd.DataFrame({"missing": missing, "pct": (missing / len(filtered) * 100).round(2) if len(filtered) else missing})
    st.dataframe(missing_df[missing_df["missing"] > 0] if missing.sum() else missing_df, use_container_width=True)

    st.markdown('<div class="section-label">Hourly continuity per city</div>', unsafe_allow_html=True)

    quality_sorted = filtered.sort_values(["city_name", "timestamp_utc"])
    diffs_by_city = quality_sorted.groupby("city_name")["timestamp_utc"].diff()
    expected = pd.Timedelta(hours=1)
    gaps_report = pd.DataFrame({
        "n_points": quality_sorted.groupby("city_name").size(),
        "gaps": (diffs_by_city > expected).groupby(quality_sorted["city_name"]).sum(),
        "max_gap": diffs_by_city.groupby(quality_sorted["city_name"]).max().astype(str),
    })
    st.dataframe(gaps_report, use_container_width=True)

    st.markdown('<div class="section-label">Descriptive statistics</div>', unsafe_allow_html=True)
    st.dataframe(filtered[POLLUTANTS + ["aqi"]].describe().T.round(2), use_container_width=True)

with tab8:
    """Raw data export"""
    st.markdown('<div class="section-label">Raw data</div>', unsafe_allow_html=True)

    page_size = st.selectbox("Rows per page", [10, 25, 50, 100], index=1)
    total_rows = len(filtered)
    total_pages = max(1, (total_rows - 1) // page_size + 1)

    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)

    display_cols = ["city_name", "timestamp_utc", "aqi", "aqi_label"] + selected_pollutants
    display_cols = [col for col in display_cols if col in filtered.columns]

    st.dataframe(filtered[display_cols].iloc[start_idx:end_idx], use_container_width=True, height=400)

    csv = filtered[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download (CSV)", data=csv,
        file_name=f"aqi_data_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
    )

# ---------- Footer ----------
st.markdown(
    f"""
    <div class="footer">
        AQI DATA WAREHOUSE — {len(df):,} TOTAL ROWS · {df['city_name'].nunique()} CITIES ·
        LATEST READING {df["timestamp_utc"].max().strftime('%d/%m/%Y %H:%M')} UTC ·
        POWERED BY OPENWEATHERMAP / AIRFLOW / POSTGRES
    </div>
    """,
    unsafe_allow_html=True,
)