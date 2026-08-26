"""
Custom CSS for the AI Investment Advisor dashboard: a dark "control room"
monitoring theme, forced into strict RTL with a Hebrew webfont.

Notes:
- Streamlit's own widgets are targeted via their `data-testid` attributes,
  which is the standard (if slightly version-sensitive) way to restyle
  built-in components. If a future Streamlit upgrade renames an attribute,
  the affected selector below will simply stop matching - the app still
  works, it just loses that bit of RTL/theme polish.
- `!important` is used deliberately throughout: Streamlit ships its own
  inline/utility styles that would otherwise win the cascade.
"""

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;600;700;800&family=Share+Tech+Mono&display=swap');

:root {
  --bg: #050a0f;
  --bg2: #080f17;
  --bg3: #0c1824;
  --card: #0d1f30;
  --card2: #102540;
  --border: #1a3a5c;
  --border2: #1e4a73;
  --cyan: #00d4ff;
  --green: #00ff88;
  --orange: #ff6b35;
  --yellow: #ffd700;
  --red: #ff3355;
  --text: #c8e0f0;
  --text2: #7a9db5;
  --text3: #4a7a99;
}

/* ---------- Global RTL + Hebrew font ---------- */
html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {
  direction: rtl !important;
  font-family: 'Assistant', 'Noto Sans Hebrew', 'Segoe UI', sans-serif !important;
  background-color: var(--bg) !important;
  color: var(--text) !important;
}

.main .block-container {
  direction: rtl !important;
  text-align: right !important;
  padding-top: 1.5rem;
}

p, span, div, li, label, h1, h2, h3, h4, h5, h6,
.stMarkdown, .stText, .stCaption {
  text-align: right !important;
}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
  direction: rtl !important;
  text-align: right !important;
  background-color: var(--bg2) !important;
  border-left: 1px solid var(--border);
}
[data-testid="stSidebar"] * { text-align: right !important; }

/* ---------- Inputs / buttons ---------- */
input, textarea, select {
  direction: rtl !important;
  text-align: right !important;
}
.stButton > button {
  direction: rtl !important;
  width: 100%;
  border: 1px solid var(--border2) !important;
  background: var(--card2) !important;
  color: var(--cyan) !important;
}
.stButton > button:hover {
  border-color: var(--cyan) !important;
  box-shadow: 0 0 12px rgba(0,212,255,.35);
}

/* ---------- Metrics ---------- */
[data-testid="stMetric"] {
  direction: rtl !important;
  text-align: right !important;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 14px;
}
[data-testid="stMetricLabel"], [data-testid="stMetricValue"], [data-testid="stMetricDelta"] {
  text-align: right !important;
  justify-content: flex-end !important;
}

/* ---------- Tables / dataframes ---------- */
[data-testid="stDataFrame"], [data-testid="stTable"] {
  direction: rtl !important;
}
[data-testid="stDataFrame"] * , [data-testid="stTable"] * {
  text-align: right !important;
}
table, th, td { direction: rtl !important; text-align: right !important; }

/* ---------- Alerts (st.error / st.success / st.warning / st.info) ---------- */
[data-testid="stAlert"] {
  direction: rtl !important;
  text-align: right !important;
  border-radius: 12px !important;
}

/* ---------- Charts ----------
   Deliberately NOT forcing direction:rtl on the Plotly SVG container: doing
   so clips the chart's own internally-rendered content (axis tick labels
   get cut off at the container edge). Plotly renders its own coordinate
   system LTR internally regardless; RTL-appropriate layout (title anchored
   right, Hebrew labels, automargin for long Hebrew tick text) is set
   per-figure instead, see dashboard/app.py. Only the outer wrapper that
   Streamlit places the chart in is aligned with the rest of the page. */
[data-testid="stPlotlyChart"] { direction: ltr; }

/* ---------- Expanders ---------- */
[data-testid="stExpander"] { direction: rtl !important; text-align: right !important; border: 1px solid var(--border); border-radius: 10px; }
[data-testid="stExpander"] summary { text-align: right !important; }

