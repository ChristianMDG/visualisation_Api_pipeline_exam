"""
AQI Data Warehouse — Interactive Dashboard (Streamlit)

Console de monitoring de la qualité de l'air : connexion robuste au warehouse
PostgreSQL (Neon), navigation par onglets, filtres avancés, design sombre
technique (Inter + JetBrains Mono).
"""
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ---------- Configuration de la page ----------
st.set_page_config(
    page_title="AQI Data Warehouse",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Thème Plotly global : toutes les figures px.* héritent de ce template sombre
px.defaults.template = "plotly_dark"

# ---------- Constantes ----------
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

# ---------- Style : console technique sombre ----------
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
    }

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
    .stApp { background: var(--bg); }

    /* En-tête */
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

    /* Cards métriques */
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

    /* Badges AQI (contour, pas de remplissage) */
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

    /* Lignes de classement */
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
    }
    .stTabs [aria-selected="true"] { color: var(--accent) !important; }

    /* Dataframes / metrics natifs Streamlit */
    [data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; }

    /* Footer */
    .footer {
        padding: 1.25rem 0 0.5rem 0;
        border-top: 1px solid var(--border);
        margin-top: 2rem;
        color: var(--text-muted);
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
    }

    /* ===== Sidebar ===== */
    section[data-testid="stSidebar"] {
        background: var(--surface);
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] > div { padding-top: 0.5rem; }

    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding-bottom: 1rem;
        margin-bottom: 1.1rem;
        border-bottom: 1px solid var(--border);
    }
    .sidebar-brand .dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: var(--accent);
        box-shadow: 0 0 8px var(--accent);
        flex-shrink: 0;
    }
    .sidebar-brand .brand-text { display: flex; flex-direction: column; line-height: 1.2; }
    .sidebar-brand .brand-title {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--text);
        letter-spacing: 0.02em;
    }
    .sidebar-brand .brand-sub {
        font-size: 0.68rem;
        color: var(--text-muted);
    }

    /* Cards natives st.container(border=True) dans la sidebar */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--bg);
        border: 1px solid var(--border) !important;
        border-radius: 8px;
        margin-bottom: 0.85rem;
    }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] > div {
        padding: 0.9rem 0.95rem;
    }

    .sidebar-card-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.66rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: 0.65rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    .sidebar-card-label::before {
        content: "";
        width: 3px; height: 12px;
        background: var(--accent);
        border-radius: 2px;
        display: inline-block;
    }

    /* Widgets : multiselect, selectbox, date input */
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] input {
        background: var(--surface) !important;
        border-color: var(--border) !important;
        color: var(--text) !important;
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
    }
    section[data-testid="stSidebar"] [data-baseweb="tag"] {
        background: rgba(91, 141, 239, 0.18) !important;
        border: 1px solid var(--accent) !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="tag"] span { color: var(--text) !important; }

    /* Slider */
    section[data-testid="stSidebar"] [data-testid="stSlider"] div[role="slider"] {
        background-color: var(--accent) !important;
        box-shadow: 0 0 0 4px rgba(91, 141, 239, 0.18);
    }

    /* Expander */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 8px;
    }
    section[data-testid="stSidebar"] summary {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        color: var(--text-muted);
    }

    /* Mini stats grid */
    .stat-mini {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 0.55rem 0.65rem;
    }
    .stat-mini .stat-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.6rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .stat-mini .stat-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--text);
        margin-top: 0.15rem;
    }

    .sidebar-footnote {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        color: var(--text-muted);
        line-height: 1.5;
        padding: 0.6rem 0.1rem 0 0.1rem;
    }
    .sidebar-footnote .live-dot {
        display: inline-block;
        width: 6px; height: 6px;
        border-radius: 50%;
        background: #22c55e;
        margin-right: 0.35rem;
        box-shadow: 0 0 6px #22c55e;
    }

    /* Scrollbar sidebar */
    section[data-testid="stSidebar"] ::-webkit-scrollbar { width: 6px; }
    section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
        background: var(--border); border-radius: 3px;
    }

    @media (max-width: 768px) {
        .app-header h1 { font-size: 1.3rem; }
        .metric-card .value { font-size: 1.3rem; }
    }
