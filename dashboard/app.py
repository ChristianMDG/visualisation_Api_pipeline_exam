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
