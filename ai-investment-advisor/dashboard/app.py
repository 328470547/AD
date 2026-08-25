"""
AI Investment Advisor - Streamlit dashboard (Phase 4).

Control-room style monitoring dashboard, fully RTL and in Hebrew, that
consumes the FastAPI backend's aggregated /api/dashboard/snapshot endpoint
(Phase 2 data services + Phase 3 Claude-powered agents) and renders:

  1. A always-on-top "Risk Alerts" zone (st.error) for flagged/high-risk
     names - the single most important thing a user should see first.
  2. Real-time news + market sentiment.
  3. AI reasoning / daily SEC report summaries per company.
  4. Small-cap opportunities, highlighted in green (st.success).
  5. An on-demand deep-dive search box for any single ticker.

Run with:  streamlit run dashboard/app.py
(the FastAPI backend must be running separately: uvicorn app.main:app)
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

# `streamlit run dashboard/app.py` only adds this file's own directory to
# sys.path, not the project root - add it explicitly so the package-style
# imports below (dashboard.api_client, dashboard.styles) resolve regardless
# of the working directory the app is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.api_client import (
    API_BASE_URL,
    BackendError,
    fetch_dashboard_snapshot,
    fetch_health,
    fetch_report_analysis,
    fetch_risk_assessment,
)
from dashboard.styles import CUSTOM_CSS

SENTIMENT_COLOR = {"חיובי": "green", "שלילי": "red", "מעורב": "orange", "ניטרלי": "gray"}
RISK_COLOR = {"גבוה": "red", "בינוני": "orange", "נמוך": "green"}
HEALTH_COLOR = {"חזק": "green", "בינוני": "orange", "חלש": "red"}

DISCLAIMER_HE = (
    "⚠️ המידע המוצג במערכת זו הופק על-ידי בינה מלאכותית לצרכי מידע בלבד, "
    "ואינו מהווה ייעוץ השקעות מוסמך. יש לבצע בדיקת נאותות עצמאית ולהתייעץ "
    "עם בעל רישיון לפני כל החלטת השקעה."
)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def format_money(value: float | None) -> str:
    if value is None:
        return "לא ידוע"
    value = float(value)
    abs_v = abs(value)
    if abs_v >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if abs_v >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs_v >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if abs_v >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.2f}"


def format_time(iso_str: str | None) -> str:
    if not iso_str:
        return "—"
    try:
        return datetime.fromisoformat(iso_str).strftime("%H:%M:%S")
    except ValueError:
        return iso_str


def badge(text: str, color: str) -> str:
    return f'<span class="cr-badge {color}">{text}</span>'


def chips(items: list[str], icon: str = "") -> str:
    prefix = f"{icon} " if icon else ""
    return " ".join(f'<span class="cr-chip">{prefix}{item}</span>' for item in items)


# ---------------------------------------------------------------------------
# Zone renderers
# ---------------------------------------------------------------------------
def render_header() -> None:
    st.markdown(
        """
        <div class="cr-header">
            <h1>📈 יועץ ההשקעות מבוסס בינה מלאכותית</h1>
            <p>חדר בקרה למעקב שוק בזמן אמת — חדשות, סיכונים, דוחות כספיים והזדמנויות צמיחה, מונע על-ידי Claude</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_bar(snapshot: dict | None, backend_online: bool) -> None:
    watchlist = snapshot.get("watchlist", []) if snapshot else []
    alerts = snapshot.get("risk_alerts", []) if snapshot else []
    flagged = [a for a in alerts if a.get("is_flagged") or a.get("risk_level") == "גבוה"]
    smallcap_count = len(snapshot.get("smallcap_opportunities", [])) if snapshot else 0
    reports_count = len(snapshot.get("company_reports", [])) if snapshot else 0
    updated = format_time(snapshot.get("generated_at")) if snapshot else "—"

    led_class = "online" if backend_online else "offline"
    led_label = "מחובר" if backend_online else "מנותק"

    st.markdown(
        f"""
        <div class="cr-status-row">
            <div class="cr-kpi"><div class="cr-val"><span class="cr-led {led_class}"></span>{led_label}</div>
                <div class="cr-lbl">סטטוס שרת</div></div>
            <div class="cr-kpi"><div class="cr-val">{len(watchlist)}</div><div class="cr-lbl">מניות במעקב</div></div>
            <div class="cr-kpi"><div class="cr-val" style="color:var(--red)">{len(flagged)}</div>
                <div class="cr-lbl">התרעות סיכון</div></div>
            <div class="cr-kpi"><div class="cr-val" style="color:var(--green)">{smallcap_count}</div>
                <div class="cr-lbl">הזדמנויות Small-Cap</div></div>
            <div class="cr-kpi"><div class="cr-val">{reports_count}</div><div class="cr-lbl">דוחות שנותחו</div></div>
            <div class="cr-kpi"><div class="cr-val">{updated}</div><div class="cr-lbl">עדכון אחרון (UTC)</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_risk_distribution_chart(alerts: list[dict]) -> None:
    """Small horizontal bar chart summarizing risk levels across the
    watchlist - styled to match the control-room dark theme and laid out
    so the Hebrew title/labels read correctly in an RTL page."""
    if not alerts:
        return

    counts = Counter(a.get("risk_level", "לא ידוע") for a in alerts)
    order = ["גבוה", "בינוני", "נמוך"]
    levels = [lvl for lvl in order if lvl in counts] + [lvl for lvl in counts if lvl not in order]
    values = [counts[lvl] for lvl in levels]
    color_map = {"גבוה": "#ff3355", "בינוני": "#ff6b35", "נמוך": "#00ff88"}
    bar_colors = [color_map.get(lvl, "#7a9db5") for lvl in levels]

    fig = go.Figure(
        go.Bar(x=values, y=levels, orientation="h", marker_color=bar_colors, text=values, textposition="outside")
    )
    fig.update_layout(
        title=dict(text="התפלגות רמות סיכון ברשימת המעקב", x=0.98, xanchor="right", font=dict(color="#00d4ff")),
        paper_bgcolor="#0d1f30",
        plot_bgcolor="#0d1f30",
        font=dict(family="Assistant, sans-serif", color="#c8e0f0"),
        height=220,
        margin=dict(l=90, r=10, t=45, b=10),
        yaxis=dict(autorange="reversed", automargin=True, tickfont=dict(size=14)),
        xaxis=dict(gridcolor="#1a3a5c"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_risk_alerts_zone(snapshot: dict | None) -> None:
    st.markdown('<div class="cr-alert-zone">', unsafe_allow_html=True)
    st.markdown('<div class="cr-zone-title alert">🚨 התרעות וסיכונים</div>', unsafe_allow_html=True)

    if snapshot is None:
        st.warning("לא ניתן להציג התרעות סיכון - אין חיבור לשרת ה-Backend.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    error_he = snapshot.get("risk_alerts_error_he")
    if error_he:
        st.warning(f"⚠️ {error_he}")

    alerts = snapshot.get("risk_alerts", [])
    flagged = [a for a in alerts if a.get("is_flagged") or a.get("risk_level") == "גבוה"]
    medium = [a for a in alerts if a not in flagged and a.get("risk_level") == "בינוני"]

    if not error_he and not flagged:
        st.success("✅ לא זוהו כרגע התרעות סיכון גבוהות בקרב המניות שנבדקו.")

    for a in flagged:
        st.markdown('<div class="cr-alert-wrap">', unsafe_allow_html=True)
        st.error(
            f"**{a.get('ticker', '')} — {a.get('company_name') or ''}**\n\n"
            f"**{a.get('warning_headline_he', '')}**\n\n{a.get('warning_detail_he', '')}"
        )
        st.markdown("</div>", unsafe_allow_html=True)
        red_flags = a.get("red_flags_he") or []
        if red_flags:
            st.markdown(chips(red_flags, "🚩"), unsafe_allow_html=True)
        with st.expander(f"שרשרת החשיבה של סוכן ניהול הסיכונים — {a.get('ticker', '')}"):
            st.write(a.get("reasoning_he", ""))

    if medium:
        with st.expander(f"סיכון בינוני ({len(medium)} ניירות נוספים) — לחצו להרחבה"):
            for a in medium:
                st.markdown(f"**{a.get('ticker', '')}** — {a.get('warning_headline_he', '')}")
                st.caption(a.get("warning_detail_he", ""))

    render_risk_distribution_chart(alerts)
    st.markdown("</div>", unsafe_allow_html=True)


def render_news_zone(snapshot: dict | None) -> None:
    st.markdown('<div class="cr-zone-title">📰 חדשות שוק וסנטימנט</div>', unsafe_allow_html=True)
    if snapshot is None:
        st.info("אין חיבור לשרת.")
        return

    news = snapshot.get("news_sentiment")
    error_he = snapshot.get("news_error_he")
    if not news:
        st.warning(f"⚠️ {error_he or 'לא נמצא ניתוח חדשות זמין כרגע.'}")
        return

    color = SENTIMENT_COLOR.get(news.get("market_sentiment"), "gray")
    st.markdown(badge(f"סנטימנט: {news.get('market_sentiment', '')}", color), unsafe_allow_html=True)
    st.markdown(f"#### {news.get('headline_he', '')}")
    st.write(news.get("market_impact_summary_he", ""))

    drivers = news.get("key_drivers_he") or []
    if drivers:
        st.markdown("**גורמים מרכזיים:**")
        st.markdown(chips(drivers), unsafe_allow_html=True)

    sectors = news.get("affected_sectors_he") or []
    if sectors:
        st.markdown("**סקטורים מושפעים:**")
        st.markdown(chips(sectors), unsafe_allow_html=True)

    with st.expander("שרשרת החשיבה של סוכן ניתוח החדשות"):
        st.write(news.get("reasoning_he", ""))


def render_reports_zone(snapshot: dict | None) -> None:
    st.markdown('<div class="cr-zone-title">📄 ניתוח דוחות SEC ובריאות פיננסית</div>', unsafe_allow_html=True)
    if snapshot is None:
        st.info("אין חיבור לשרת.")
        return

    reports = snapshot.get("company_reports", [])
    error_he = snapshot.get("company_reports_error_he")
    if not reports:
        st.warning(f"⚠️ {error_he or 'לא נמצאו ניתוחי דוחות זמינים כרגע.'}")
        return

    for r in reports:
        color = HEALTH_COLOR.get(r.get("financial_health"), "gray")
        st.markdown(
            f'<div class="cr-card-title">{r.get("ticker", "")} — {r.get("company_name") or ""}</div>'
            f'<div class="cr-card-sub">{r.get("fiscal_period_he") or ""}</div>'
            + badge(f"בריאות פיננסית: {r.get('financial_health', '')}", color),
            unsafe_allow_html=True,
        )
        st.write(r.get("summary_he", ""))
        st.caption(r.get("key_metrics_commentary_he", ""))
        st.markdown(f"*{r.get('recommendation_he', '')}*")
        with st.expander(f"שרשרת החשיבה — {r.get('ticker', '')}"):
            st.write(r.get("reasoning_he", ""))
        st.divider()


def render_smallcap_zone(snapshot: dict | None) -> None:
    st.markdown('<div class="cr-zone-title success">🌱 הזדמנויות Small-Cap</div>', unsafe_allow_html=True)
    if snapshot is None:
        st.info("אין חיבור לשרת.")
        return

    opportunities = snapshot.get("smallcap_opportunities", [])
    error_he = snapshot.get("smallcap_error_he")
    if not opportunities:
        st.warning(f"⚠️ {error_he or 'לא נמצאו הזדמנויות Small-Cap התואמות את הקריטריונים כרגע.'}")
        return

    for o in opportunities:
        st.markdown('<div class="cr-success-wrap">', unsafe_allow_html=True)
        st.success(
            f"**{o.get('ticker', '')} — {o.get('company_name') or ''}**  \n"
            f"שווי שוק: {format_money(o.get('market_cap_usd'))}\n\n"
            f"{o.get('growth_thesis_he', '')}"
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.progress(
            min(max(o.get("opportunity_score", 0), 0), 10) / 10,
            text=f"ציון אטרקטיביות: {o.get('opportunity_score', 0)}/10",
        )
        risks = o.get("key_risks_he") or []
        if risks:
            st.markdown(chips(risks, "⚠️"), unsafe_allow_html=True)
        with st.expander(f"שרשרת החשיבה — {o.get('ticker', '')}"):
            st.write(o.get("reasoning_he", ""))
        st.markdown("")


def render_ticker_deep_dive() -> None:
    st.markdown('<div class="cr-zone-title">🔍 ניתוח מעמיק לפי טיקר</div>', unsafe_allow_html=True)
    col_input, col_button = st.columns([4, 1])
    with col_input:
        ticker = st.text_input(
            "הזינו טיקר לניתוח", placeholder="לדוגמה: AAPL", label_visibility="collapsed", key="deep_dive_ticker"
        )
    with col_button:
        run = st.button("🔎 נתח", use_container_width=True)

    if not (run and ticker.strip()):
        return

    ticker = ticker.strip().upper()
    with st.spinner(f"מריץ ניתוח AI עבור {ticker}... (עשוי לקחת מספר עשרות שניות)"):
        risk, risk_error = None, None
        report, report_error = None, None
        try:
            risk = fetch_risk_assessment(ticker)
        except BackendError as exc:
            risk_error = exc.message_he
        try:
            report = fetch_report_analysis(ticker)
        except BackendError as exc:
            report_error = exc.message_he

    col_risk, col_report = st.columns(2, gap="medium")
    with col_risk:
        st.markdown("##### הערכת סיכון")
        if risk_error:
            st.warning(f"⚠️ {risk_error}")
        elif risk:
            color = RISK_COLOR.get(risk.get("risk_level"), "gray")
            st.markdown(badge(f"רמת סיכון: {risk.get('risk_level', '')}", color), unsafe_allow_html=True)
            st.write(risk.get("warning_detail_he", ""))
            red_flags = risk.get("red_flags_he") or []
            if red_flags:
                st.markdown(chips(red_flags, "🚩"), unsafe_allow_html=True)
            with st.expander("שרשרת חשיבה"):
                st.write(risk.get("reasoning_he", ""))

    with col_report:
        st.markdown("##### ניתוח דוח כספי")
        if report_error:
            st.warning(f"⚠️ {report_error}")
        elif report:
            color = HEALTH_COLOR.get(report.get("financial_health"), "gray")
            st.markdown(badge(f"בריאות פיננסית: {report.get('financial_health', '')}", color), unsafe_allow_html=True)
            st.write(report.get("summary_he", ""))
            with st.expander("שרשרת חשיבה"):
                st.write(report.get("reasoning_he", ""))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title="יועץ השקעות AI",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### ⚙️ לוח בקרה")
        st.caption(f"מחובר לשרת: `{API_BASE_URL}`")
        tickers_input = st.text_input(
            "רשימת מעקב (טיקרים מופרדים בפסיק)", value="", placeholder="AAPL,TSLA,GME,PLTR"
        )
        st.caption("השאירו ריק כדי להשתמש ברשימת המעקב המוגדרת בשרת.")
        auto_refresh = st.toggle("🔄 רענון אוטומטי כל 60 שניות", value=False)
        if st.button("רענן נתונים עכשיו", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.caption(DISCLAIMER_HE)

    render_header()

    backend_online = True
    try:
        fetch_health()
    except BackendError:
        backend_online = False

    snapshot: dict | None = None
    if backend_online:
        try:
            snapshot = fetch_dashboard_snapshot(tickers_input.strip() or None)
        except BackendError as exc:
            st.error(f"⚠️ שגיאה בטעינת נתוני הדשבורד: {exc.message_he}")
    else:
        st.error(
            f"🔌 לא ניתן להתחבר לשרת ה-Backend בכתובת `{API_BASE_URL}`. "
            "ודאו שהשרת פעיל (הריצו: `uvicorn app.main:app --reload`) ולחצו על 'רענן נתונים עכשיו'."
        )

    render_status_bar(snapshot, backend_online)
    render_risk_alerts_zone(snapshot)

    col_news, col_reports, col_smallcap = st.columns(3, gap="medium")
    with col_news:
        render_news_zone(snapshot)
    with col_reports:
        render_reports_zone(snapshot)
    with col_smallcap:
        render_smallcap_zone(snapshot)

    st.divider()
    render_ticker_deep_dive()

    st.markdown(
        '<div class="cr-footer">יועץ השקעות AI &middot; מונע על-ידי Claude &middot; המידע אינו מהווה ייעוץ השקעות</div>',
        unsafe_allow_html=True,
    )

    if auto_refresh:
        time.sleep(60)
        st.rerun()


if __name__ == "__main__":
    main()