</style>
"""


# ---------- Connexion à la base de données ----------
def get_database_url():
    """Cherche DATABASE_URL dans st.secrets (déploiement) puis dans .env (local)."""
    load_dotenv()
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        # st.secrets lève une exception si aucun fichier secrets.toml n'existe.
        # C'est normal en local : on retombe sur la variable d'environnement.
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


# ---------- Chargement des données ----------
# IMPORTANT : pas de fenêtre de date ni de LIMIT côté SQL par défaut -> on charge
# TOUT le warehouse. Le filtrage par période se fait ensuite côté sidebar (client).
# Un plafond de sécurité (SAFETY_ROW_CAP) évite juste une requête runaway si le
# pipeline tourne depuis très longtemps.
SAFETY_ROW_CAP = 1_000_000


@st.cache_data(ttl=600, show_spinner="Chargement des données du warehouse...")
def load_data():
    """
    Charge TOUTES les lignes du warehouse, avec retry sur erreurs transitoires.
    Retourne (df, error_message, truncated). error_message est None si tout va bien.
    truncated est True si le plafond de sécurité a été atteint.
    """
    engine = get_engine()
    if engine is None:
        return None, "DATABASE_URL introuvable (ni dans st.secrets, ni dans .env).", False

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
                time.sleep(2 * (attempt + 1))  # backoff progressif
                continue
            break  # erreur non transitoire (ex: SQL invalide) -> inutile de retenter
        except Exception as e:
            last_error = str(e)
            time.sleep(2 * (attempt + 1))
            continue

    return None, last_error or "Échec de chargement après plusieurs tentatives.", False


# ---------- Fonctions utilitaires AQI ----------
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


def get_aqi_badge(aqi_label: str) -> str:
    classes = {
        "Good": "aqi-good",
        "Fair": "aqi-fair",
        "Moderate": "aqi-moderate",
        "Poor": "aqi-poor",
        "Very Poor": "aqi-very-poor",
    }
    return f'<span class="aqi-badge {classes.get(aqi_label, "")}">{aqi_label}</span>'


# ---------- Application ----------
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

df, load_error, truncated = load_data()

st.markdown(
    """
    <div class="app-header">
        <div class="eyebrow">DataGreen · MangaRivotra</div>
        <h1>AQI Data Warehouse</h1>
        <p>Monitoring de la qualité de l'air — pipeline Airflow / warehouse Postgres</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if load_error is not None:
    st.error(f"**Impossible de charger les données**\n\n{load_error}")
    st.info(
        "Vérifiez que :\n"
        "- `DATABASE_URL` est défini dans `.env` (local) ou `.streamlit/secrets.toml` (déploiement)\n"
        "- Le warehouse Neon est accessible depuis votre réseau\n"
        "- Les tables `fact_air_quality`, `dim_city`, `dim_time` contiennent des données"
    )
    st.stop()

if df is None or df.empty:
    st.warning("Aucune donnée disponible dans le warehouse pour le moment.")
    st.stop()

if truncated:
    st.warning(
        f"Le warehouse contient plus de {SAFETY_ROW_CAP:,} lignes : "
        f"seules les {SAFETY_ROW_CAP:,} premières ont été chargées pour rester réactif. "
        "Réduis la période dans la sidebar si tu veux affiner."
    )

