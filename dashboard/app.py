"""
AQI Data Warehouse — Interactive Dashboard (Streamlit)

Design ergonomique avec cards, navigation par onglets, filtres avancés,
et connexion robuste au data warehouse PostgreSQL (Neon).
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
    page_title="🌍 AQI Data Warehouse",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Constantes ----------
AQI_LABELS = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
AQI_COLORS = {
    "Good": "#10b981",
    "Fair": "#fbbf24",
    "Moderate": "#f59e0b",
    "Poor": "#ef4444",
    "Very Poor": "#7f1d1d",
}
AQI_ORDER = ["Good", "Fair", "Moderate", "Poor", "Very Poor"]
POLLUTANTS = ["co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3"]

CUSTOM_CSS = """
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-header h1 { font-size: 2.5rem; font-weight: 700; margin: 0; }
    .main-header p { font-size: 1.1rem; opacity: 0.9; margin: 0.5rem 0 0 0; }

    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 4px solid #667eea;
        transition: transform 0.2s, box-shadow 0.2s;
        margin-bottom: 1rem;
    }
    .metric-card:hover { transform: translateY(-3px); box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
    .metric-card .label { font-size: 0.85rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-card .value { font-size: 2rem; font-weight: 700; color: #1f2937; margin: 0.25rem 0; }
    .metric-card .change { font-size: 0.85rem; color: #10b981; }

    .aqi-badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 20px; font-weight: 600; font-size: 0.8rem; }
    .aqi-good { background: #10b981; color: white; }
    .aqi-fair { background: #fbbf24; color: #1f2937; }
    .aqi-moderate { background: #f59e0b; color: white; }
    .aqi-poor { background: #ef4444; color: white; }
    .aqi-very-poor { background: #7f1d1d; color: white; }

    .footer { text-align: center; padding: 2rem; color: #94a3b8; border-top: 1px solid #e2e8f0; margin-top: 2rem; }

    @media (max-width: 768px) {
        .main-header h1 { font-size: 1.8rem; }
        .metric-card .value { font-size: 1.5rem; }
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
@st.cache_data(ttl=600, show_spinner="🔄 Chargement des données...")
def load_data(days_back: int = 30, row_limit: int = 50_000):
    """
    Charge les données du warehouse avec retry sur erreurs transitoires.
    Retourne (df, error_message). error_message est None si tout s'est bien passé.
    """
    engine = get_engine()
    if engine is None:
        return None, "DATABASE_URL introuvable (ni dans st.secrets, ni dans .env)."

    query = f"""
        SELECT
            c.city_name, c.country, c.latitude, c.longitude,
            t.timestamp_utc, t.date, t.hour, t.day_of_week, t.day_name, t.is_weekend,
            f.aqi, f.co, f.no, f.no2, f.o3, f.so2, f.pm2_5, f.pm10, f.nh3
        FROM fact_air_quality f
        JOIN dim_city c ON c.city_key = f.city_key
        JOIN dim_time t ON t.time_key = f.time_key
        WHERE t.date >= CURRENT_DATE - INTERVAL '{days_back} days'
        ORDER BY c.city_name, t.timestamp_utc
        LIMIT {row_limit};
    """

    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            df = pd.read_sql(query, engine)
            if df.empty:
                return df, None

            df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
            df["aqi_label"] = df["aqi"].map(AQI_LABELS)
            return df, None

        except SQLAlchemyError as e:
            last_error = str(e)
            # Erreur transitoire connue (connexion coupée côté Neon) -> on retente
            if "SSL" in last_error or "closed" in last_error or "timeout" in last_error.lower():
                time.sleep(2 * (attempt + 1))  # backoff progressif
                continue
            break  # erreur non transitoire (ex: SQL invalide) -> inutile de retenter
        except Exception as e:
            last_error = str(e)
            time.sleep(2 * (attempt + 1))
            continue

    return None, last_error or "Échec de chargement après plusieurs tentatives."


# ---------- Fonctions utilitaires AQI ----------
def get_aqi_color(aqi_value: float) -> str:
    if aqi_value <= 1:
        return "#10b981"
    elif aqi_value <= 2:
        return "#fbbf24"
    elif aqi_value <= 3:
        return "#f59e0b"
    elif aqi_value <= 4:
        return "#ef4444"
    return "#7f1d1d"
 
 
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
 
df, load_error = load_data()
 
st.markdown(
    """
    <div class="main-header">
        <h1>🌍 AQI Data Warehouse</h1>
        <p>Tableau de bord interactif de la qualité de l'air — Données en temps réel</p>
    </div>
    """,
    unsafe_allow_html=True,
)
 
if load_error is not None:
    st.error(f"❌ **Impossible de charger les données**\n\n{load_error}")
    st.info(
        "Vérifiez que :\n"
        "- `DATABASE_URL` est défini dans `.env` (local) ou `.streamlit/secrets.toml` (déploiement)\n"
        "- Le warehouse Neon est accessible depuis votre réseau\n"
        "- Les tables `fact_air_quality`, `dim_city`, `dim_time` contiennent des données"
    )
    st.stop()
 
if df is None or df.empty:
    st.warning("⚠️ Aucune donnée disponible sur la période demandée.")
    st.stop()

# ---------- Sidebar ----------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/air-quality.png", width=80)
    st.markdown("### 🎛️ Filtres")
 
    cities = sorted(df["city_name"].unique())
    selected_cities = st.multiselect(
        "🏙️ Villes", cities, default=cities[:3] if len(cities) > 3 else cities,
        help="Sélectionnez les villes à afficher",
    )
 
    date_min = df["timestamp_utc"].min().date()
    date_max = df["timestamp_utc"].max().date()
    default_start = max(date_min, date_max - timedelta(days=7))
 
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("📅 Début", default_start, min_value=date_min, max_value=date_max)
    with col2:
        end_date = st.date_input("📅 Fin", date_max, min_value=date_min, max_value=date_max)
 
    with st.expander("🔍 Filtres avancés"):
        aqi_lo, aqi_hi = float(df["aqi"].min()), float(df["aqi"].max())
        if aqi_lo == aqi_hi:
            # Un slider Streamlit exige min < max : on élargit artificiellement
            aqi_lo, aqi_hi = aqi_lo - 0.5, aqi_hi + 0.5
        aqi_min, aqi_max = st.slider("AQI Range", min_value=aqi_lo, max_value=aqi_hi, value=(aqi_lo, aqi_hi))
 
        selected_pollutants = st.multiselect(
            "Polluants à afficher", POLLUTANTS, default=["pm2_5", "pm10", "no2", "o3"]
        )
 
    st.markdown("---")
    st.markdown("### 📊 Statistiques")
 
    filtered = df[df["city_name"].isin(selected_cities)]
    filtered = filtered[
        (filtered["timestamp_utc"].dt.date >= start_date) & (filtered["timestamp_utc"].dt.date <= end_date)
    ]
    filtered = filtered[(filtered["aqi"] >= aqi_min) & (filtered["aqi"] <= aqi_max)]
 
    if not filtered.empty:
        st.metric("📊 Total mesures", f"{len(filtered):,}")
        st.metric("🏙️ Villes", filtered["city_name"].nunique())
        st.metric("📈 AQI moyen", f"{filtered['aqi'].mean():.2f}")
        st.metric("🔴 AQI max", f"{filtered['aqi'].max():.2f}")
        last_update = filtered["timestamp_utc"].max()
        st.caption(f"🕐 Dernière mise à jour: {last_update.strftime('%d/%m/%Y %H:%M')}")
 
    st.markdown("---")
    st.caption("💡 *Les données sont mises à jour toutes les heures*")
 
if filtered.empty:
    st.warning("⚠️ Aucune donnée ne correspond aux filtres sélectionnés.")
    st.stop()

# ---------- Métriques principales ----------
st.markdown("### 📊 Vue d'ensemble")
 
col1, col2, col3, col4, col5 = st.columns(5)
 
with col1:
    st.markdown(
        f"""<div class="metric-card"><div class="label">📊 Total mesures</div>
        <div class="value">{len(filtered):,}</div></div>""",
        unsafe_allow_html=True,
    )
 
with col2:
    st.markdown(
        f"""<div class="metric-card"><div class="label">🏙️ Villes</div>
        <div class="value">{filtered['city_name'].nunique()}</div></div>""",
        unsafe_allow_html=True,
    )
 
with col3:
    avg_aqi = filtered["aqi"].mean()
    color = get_aqi_color(avg_aqi)
    st.markdown(
        f"""<div class="metric-card" style="border-left-color: {color};">
        <div class="label">📈 AQI moyen</div>
        <div class="value" style="color: {color};">{avg_aqi:.2f}</div></div>""",
        unsafe_allow_html=True,
    )
 
with col4:
    max_aqi = filtered["aqi"].max()
    color = get_aqi_color(max_aqi)
    st.markdown(
        f"""<div class="metric-card" style="border-left-color: {color};">
        <div class="label">🔴 AQI max</div>
        <div class="value" style="color: {color};">{max_aqi:.2f}</div></div>""",
        unsafe_allow_html=True,
    )
 
with col5:
    best_city = filtered.groupby("city_name")["aqi"].mean().idxmin()
    best_aqi = filtered.groupby("city_name")["aqi"].mean().min()
    st.markdown(
        f"""<div class="metric-card" style="border-left-color: #10b981;">
        <div class="label">🌟 Meilleure ville</div>
        <div class="value" style="font-size: 1.2rem;">{best_city}</div>
        <div class="change">AQI: {best_aqi:.2f}</div></div>""",
        unsafe_allow_html=True,
    )
 
st.markdown("---")

# ---------- Tabs ----------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Overview", "🏙️ Villes", "📈 Tendances", "🔗 Corrélations", "📋 Données"]
)
 
with tab1:
    col1, col2 = st.columns([2, 1])
 
    with col1:
        st.subheader("🌍 Carte des villes")
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
                projection="natural earth", title="Qualité de l'air par ville",
            )
            fig_map.update_layout(height=500)
            st.plotly_chart(fig_map, use_container_width=True)
 
    with col2:
        st.subheader("📊 Distribution AQI")
        aqi_dist = filtered["aqi_label"].value_counts().reset_index()
        aqi_dist.columns = ["Category", "Count"]
 
        fig_pie = px.pie(
            aqi_dist, values="Count", names="Category", color="Category",
            color_discrete_map=AQI_COLORS, hole=0.4,
        )
        fig_pie.update_layout(height=300)
        st.plotly_chart(fig_pie, use_container_width=True)
 
        st.subheader("🌟 Top 5 meilleures villes")
        best_cities = filtered.groupby("city_name")["aqi"].mean().sort_values().head(5)
        for city, aqi in best_cities.items():
            color = get_aqi_color(aqi)
            st.markdown(
                f"""<div style="display: flex; justify-content: space-between; padding: 0.3rem 0;
                border-bottom: 1px solid #e2e8f0;">
                <span>{city}</span>
                <span style="color: {color}; font-weight: 600;">AQI: {aqi:.2f}</span></div>""",
                unsafe_allow_html=True,
            )
 
with tab2:
    st.subheader("🏙️ Comparaison des villes")
 
    city_stats = filtered.groupby("city_name").agg(
        {"aqi": ["mean", "min", "max", "std"], "timestamp_utc": "count"}
    ).round(2)
    city_stats.columns = ["AQI moyen", "AQI min", "AQI max", "Écart-type", "Mesures"]
    city_stats = city_stats.sort_values("AQI moyen")
 
    st.dataframe(city_stats, use_container_width=True)
 
    fig_city_bar = px.bar(
        city_stats.reset_index(), x="city_name", y="AQI moyen",
        color="AQI moyen", color_continuous_scale="RdYlGn_r", title="AQI moyen par ville",
    )
    st.plotly_chart(fig_city_bar, use_container_width=True)
 
    fig_box = px.box(filtered, x="city_name", y="aqi", color="city_name", title="Distribution AQI par ville")
    st.plotly_chart(fig_box, use_container_width=True)
 
with tab3:
    st.subheader("📈 Évolution temporelle")
 
    trend_cities = st.multiselect(
        "Villes pour les tendances", selected_cities,
        default=selected_cities[:2] if len(selected_cities) > 2 else selected_cities,
    )
 
    if trend_cities:
        trend_data = filtered[filtered["city_name"].isin(trend_cities)]
 
        daily = (
            trend_data.set_index("timestamp_utc")
            .groupby("city_name")["aqi"]
            .resample("1D").mean()
            .reset_index()
        )
        fig_trend = px.line(daily, x="timestamp_utc", y="aqi", color="city_name",
                             title="Évolution AQI - Moyenne quotidienne")
        fig_trend.update_layout(height=400)
        st.plotly_chart(fig_trend, use_container_width=True)
 
        st.subheader("🕐 Heatmap horaire")
        hourly_pivot = trend_data.pivot_table(index="hour", columns="city_name", values="aqi", aggfunc="mean")
        fig_heatmap = px.imshow(
            hourly_pivot, labels=dict(x="Ville", y="Heure", color="AQI"),
            title="AQI moyen par heure et par ville", color_continuous_scale="RdYlGn_r",
        )
        fig_heatmap.update_layout(height=400)
        st.plotly_chart(fig_heatmap, use_container_width=True)
 
        st.subheader("📅 Week-end vs Semaine")
        wk = trend_data.groupby(["city_name", "is_weekend"])["aqi"].mean().reset_index()
        # is_weekend vient de Postgres comme un vrai BOOLEAN -> True/False, pas 1/0.
        # On gère les deux cas pour rester robuste si la colonne change de type un jour.
        wk["period"] = wk["is_weekend"].map({True: "Week-end", False: "Semaine", 1: "Week-end", 0: "Semaine"})
 
        fig_wk = px.bar(wk, x="city_name", y="aqi", color="period", barmode="group",
                         title="AQI moyen - Week-end vs Semaine")
        st.plotly_chart(fig_wk, use_container_width=True)
    else:
        st.info("ℹ️ Sélectionnez au moins une ville pour voir les tendances.")
 
with tab4:
    st.subheader("🔗 Corrélations entre polluants")
 
    variables = ["aqi"] + POLLUTANTS
    corr_pollutants = st.multiselect(
        "Polluants pour la matrice de corrélation", variables,
        default=["aqi", "pm2_5", "pm10", "no2", "o3", "co"],
    )
 
    if len(corr_pollutants) >= 2:
        corr_data = filtered[corr_pollutants].corr()
        fig_corr = px.imshow(
            corr_data, text_auto=".2f", color_continuous_scale="RdBu_r",
            zmin=-1, zmax=1, title="Matrice de corrélation",
        )
        fig_corr.update_layout(height=500)
        st.plotly_chart(fig_corr, use_container_width=True)
 
        st.subheader("📊 Analyse bivariée")
        col1, col2 = st.columns(2)
        with col1:
            x_var = st.selectbox("Variable X", variables, index=0)
        with col2:
            default_idx = min(5, len(variables) - 1)
            y_var = st.selectbox("Variable Y", variables, index=default_idx)
 
        fig_scatter = px.scatter(
            filtered, x=x_var, y=y_var, color="city_name", opacity=0.5,
            trendline="ols", title=f"{x_var} vs {y_var}",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("ℹ️ Sélectionnez au moins 2 polluants pour voir les corrélations")
 
with tab5:
    st.subheader("📋 Données brutes")
 
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
        label="📥 Télécharger les données (CSV)", data=csv,
        file_name=f"aqi_data_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
    )

# ---------- Footer ----------
st.markdown(
    f"""
    <div class="footer">
        <p>🌍 AQI Data Warehouse — Powered by OpenWeatherMap & Streamlit</p>
        <p style="font-size: 0.8rem;">
            Données mises à jour toutes les heures •
            Dernière mise à jour: {filtered["timestamp_utc"].max().strftime('%d/%m/%Y %H:%M')} •
            Version 2.0
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)
 
