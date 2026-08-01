# 🌍 AQI Data Warehouse — Dashboard & Analysis

## 📌 Table of Contents
1. [Project Overview](#overview)
2. [Dashboard Features](#dashboard)
3. [Analysis Notebooks](#notebooks)
4. [Installation & Deployment](#installation)
5. [Project Structure](#structure)
6. [Data Sources](#datasources)
7. [Security & Best Practices](#security)
8. [Links & Resources](#links)

---

## 1. Project Overview {#overview}

**AQI Data Warehouse** is an interactive air quality monitoring solution that visualizes pollution data from multiple cities. This repository focuses on:

- **Interactive Dashboard** built with Streamlit for real-time data visualization
- **Analysis Notebooks** for exploratory data analysis and insights
- **Data Warehouse** connection to PostgreSQL database on Neon
- **Automated visualizations** using Plotly, Matplotlib, and Seaborn

### 🎯 Objectives
- Provide an intuitive dashboard for air quality monitoring
- Enable data exploration through Jupyter notebooks
- Visualize pollutant trends and correlations
- Support data-driven decision making

---

## 2. Dashboard Features {#dashboard}

### 🖥️ Main Sections

**📊 Overview**
- Key metrics: Total measurements, cities count, average/max AQI
- Interactive geographic map with city air quality
- AQI category distribution (Good → Very Poor)
- Top 5 cities with best air quality

**🏙️ City Comparison**
- Comprehensive city statistics (mean, min, max, std)
- Comparative bar charts
- Box plots showing AQI distribution

**📈 Time Trends**
- Daily AQI evolution with line charts
- Hourly heatmap (AQI by hour and city)
- Weekend vs weekday comparison

**🔗 Correlations**
- Correlation matrix between pollutants
- Interactive bivariate analysis (scatter plots)
- Trend lines for relationship analysis

**📋 Raw Data**
- Paginated data view
- CSV export functionality
- Filtered data display

### 🎨 Design
- Modern interface with responsive cards
- Color-coded AQI badges (Good → Very Poor)
- Fully responsive (mobile, tablet, desktop)
- Consistent color scheme throughout

---

## 3. Analysis Notebooks {#notebooks}

### 📓 `notebooks/analysis.ipynb`

**Purpose**: Exploratory Data Analysis (EDA) and in-depth analysis of air quality data.

**Key Analyses**:

```python
# Connection Setup
from sqlalchemy import create_engine
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load data from warehouse
query = """
SELECT 
    c.city_name, c.country, c.latitude, c.longitude,
    t.timestamp_utc, t.date, t.hour, t.day_name,
    f.aqi, f.pm2_5, f.pm10, f.no2, f.o3, f.co
FROM fact_air_quality f
JOIN dim_city c ON c.city_key = f.city_key
JOIN dim_time t ON t.time_key = f.time_key
ORDER BY c.city_name, t.timestamp_utc
LIMIT 10000
"""
df = pd.read_sql(query, engine)
```

**Visualizations Included**:
1. **AQI Distribution**: Histogram with KDE
2. **City Comparison**: Bar charts and box plots
3. **Temporal Analysis**: Time series plots
4. **Correlation Matrix**: Heatmap of pollutants
5. **Geographic Map**: Scatter geo plot
6. **Hourly Patterns**: Heatmaps and line charts

**Usage**:
```bash
# Launch Jupyter Notebook
jupyter notebook notebooks/analysis.ipynb

# Or use VS Code with Python extension
# Open the notebook and select Python kernel
```

**Key Insights**:
- Identify cities with highest/lowest AQI
- Understand pollution patterns by hour/day
- Discover correlations between pollutants
- Track air quality trends over time

---

## 4. Installation & Deployment {#installation}

### 📦 Prerequisites
```bash
Python 3.11+
Git
Neon Account (Database access)
```

### 🔧 Local Installation

```bash
# 1. Clone the repository
git clone https://github.com/ChristianMDG/visualisation_Api_pipeline_exam.git
cd visualisation_Api_pipeline_exam

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
# Create .env file with your database URL
cat > .env << EOF
DATABASE_URL=postgresql://username:password@host.neon.tech/neondb?sslmode=require
EOF

# 5. Launch dashboard
streamlit run dashboard/app.py

# 6. Launch notebook (optional)
jupyter notebook notebooks/analysis.ipynb
```

### 🚀 Deploy Dashboard on Streamlit Cloud

**1. Prepare files**
```bash
# requirements.txt
streamlit>=1.38.0
pandas>=2.0.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.9
plotly>=5.22.0
python-dotenv>=1.0.0
matplotlib>=3.8.0
seaborn>=0.13.0
```

**2. Configure secrets**
```toml
# .streamlit/secrets.toml (DO NOT COMMIT)
DATABASE_URL = "postgresql://username:password@host.neon.tech/neondb?sslmode=require"
```

**3. Deploy**
- Visit [share.streamlit.io](https://share.streamlit.io)
- Connect GitHub account
- Select repository and branch
- Set main file path: `dashboard/app.py`
- Add secrets in "Advanced settings"
- Click "Deploy"

**4. Access Dashboard**
- URL: `https://visualisationapipipelineexam-d3xfoonxl7gzkekwntej96.streamlit.app`

---

## 5. Project Structure {#structure}

```
visualisation_Api_pipeline_exam/
├── dashboard/
│   ├── app.py                    # Main Streamlit application (incl. DB connection)
│   └── requirements.txt          # Dependencies for Streamlit Cloud deployment
├── notebooks/
│   └── analysis.ipynb            # EDA and analysis notebook
├── .devcontainer/                # Codespaces / VS Code dev container config
├── .env.example                  # Template for local environment variables
├── .gitignore                    # Ignored files
├── requirements.txt              # Python dependencies (local/full dev)
└── README.md                     # Documentation
```

### 📄 Key Files Description

| File | Description |
|------|-------------|
| `dashboard/app.py` | Interactive dashboard with 5 tabs (database connection managed inline via `get_database_url()`) |
| `notebooks/analysis.ipynb` | Exploratory data analysis |
| `requirements.txt` | All Python dependencies |

---

## 6. Data Sources {#datasources}

### 🗄️ Data Warehouse (Neon PostgreSQL)

**Database Schema**:

**fact_air_quality** (Main fact table)
- `aqi`: Air Quality Index (1-5)
- `pm2_5, pm10`: Particulate matter
- `co, no, no2, o3, so2, nh3`: Gas pollutants
- `city_key`: Foreign key to dim_city
- `time_key`: Foreign key to dim_time

**dim_city** (City dimension)
- `city_key`: Primary key
- `city_name, country`: Location info
- `latitude, longitude`: Geographic coordinates

**dim_time** (Time dimension)
- `time_key`: Primary key
- `timestamp_utc`: Full timestamp
- `date, hour`: Date and time components
- `day_of_week, is_weekend`: Temporal attributes

### 📊 Sample Query
```sql
SELECT 
    c.city_name,
    c.country,
    t.date,
    AVG(f.aqi) as avg_aqi,
    AVG(f.pm2_5) as avg_pm25
FROM fact_air_quality f
JOIN dim_city c ON f.city_key = c.city_key
JOIN dim_time t ON f.time_key = t.time_key
WHERE t.date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY c.city_name, c.country, t.date
ORDER BY t.date DESC, avg_aqi DESC;
```

---

## 7. Security & Best Practices {#security}

### 🔐 Secret Management
- **Never commit** `.env` or `secrets.toml`
- Use `st.secrets` for Streamlit Cloud deployment
- Store database credentials securely
- Regular password rotation recommended

### 📝 Best Practices

**Code Quality**:
- Modular functions with clear documentation
- Error handling with try-except blocks
- Data validation before processing
- Efficient caching (Streamlit cache)

**Performance**:
- Load the full warehouse, capped at 100,000 rows as a safety limit (`SAFETY_ROW_CAP`)
- Filtering by period happens client-side in the sidebar
- Implement data pagination
- Cache expensive operations (`st.cache_data`, `st.cache_resource`)

**Security**:
- Never expose database credentials
- Use read-only connections for dashboard
- Implement proper error messages (no stack traces)

---

## 8. Links & Resources {#links}

### 📊 Deployed Dashboard
- **URL**: [https://visualisationapipipelineexam-d3xfoonxl7gzkekwntej96.streamlit.app](https://visualisationapipipelineexam-d3xfoonxl7gzkekwntej96.streamlit.app)

### 📁 Source Code
- **Repository**: `https://github.com/ChristianMDG/visualisation_Api_pipeline_exam.git`

### 📚 Documentation
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Pandas Documentation](https://pandas.pydata.org/)
- [SQLAlchemy Documentation](https://www.sqlalchemy.org/)
- [Plotly Documentation](https://plotly.com/python/)

### 🛠️ Tools Used
- **Dashboard**: Streamlit
- **Visualization**: Plotly, Matplotlib, Seaborn
- **Data Processing**: Pandas, SQLAlchemy
- **Database**: Neon (PostgreSQL)

---

## 📊 Performance & Limits

| Feature | Specification |
|---------|---------------|
| Data period | None (full warehouse, filtered client-side) |
| Query limit | 100,000 rows (safety cap) |
| Cache TTL | 10 minutes |
| Update frequency | Real-time (on query) |
| Load time | 2-5 seconds |

---

## 👥 Contributors

- **Christian** - Data Engineer & Developer
- Project created as part of training

---

## 📞 Support

For questions or issues:
- Open an issue on GitHub
- Contact the project team

---

**Last Updated**: July 29, 2026
**Version**: 2.0

---

🌍 *AQI Data Warehouse — Interactive Air Quality Monitoring*