# ---------- Sidebar ----------
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

    with st.container(border=True):
        st.markdown('<div class="sidebar-card-label">Villes</div>', unsafe_allow_html=True)
        selected_cities = st.multiselect(
            "Villes", cities, default=cities, label_visibility="collapsed",
            help="Sélectionnez les villes à afficher",
        )

    with st.container(border=True):
        st.markdown('<div class="sidebar-card-label">Période</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Début", date_min, min_value=date_min, max_value=date_max)
        with col2:
            end_date = st.date_input("Fin", date_max, min_value=date_min, max_value=date_max)

    with st.container(border=True):
        st.markdown('<div class="sidebar-card-label">Filtres avancés</div>', unsafe_allow_html=True)
        with st.expander("AQI & polluants", expanded=False):
            aqi_lo, aqi_hi = float(df["aqi"].min()), float(df["aqi"].max())
            if aqi_lo == aqi_hi:
                # Un slider Streamlit exige min < max : on élargit artificiellement
                aqi_lo, aqi_hi = aqi_lo - 0.5, aqi_hi + 0.5
            aqi_min, aqi_max = st.slider("AQI Range", min_value=aqi_lo, max_value=aqi_hi, value=(aqi_lo, aqi_hi))

            selected_pollutants = st.multiselect(
                "Polluants à afficher", POLLUTANTS, default=["pm2_5", "pm10", "no2", "o3"]
            )

    filtered = df[df["city_name"].isin(selected_cities)]
    filtered = filtered[
        (filtered["timestamp_utc"].dt.date >= start_date) & (filtered["timestamp_utc"].dt.date <= end_date)
    ]
    filtered = filtered[(filtered["aqi"] >= aqi_min) & (filtered["aqi"] <= aqi_max)]

    if not filtered.empty:
        with st.container(border=True):
            st.markdown('<div class="sidebar-card-label">Aperçu filtré</div>', unsafe_allow_html=True)
            s1, s2 = st.columns(2)
            with s1:
                st.markdown(
                    f"""<div class="stat-mini"><div class="stat-label">Mesures</div>
                    <div class="stat-value">{len(filtered):,}</div></div>""",
                    unsafe_allow_html=True,
                )
            with s2:
                st.markdown(
                    f"""<div class="stat-mini"><div class="stat-label">Villes</div>
                    <div class="stat-value">{filtered['city_name'].nunique()}</div></div>""",
                    unsafe_allow_html=True,
                )
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            s3, s4 = st.columns(2)
            avg_c = get_aqi_color(filtered["aqi"].mean())
            max_c = get_aqi_color(filtered["aqi"].max())
            with s3:
                st.markdown(
                    f"""<div class="stat-mini" style="border-left:2px solid {avg_c};">
                    <div class="stat-label">AQI moyen</div>
                    <div class="stat-value" style="color:{avg_c};">{filtered['aqi'].mean():.2f}</div></div>""",
                    unsafe_allow_html=True,
                )
            with s4:
                st.markdown(
                    f"""<div class="stat-mini" style="border-left:2px solid {max_c};">
                    <div class="stat-label">AQI max</div>
                    <div class="stat-value" style="color:{max_c};">{filtered['aqi'].max():.2f}</div></div>""",
                    unsafe_allow_html=True,
                )

    last_update = df["timestamp_utc"].max()
    st.markdown(
        f"""
        <div class="sidebar-footnote">
            <div><span class="live-dot"></span>Warehouse connecté</div>
            <div>{len(df):,} lignes · {df['city_name'].nunique()} villes</div>
            <div>Dernière ingestion : {last_update.strftime('%d/%m/%Y %H:%M')} UTC</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if filtered.empty:
    st.warning("Aucune donnée ne correspond aux filtres sélectionnés.")
    st.stop()

# ---------- Métriques principales ----------
st.markdown('<div class="section-label">Vue d\'ensemble</div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(
        f"""<div class="metric-card"><div class="label">Total mesures</div>
        <div class="value">{len(filtered):,}</div></div>""",
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""<div class="metric-card"><div class="label">Villes</div>
        <div class="value">{filtered['city_name'].nunique()}</div></div>""",
        unsafe_allow_html=True,
    )

with col3:
    avg_aqi = filtered["aqi"].mean()
    color = get_aqi_color(avg_aqi)
    st.markdown(
        f"""<div class="metric-card" style="border-left-color: {color};">
        <div class="label">AQI moyen</div>
        <div class="value" style="color: {color};">{avg_aqi:.2f}</div></div>""",
        unsafe_allow_html=True,
    )

with col4:
    max_aqi = filtered["aqi"].max()
    color = get_aqi_color(max_aqi)
    st.markdown(
        f"""<div class="metric-card" style="border-left-color: {color};">
        <div class="label">AQI max</div>
        <div class="value" style="color: {color};">{max_aqi:.2f}</div></div>""",
        unsafe_allow_html=True,
    )

with col5:
    best_city = filtered.groupby("city_name")["aqi"].mean().idxmin()
    best_aqi = filtered.groupby("city_name")["aqi"].mean().min()
    color = get_aqi_color(best_aqi)
    st.markdown(
        f"""<div class="metric-card" style="border-left-color: {color};">
        <div class="label">Meilleure ville</div>
        <div class="value" style="font-size: 1.15rem;">{best_city}</div>
        <div class="change">AQI {best_aqi:.2f}</div></div>""",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ---------- Tabs ----------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Overview", "Villes", "Tendances", "Corrélations", "Données"]
)

with tab1:
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown('<div class="section-label">Carte des villes</div>', unsafe_allow_html=True)
        city_points = filtered.dropna(subset=["latitude", "longitude"]).drop_duplicates("city_name")[
            ["city_name", "latitude", "longitude"]
        ]
        city_avg = filtered.groupby("city_name")["aqi"].mean().reset_index()
        city_points = city_points.merge(city_avg, on="city_name")

        if city_points.empty:
            st.info("Aucune coordonnée géographique disponible pour les villes sélectionnées.")
        else:
            fig_map = px.scatter_geo(
                city_points, lat="latitude", lon="longitude", hover_name="city_name",
                size="aqi", color="aqi", color_continuous_scale="RdYlGn_r",
                projection="natural earth",
            )
            fig_map.update_layout(height=480, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_map, use_container_width=True)

    with col2:
        st.markdown('<div class="section-label">Distribution AQI</div>', unsafe_allow_html=True)
        aqi_dist = filtered["aqi_label"].value_counts().reset_index()
        aqi_dist.columns = ["Category", "Count"]

        fig_pie = px.pie(
            aqi_dist, values="Count", names="Category", color="Category",
            color_discrete_map=AQI_COLORS, hole=0.55,
        )
        fig_pie.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown('<div class="section-label">Top 5 villes les plus propres</div>', unsafe_allow_html=True)
        best_cities = filtered.groupby("city_name")["aqi"].mean().sort_values().head(5)
        for city, aqi in best_cities.items():
            st.markdown(
                f"""<div class="rank-row"><span>{city}</span>
                <span class="rank-value" style="color:{get_aqi_color(aqi)};">{aqi:.2f}</span></div>""",
                unsafe_allow_html=True,
            )

with tab2:
    st.markdown('<div class="section-label">Comparaison des villes</div>', unsafe_allow_html=True)

    city_stats = filtered.groupby("city_name").agg(
        {"aqi": ["mean", "min", "max", "std"], "timestamp_utc": "count"}
    ).round(2)
    city_stats.columns = ["AQI moyen", "AQI min", "AQI max", "Écart-type", "Mesures"]
    city_stats = city_stats.sort_values("AQI moyen")

    st.dataframe(city_stats, use_container_width=True)

    fig_city_bar = px.bar(
        city_stats.reset_index(), x="city_name", y="AQI moyen",
        color="AQI moyen", color_continuous_scale="RdYlGn_r",
    )
    st.plotly_chart(fig_city_bar, use_container_width=True)

    fig_box = px.box(filtered, x="city_name", y="aqi", color="city_name")
    st.plotly_chart(fig_box, use_container_width=True)

with tab3:
    st.markdown('<div class="section-label">Évolution temporelle</div>', unsafe_allow_html=True)

    trend_cities = st.multiselect(
        "Villes pour les tendances", selected_cities,
        default=selected_cities[:3] if len(selected_cities) > 3 else selected_cities,
    )

    if trend_cities:
        trend_data = filtered[filtered["city_name"].isin(trend_cities)]

        daily = (
            trend_data.set_index("timestamp_utc")
            .groupby("city_name")["aqi"]
            .resample("1D").mean()
            .reset_index()
        )
        fig_trend = px.line(daily, x="timestamp_utc", y="aqi", color="city_name")
        fig_trend.update_layout(height=380)
        st.plotly_chart(fig_trend, use_container_width=True)

        st.markdown('<div class="section-label">Profil horaire</div>', unsafe_allow_html=True)
        hourly_pivot = trend_data.pivot_table(index="hour", columns="city_name", values="aqi", aggfunc="mean")
        fig_heatmap = px.imshow(
            hourly_pivot, labels=dict(x="Ville", y="Heure", color="AQI"),
            color_continuous_scale="RdYlGn_r",
        )
        fig_heatmap.update_layout(height=380)
        st.plotly_chart(fig_heatmap, use_container_width=True)

        st.markdown('<div class="section-label">Semaine vs Week-end</div>', unsafe_allow_html=True)
        wk = trend_data.groupby(["city_name", "is_weekend"])["aqi"].mean().reset_index()
        wk["period"] = wk["is_weekend"].map({True: "Week-end", False: "Semaine", 1: "Week-end", 0: "Semaine"})

        fig_wk = px.bar(wk, x="city_name", y="aqi", color="period", barmode="group")
        st.plotly_chart(fig_wk, use_container_width=True)
    else:
        st.info("Sélectionnez au moins une ville pour voir les tendances.")

with tab4:
    st.markdown('<div class="section-label">Corrélations entre polluants</div>', unsafe_allow_html=True)

    variables = ["aqi"] + POLLUTANTS
    corr_pollutants = st.multiselect(
        "Polluants pour la matrice de corrélation", variables,
        default=["aqi", "pm2_5", "pm10", "no2", "o3", "co"],
    )

    if len(corr_pollutants) >= 2:
        corr_data = filtered[corr_pollutants].corr()
        fig_corr = px.imshow(
            corr_data, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
        )
        fig_corr.update_layout(height=480)
        st.plotly_chart(fig_corr, use_container_width=True)

        st.markdown('<div class="section-label">Analyse bivariée</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            x_var = st.selectbox("Variable X", variables, index=0)
        with col2:
            default_idx = min(5, len(variables) - 1)
            y_var = st.selectbox("Variable Y", variables, index=default_idx)

        fig_scatter = px.scatter(
            filtered, x=x_var, y=y_var, color="city_name", opacity=0.55, trendline="ols",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Sélectionnez au moins 2 polluants pour voir les corrélations.")

with tab5:
    st.markdown('<div class="section-label">Données brutes</div>', unsafe_allow_html=True)

    page_size = st.selectbox("Lignes par page", [10, 25, 50, 100], index=1)
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
        label="Télécharger (CSV)", data=csv,
        file_name=f"aqi_data_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
    )

# ---------- Footer ----------
st.markdown(
    f"""
    <div class="footer">
        AQI DATA WAREHOUSE — {len(df):,} LIGNES TOTALES · {df['city_name'].nunique()} VILLES ·
        DERNIÈRE MESURE {df["timestamp_utc"].max().strftime('%d/%m/%Y %H:%M')} UTC ·
        POWERED BY OPENWEATHERMAP / AIRFLOW / POSTGRES
    </div>
    """,
    unsafe_allow_html=True,
)