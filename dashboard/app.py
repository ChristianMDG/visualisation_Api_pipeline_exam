"""
AQI Data Warehouse — Tableau de bord interactif (Streamlit)

Console de surveillance de la qualité de l'air : connexion robuste à l'entrepôt PostgreSQL (Neon),
navigation par onglets, filtres avancés, design technique sombre (Inter + JetBrains Mono).
Reflète l'analyse exploratoire du notebook avec des visualisations interactives.
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

# ---------- Configuration de la page ----------
st.set_page_config(
    page_title="AQI Data Warehouse",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Thème Plotly global : tous les graphiques px.* héritent de ce template sombre
px.defaults.template = "plotly_dark"

# ---------- Constantes ----------
AQI_LABELS = {1: "Bon", 2: "Correct", 3: "Modéré", 4: "Mauvais", 5: "Très mauvais"}
AQI_COLORS = {
    "Bon": "#22c55e",
    "Correct": "#84cc16",
    "Modéré": "#eab308",
    "Mauvais": "#f97316",
    "Très mauvais": "#ef4444",
}
AQI_ORDER = ["Bon", "Correct", "Modéré", "Mauvais", "Très mauvais"]
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
        --good: #22c55e;
        --fair: #84cc16;
        --moderate: #eab308;
        --poor: #f97316;
        --very-poor: #ef4444;
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

    /* Étiquettes de section */
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

    /* Cartes métriques */
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

    /* Badges AQI (contour, sans remplissage) */
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

    /* Onglets */
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

    /* DataFrames Streamlit natifs / métriques */
    [data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; }

    /* Pied de page */
    .footer {
        padding: 1.25rem 0 0.5rem 0;
        border-top: 1px solid var(--border);
        margin-top: 2rem;
        color: var(--text-muted);
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        text-align: center;
    }

    /* ===== Barre latérale ===== */
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

    /* Cartes natives st.container(border=True) dans la barre latérale */
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

    /* Curseur */
    section[data-testid="stSidebar"] [data-testid="stSlider"] div[role="slider"] {
        background-color: var(--accent) !important;
        box-shadow: 0 0 0 4px rgba(91, 141, 239, 0.18);
    }

    /* Zone déroulante */
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

    /* Grille de statistiques miniatures */
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

    /* Barre de défilement de la barre latérale */
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
    """Recherche DATABASE_URL dans st.secrets (déploiement), puis dans .env (local)."""
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


# ---------- Chargement des données ----------
# IMPORTANT : pas de fenêtre temporelle ni de LIMIT côté SQL par défaut -> nous chargeons
# L'INTÉGRALITÉ de l'entrepôt. Le filtrage par période se fait ensuite dans la barre
# latérale (côté client). Un plafond de sécurité (SAFETY_ROW_CAP) protège juste contre
# une requête incontrôlée si la pipeline a tourné très longtemps.
SAFETY_ROW_CAP = 100_000


@st.cache_data(ttl=600, show_spinner="Chargement des données de l'entrepôt...")
def load_data():
    """
    Charge TOUTES les lignes de l'entrepôt, avec nouvelle tentative en cas d'erreur
    transitoire. Retourne (df, error_message, truncated). error_message est None
    si tout est correct. truncated est True si le plafond de sécurité a été atteint.
    """
    engine = get_engine()
    if engine is None:
        return None, "DATABASE_URL introuvable (ni dans st.secrets ni dans .env).", False

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
                time.sleep(2 * (attempt + 1))  # Backoff progressif
                continue
            break  # Erreur non transitoire (ex: SQL invalide) -> inutile de réessayer
        except Exception as e:
            last_error = str(e)
            time.sleep(2 * (attempt + 1))
            continue

    return None, last_error or "Le chargement a échoué après plusieurs tentatives.", False


# ---------- Fonctions d'aide AQI ----------
def get_aqi_color(aqi_value: float) -> str:
    if aqi_value <= 1:
        return AQI_COLORS["Bon"]
    elif aqi_value <= 2:
        return AQI_COLORS["Correct"]
    elif aqi_value <= 3:
        return AQI_COLORS["Modéré"]
    elif aqi_value <= 4:
        return AQI_COLORS["Mauvais"]
    return AQI_COLORS["Très mauvais"]


def get_aqi_badge(aqi_label: str) -> str:
    classes = {
        "Bon": "aqi-good",
        "Correct": "aqi-fair",
        "Modéré": "aqi-moderate",
        "Mauvais": "aqi-poor",
        "Très mauvais": "aqi-very-poor",
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
        <p>Surveillance de la qualité de l'air — Pipeline Airflow / Entrepôt Postgres</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if load_error is not None:
    st.error(f"**Impossible de charger les données**\n\n{load_error}")
    st.info(
        "Vérifiez que :\n"
        "- `DATABASE_URL` est défini dans `.env` (local) ou `.streamlit/secrets.toml` (déploiement)\n"
        "- L'entrepôt Neon est accessible depuis votre réseau\n"
        "- Les tables `fact_air_quality`, `dim_city`, `dim_time` contiennent des données"
    )
    st.stop()

if df is None or df.empty:
    st.warning("Aucune donnée disponible dans l'entrepôt pour le moment.")
    st.stop()

if truncated:
    st.warning(
        f"L'entrepôt contient plus de {SAFETY_ROW_CAP:,} lignes : "
        f"seules les {SAFETY_ROW_CAP:,} premières ont été chargées pour rester réactif. "
        "Réduisez la période dans la barre latérale pour affiner les résultats."
    )

# ---------- Barre latérale ----------
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="dot"></div>
            <div class="brand-text">
                <div class="brand-title">DATAGREEN</div>
                <div class="brand-sub">Console AQI Warehouse</div>
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
                aqi_lo, aqi_hi = aqi_lo - 0.5, aqi_hi + 0.5
            aqi_min, aqi_max = st.slider("Plage AQI", min_value=aqi_lo, max_value=aqi_hi, value=(aqi_lo, aqi_hi))

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
                    f"""<div class="stat-mini"><div class="stat-label">Relevés</div>
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
            <div><span class="live-dot"></span>Entrepôt connecté</div>
            <div>{len(df):,} lignes · {df['city_name'].nunique()} villes</div>
            <div>Dernière ingestion : {last_update.strftime('%d/%m/%Y %H:%M')} UTC</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if filtered.empty:
    st.warning("Aucune donnée ne correspond aux filtres sélectionnés.")
    st.stop()