/* ================= Control-room components ================= */

.cr-header {
  background: linear-gradient(135deg, var(--card) 0%, var(--card2) 100%);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px 28px;
  margin-bottom: 18px;
  box-shadow: 0 0 30px rgba(0,212,255,0.08);
}
.cr-header h1 {
  color: var(--cyan) !important;
  font-size: 1.9rem;
  margin: 0;
  text-shadow: 0 0 20px rgba(0,212,255,.4);
}
.cr-header p { color: var(--text2) !important; margin: 6px 0 0; font-size: .95rem; }

.cr-status-row { display: flex; gap: 10px; flex-wrap: wrap; margin: 6px 0 20px; }
.cr-kpi {
  flex: 1 1 160px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px 16px;
  text-align: center !important;
}
.cr-kpi .cr-val {
  font-family: 'Share Tech Mono', monospace;
  font-size: 1.5rem;
  color: var(--cyan);
  direction: ltr;
}
.cr-kpi .cr-lbl { color: var(--text2); font-size: .78rem; margin-top: 4px; }

.cr-led {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  margin-left: 6px;
  vertical-align: middle;
}
.cr-led.online { background: var(--green); box-shadow: 0 0 8px var(--green); }
.cr-led.offline { background: var(--red); box-shadow: 0 0 8px var(--red); }

.cr-zone-title {
  color: var(--cyan) !important;
  font-size: 1.25rem;
  font-weight: 800;
  border-bottom: 2px solid var(--border);
  padding-bottom: 6px;
  margin: 6px 0 12px;
}
.cr-zone-title.alert { color: var(--red) !important; border-bottom-color: var(--red); }
.cr-zone-title.success { color: var(--green) !important; border-bottom-color: var(--green); }

.cr-alert-zone {
  border: 1px solid var(--red);
  border-radius: 14px;
  background: rgba(255,51,85,0.05);
  box-shadow: 0 0 30px rgba(255,51,85,.12);
  padding: 16px 18px 6px;
  margin-bottom: 22px;
}

.cr-alert-wrap [data-testid="stAlert"] {
  border: 1px solid var(--red) !important;
  background: rgba(255,51,85,.08) !important;
  box-shadow: 0 0 14px rgba(255,51,85,.2);
}
.cr-success-wrap [data-testid="stAlert"] {
  border: 1px solid var(--green) !important;
  background: rgba(0,255,136,.06) !important;
  box-shadow: 0 0 14px rgba(0,255,136,.15);
}
.cr-info-wrap [data-testid="stAlert"] {
  border: 1px solid var(--cyan) !important;
  background: rgba(0,212,255,.05) !important;
}

.cr-badge {
  display: inline-block;
  padding: 2px 12px;
  border-radius: 999px;
  font-size: .75rem;
  font-weight: 700;
  margin-right: 6px;
}
.cr-badge.red { background: rgba(255,51,85,.18); color: var(--red); border: 1px solid var(--red); }
.cr-badge.orange { background: rgba(255,107,53,.18); color: var(--orange); border: 1px solid var(--orange); }
.cr-badge.green { background: rgba(0,255,136,.18); color: var(--green); border: 1px solid var(--green); }
.cr-badge.cyan { background: rgba(0,212,255,.18); color: var(--cyan); border: 1px solid var(--cyan); }
.cr-badge.gray { background: rgba(122,157,181,.18); color: var(--text2); border: 1px solid var(--text3); }

.cr-card-title { font-weight: 800; color: var(--text); font-size: 1.02rem; margin-bottom: 4px; }
.cr-card-sub { color: var(--text3); font-size: .8rem; margin-bottom: 8px; font-family: 'Share Tech Mono', monospace; direction: ltr; text-align: right; }
.cr-chip { display:inline-block; background: var(--card2); border:1px solid var(--border2); color: var(--text2); border-radius:8px; padding:2px 10px; margin:2px; font-size:.78rem; }

.cr-footer { color: var(--text3); font-size: .78rem; text-align: center !important; margin-top: 30px; }
</style>
"""