# ---------- Métriques clés ----------
st.markdown('<div class="section-label">Vue d\'ensemble</div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(
        f"""<div class="metric-card"><div class="label">Total relevés</div>
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
        <div class="label">Ville la plus propre</div>
        <div class="value" style="font-size: 1.15rem;">{best_city}</div>
        <div class="change">AQI {best_aqi:.2f}</div></div>""",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ---------- Onglets ----------
# Organisation : chaque onglet correspond à une section clé de l'analyse
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Vue d'ensemble",
    "🏙️ Villes",
    "📈 Tendances temporelles",
    "🔗 Corrélations",
    "📅 Saisons & mois",
    "⚠️ Anomalies",
    "✅ Qualité des données",
    "📋 Données brutes"
])

with tab1:
    """Vue d'ensemble : carte géographique et distribution AQI"""
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
        aqi_dist.columns = ["Catégorie", "Nombre"]

        fig_pie = px.pie(
            aqi_dist, values="Nombre", names="Catégorie", color="Catégorie",
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
    """Comparaison détaillée entre les villes"""
    st.markdown('<div class="section-label">Comparaison des villes</div>', unsafe_allow_html=True)

    city_stats = filtered.groupby("city_name").agg(
        {"aqi": ["mean", "min", "max", "std"], "timestamp_utc": "count"}
    ).round(2)
    city_stats.columns = ["AQI moyen", "AQI min", "AQI max", "Écart-type", "Relevés"]
    city_stats = city_stats.sort_values("AQI moyen")

    st.dataframe(city_stats, use_container_width=True)

    fig_city_bar = px.bar(
        city_stats.reset_index(), x="city_name", y="AQI moyen",
        color="AQI moyen", color_continuous_scale="RdYlGn_r",
        title="AQI moyen par ville",
    )
    st.plotly_chart(fig_city_bar, use_container_width=True)

    fig_box = px.box(filtered, x="city_name", y="aqi", color="city_name",
                     title="Distribution de l'AQI par ville")
    st.plotly_chart(fig_box, use_container_width=True)

with tab3:
    """Tendances temporelles : séries, profils horaires, semaine vs week-end"""
    st.markdown('<div class="section-label">Tendances temporelles</div>', unsafe_allow_html=True)

    trend_cities = st.multiselect(
        "Villes à comparer", selected_cities,
        default=selected_cities[:3] if len(selected_cities) > 3 else selected_cities,
        key="trend_cities"
    )

    if trend_cities:
        trend_data = filtered[filtered["city_name"].isin(trend_cities)]

        # Série temporelle quotidienne (moyenne mobile 7 jours)
        daily = (
            trend_data.set_index("timestamp_utc")
            .groupby("city_name")["aqi"]
            .resample("1D").mean()
            .reset_index()
        )
        # Ajout de la moyenne mobile 7 jours pour un lissage
        daily["aqi_smooth"] = daily.groupby("city_name")["aqi"].transform(
            lambda s: s.rolling(7, min_periods=1).mean()
        )
        
        fig_trend = px.line(
            daily, x="timestamp_utc", y="aqi_smooth", color="city_name",
            labels={"aqi_smooth": "AQI (moyenne mobile 7j)", "timestamp_utc": "Date"},
            title="Tendance AQI (lissée sur 7 jours)"
        )
        fig_trend.update_layout(height=380)
        st.plotly_chart(fig_trend, use_container_width=True)

        # Profil horaire (heatmap)
        st.markdown('<div class="section-label">Profil horaire (cycle jour/nuit)</div>', unsafe_allow_html=True)
        hourly_pivot = trend_data.pivot_table(index="hour", columns="city_name", values="aqi", aggfunc="mean")
        fig_heatmap = px.imshow(
            hourly_pivot, 
            labels=dict(x="Ville", y="Heure (UTC)", color="AQI"),
            color_continuous_scale="RdYlGn_r",
            title="AQI moyen par heure de la journée"
        )
        fig_heatmap.update_layout(height=380)
        st.plotly_chart(fig_heatmap, use_container_width=True)

        # Semaine vs Week-end
        st.markdown('<div class="section-label">Semaine vs Week-end</div>', unsafe_allow_html=True)
        wk = trend_data.groupby(["city_name", "is_weekend"])["aqi"].mean().reset_index()
        wk["période"] = wk["is_weekend"].map({True: "Week-end", False: "Semaine", 1: "Week-end", 0: "Semaine"})

        fig_wk = px.bar(
            wk, x="city_name", y="aqi", color="période", barmode="group",
            title="AQI moyen : semaine vs week-end"
        )
        st.plotly_chart(fig_wk, use_container_width=True)
    else:
        st.info("Sélectionnez au moins une ville pour voir les tendances.")

with tab4:
    """Corrélations entre polluants"""
    st.markdown('<div class="section-label">Corrélations entre polluants</div>', unsafe_allow_html=True)

    variables = ["aqi"] + POLLUTANTS
    corr_pollutants = st.multiselect(
        "Polluants pour la matrice de corrélation", variables,
        default=["aqi", "pm2_5", "pm10", "no2", "o3", "co"],
        key="corr_pollutants"
    )

    if len(corr_pollutants) >= 2:
        corr_data = filtered[corr_pollutants].corr()
        fig_corr = px.imshow(
            corr_data, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
            title="Matrice des corrélations"
        )
        fig_corr.update_layout(height=480)
        st.plotly_chart(fig_corr, use_container_width=True)

        if "aqi" in corr_pollutants:
            st.markdown('<div class="section-label">Corrélation avec l\'AQI — significativité</div>', unsafe_allow_html=True)
            sig_rows = []
            for col in [c for c in corr_pollutants if c != "aqi"]:
                valid = filtered[["aqi", col]].dropna()
                if len(valid) >= 3:
                    r, p = pearsonr(valid["aqi"], valid[col])
                    sig_rows.append({"polluant": col, "r": r, "p_valeur": p, "significatif (p<0.05)": p < 0.05})
            if sig_rows:
                sig_df = pd.DataFrame(sig_rows).assign(abs_r=lambda d: d["r"].abs()) \
                    .sort_values("abs_r", ascending=False).drop(columns="abs_r").set_index("polluant")
                st.dataframe(sig_df.round(4), use_container_width=True)
            st.caption(
                "Avec autant de relevés, les p-valeurs sont presque toujours significatives même pour "
                "des corrélations faibles — jugez la pertinence sur |r|, pas sur la significativité seule. "
                "Notez aussi que l'AQI est lui-même dérivé d'un sous-ensemble de ces polluants "
                "(principalement PM2.5/PM10), donc une forte corrélation reflète en partie la formule "
                "de l'indice lui-même."
            )

        st.markdown('<div class="section-label">Analyse bivariée</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            x_var = st.selectbox("Variable X", variables, index=0, key="x_var")
        with col2:
            default_idx = min(5, len(variables) - 1)
            y_var = st.selectbox("Variable Y", variables, index=default_idx, key="y_var")

        fig_scatter = px.scatter(
            filtered, x=x_var, y=y_var, color="city_name", opacity=0.55, trendline="ols",
            title=f"Relation entre {x_var} et {y_var}"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Sélectionnez au moins 2 polluants pour voir les corrélations.")

with tab5:
    """Tendances saisonnières et mensuelles"""
    st.markdown('<div class="section-label">Tendances saisonnières & mensuelles</div>', unsafe_allow_html=True)
    st.caption(
        "Les données horaires sont bruitées — nous les lissons avec une moyenne mobile sur 7 jours "
        "et les agrégeons par mois pour voir la tendance sous-jacente."
    )

    seasonal_cities = st.multiselect(
        "Villes pour l'analyse saisonnière", selected_cities,
        default=selected_cities, key="seasonal_cities",
    )

    if seasonal_cities:
        seasonal_data = filtered[filtered["city_name"].isin(seasonal_cities)].copy()
        seasonal_data["mois"] = seasonal_data["timestamp_utc"].dt.tz_localize(None).dt.to_period("M").astype(str)

        # Moyenne mobile 7 jours par ville
        daily_season = seasonal_data.groupby(["city_name", "date"])["aqi"].mean().reset_index()
        daily_season = daily_season.sort_values("date")
        daily_season["aqi_lisse"] = daily_season.groupby("city_name")["aqi"].transform(
            lambda s: s.rolling(7, min_periods=1).mean()
        )

        fig_rolling = px.line(
            daily_season, x="date", y="aqi_lisse", color="city_name",
            labels={"aqi_lisse": "AQI (moyenne mobile 7j)", "date": "Date"},
            title="Tendance AQI quotidienne (lissée)"
        )
        fig_rolling.update_layout(height=380)
        st.plotly_chart(fig_rolling, use_container_width=True)

        st.markdown('<div class="section-label">AQI moyen mensuel</div>', unsafe_allow_html=True)
        monthly = seasonal_data.groupby(["city_name", "mois"])["aqi"].mean().reset_index()
        fig_monthly = px.bar(
            monthly, x="mois", y="aqi", color="city_name", barmode="group",
            title="AQI moyen par mois"
        )
        fig_monthly.update_layout(height=380)
        st.plotly_chart(fig_monthly, use_container_width=True)

        monthly_pivot = monthly.pivot(index="mois", columns="city_name", values="aqi").round(1)
        st.dataframe(monthly_pivot, use_container_width=True)
    else:
        st.info("Sélectionnez au moins une ville pour voir les tendances saisonnières.")

with tab6:
    """Détection d'anomalies multivariée"""
    st.markdown('<div class="section-label">Détection d\'anomalies</div>', unsafe_allow_html=True)
    st.caption(
        "Un événement de pollution réel fait généralement bouger plusieurs polluants simultanément. "
        "Nous calculons un z-score glissant par polluant et signalons une lecture lorsqu'au moins "
        "un polluant dépasse le seuil. 'Polluants en accord' indique combien ont bougé ensemble, "
        "ce qui est un signal plus fort qu'un seul polluant."
    )

    ANOMALY_COLUMNS = ["pm2_5", "pm10", "no2", "o3", "co"]

    col1, col2, col3 = st.columns([1, 1, 1.4])
    with col1:
        anomaly_window = st.slider(
            "Fenêtre glissante (heures)", min_value=6, max_value=72, value=24, step=6,
            help="Durée de la fenêtre pour le calcul du z-score"
        )
    with col2:
        anomaly_threshold = st.slider(
            "Seuil z-score", min_value=1.5, max_value=5.0, value=3.0, step=0.5,
            help="Seuil au-delà duquel une valeur est considérée comme anormale"
        )
    with col3:
        anomaly_columns = st.multiselect(
            "Polluants inclus", ANOMALY_COLUMNS, default=ANOMALY_COLUMNS,
            help="Polluants à surveiller pour la détection d'anomalies"
        )

    chance_pct = 2 * norm.sf(anomaly_threshold) * 100
    st.caption(
        f"Pour une distribution approximativement normale, |z| > {anomaly_threshold:.1f} signale "
        f"environ {chance_pct:.2f}% des points par hasard sur un seul polluant. Tester plusieurs "
        "polluants indépendamment augmente le risque de faux positifs, c'est pourquoi "
        "'polluants en accord ≥ 2' est un filtre plus fiable qu'un seul polluant signalé."
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
        g["n_polluants_signales"] = (g[z_cols].abs() > threshold).sum(axis=1) if z_cols else 0
        g["est_anomalie"] = g["z_max"] > threshold if z_cols else False
        return g

    if not anomaly_columns:
        st.info("Sélectionnez au moins un polluant pour lancer la détection d'anomalies.")
    else:
        df_anomalies = filtered.groupby("city_name", group_keys=False)[filtered.columns].apply(
            lambda g: flag_anomalies_multivariate(g, anomaly_columns, window=anomaly_window, threshold=anomaly_threshold)
        )
        anomalies = df_anomalies[df_anomalies["est_anomalie"]].sort_values("timestamp_utc")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(
                f"""<div class="metric-card"><div class="label">Anomalies signalées</div>
                <div class="value">{len(anomalies):,}</div></div>""",
                unsafe_allow_html=True,
            )
        with m2:
            pct = len(anomalies) / len(filtered) * 100 if len(filtered) else 0
            st.markdown(
                f"""<div class="metric-card"><div class="label">Part des relevés</div>
                <div class="value">{pct:.2f}%</div></div>""",
                unsafe_allow_html=True,
            )
        with m3:
            agree_2plus = int((anomalies["n_polluants_signales"] >= 2).sum()) if len(anomalies) else 0
            st.markdown(
                f"""<div class="metric-card"><div class="label">Signalées sur 2+ polluants</div>
                <div class="value">{agree_2plus:,}</div></div>""",
                unsafe_allow_html=True,
            )
        with m4:
            worst_city = anomalies["city_name"].value_counts().idxmax() if len(anomalies) else "—"
            st.markdown(
                f"""<div class="metric-card"><div class="label">Ville la plus touchée</div>
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
            anom_high = sub[(sub["est_anomalie"]) & (sub[f"z_{display_col}"] > 0)]
            anom_low = sub[(sub["est_anomalie"]) & (sub[f"z_{display_col}"] <= 0)]
            if len(anom_high):
                fig_anom.add_trace(go.Scatter(
                    x=anom_high["timestamp_utc"], y=anom_high[display_col], mode="markers",
                    marker=dict(color="#ef4444", size=6 + 4 * anom_high["n_polluants_signales"], symbol="triangle-up"),
                    name=f"{city} pic", showlegend=False,
                ))
            if len(anom_low):
                fig_anom.add_trace(go.Scatter(
                    x=anom_low["timestamp_utc"], y=anom_low[display_col], mode="markers",
                    marker=dict(color="#f97316", size=6 + 4 * anom_low["n_polluants_signales"], symbol="triangle-down"),
                    name=f"{city} creux", showlegend=False,
                ))
        fig_anom.update_layout(
            height=420, 
            yaxis_title=f"{display_col.upper()} (taille du marqueur = polluants en accord)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            title=f"Détection d'anomalies sur {display_col.upper()}"
        )
        st.plotly_chart(fig_anom, use_container_width=True)

        st.markdown('<div class="section-label">Anomalies par ville</div>', unsafe_allow_html=True)
        if len(anomalies):
            counts = anomalies["city_name"].value_counts()
            totals = df_anomalies["city_name"].value_counts()
            summary = pd.DataFrame({"anomalies": counts, "total_points": totals})
            summary["pct"] = (summary["anomalies"] / summary["total_points"] * 100).round(2)
            summary = summary.sort_values("pct", ascending=False)
            st.dataframe(summary, use_container_width=True)

            with st.expander("Voir les relevés signalés"):
                display_cols = ["city_name", "timestamp_utc"] + anomaly_columns + ["aqi", "z_max", "n_polluants_signales"]
                st.dataframe(
                    anomalies[display_cols],
                    use_container_width=True, height=300,
                )
        else:
            st.info("Aucune anomalie détectée avec les paramètres actuels.")

with tab7:
    """Qualité des données"""
    st.markdown('<div class="section-label">Qualité des données</div>', unsafe_allow_html=True)
    st.caption(
        "Ce qui se trouve réellement dans l'entrepôt avec les filtres actuels : "
        "valeurs manquantes, doublons, lacunes dans la cadence horaire et valeurs hors limites."
    )

    q1, q2, q3 = st.columns(3)

    missing = filtered[POLLUTANTS + ["aqi"]].isna().sum()
    missing_pct_total = (missing.sum() / (len(filtered) * (len(POLLUTANTS) + 1)) * 100) if len(filtered) else 0
    dupes = filtered.duplicated(subset=["city_name", "timestamp_utc"]).sum()
    dupes_pct = (dupes / len(filtered) * 100) if len(filtered) else 0
    negatives = int((filtered[POLLUTANTS + ["aqi"]] < 0).sum().sum())

    with q1:
        st.markdown(
            f"""<div class="metric-card"><div class="label">Valeurs manquantes</div>
            <div class="value">{missing_pct_total:.2f}%</div></div>""",
            unsafe_allow_html=True,
        )
    with q2:
        st.markdown(
            f"""<div class="metric-card"><div class="label">Doublons (ville, timestamp)</div>
            <div class="value">{dupes:,}</div></div>""",
            unsafe_allow_html=True,
        )
    with q3:
        st.markdown(
            f"""<div class="metric-card"><div class="label">Valeurs négatives de polluants</div>
            <div class="value">{negatives:,}</div></div>""",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-label">Valeurs manquantes par colonne</div>', unsafe_allow_html=True)
    missing_df = pd.DataFrame({"manquants": missing, "pct": (missing / len(filtered) * 100).round(2) if len(filtered) else missing})
    st.dataframe(missing_df[missing_df["manquants"] > 0] if missing.sum() else missing_df, use_container_width=True)

    st.markdown('<div class="section-label">Continuité horaire par ville</div>', unsafe_allow_html=True)

    # Version vectorisée (sans groupby.apply) pour éviter les avertissements pandas 2.x
    quality_sorted = filtered.sort_values(["city_name", "timestamp_utc"])
    diffs_by_city = quality_sorted.groupby("city_name")["timestamp_utc"].diff()
    expected = pd.Timedelta(hours=1)
    gaps_report = pd.DataFrame({
        "n_points": quality_sorted.groupby("city_name").size(),
        "lacunes": (diffs_by_city > expected).groupby(quality_sorted["city_name"]).sum(),
        "lacune_max": diffs_by_city.groupby(quality_sorted["city_name"]).max().astype(str),
    })
    st.dataframe(gaps_report, use_container_width=True)

    st.markdown('<div class="section-label">Statistiques descriptives</div>', unsafe_allow_html=True)
    st.dataframe(filtered[POLLUTANTS + ["aqi"]].describe().T.round(2), use_container_width=True)

with tab8:
    """Données brutes"""
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

# ---------- Pied de page ----------
st.markdown(
    f"""
    <div class="footer">
        AQI DATA WAREHOUSE — {len(df):,} LIGNES · {df['city_name'].nunique()} VILLES ·
        DERNIER RELEVÉ {df["timestamp_utc"].max().strftime('%d/%m/%Y %H:%M')} UTC ·
        DONNÉES OPENWEATHERMAP / PIPELINE AIRFLOW / POSTGRES
    </div>
    """,
    unsafe_allow_html=True,
)