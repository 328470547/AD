"""
Smoke tests for the Streamlit dashboard using Streamlit's own headless
AppTest harness - runs dashboard/app.py end-to-end with the backend HTTP
calls mocked, and asserts the script executes without raising (this is
exactly the class of bug a manual screenshot check can miss, e.g. the
sys.path import bug and the "risk section silently looks empty on total
failure" bug both found during manual verification).
"""
from datetime import datetime, timezone
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from dashboard.api_client import BackendError

FAKE_SNAPSHOT = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "watchlist": ["AAPL", "PENNY"],
    "risk_alerts": [
        {
            "ticker": "PENNY",
            "company_name": "Penny Corp",
            "risk_level": "גבוה",
            "is_flagged": True,
            "warning_headline_he": "הפסדים מתמשכים ותזרים מזומנים שלילי",
            "warning_detail_he": "החברה מציגה הפסדים משמעותיים לאורך מספר רבעונים.",
            "red_flags_he": ["הפסד נקי", "חוב גבוה"],
            "reasoning_he": "בהתבסס על הנתונים הפיננסיים, קיים סיכון גבוה.",
        }
    ],
    "risk_alerts_error_he": None,
    "news_sentiment": {
        "market_sentiment": "מעורב",
        "headline_he": "השוק במגמה מעורבת על רקע נתוני אינפלציה",
        "market_impact_summary_he": "נתוני האינפלציה שהתפרסמו יצרו תגובה מעורבת בשווקים.",
        "key_drivers_he": ["נתוני אינפלציה", "ציפיות ריבית"],
        "affected_sectors_he": ["טכנולוגיה", "פיננסים"],
        "reasoning_he": "שרשרת חשיבה לדוגמה עבור ניתוח החדשות.",
    },
    "news_error_he": None,
    "company_reports": [
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc",
            "fiscal_period_he": "שנת כספים 2025",
            "financial_health": "חזק",
            "summary_he": "החברה מציגה יציבות פיננסית ורווחיות גבוהה.",
            "key_metrics_commentary_he": "ההכנסות והרווח הנקי במגמת עלייה יציבה.",
            "reasoning_he": "שרשרת חשיבה לדוגמה עבור ניתוח הדוח.",
            "recommendation_he": "ניתוח זה אינו מהווה ייעוץ השקעות מחייב.",
        }
    ],
    "company_reports_error_he": None,
    "smallcap_opportunities": [
        {
            "ticker": "PENNY",
            "company_name": "Penny Corp",
            "market_cap_usd": 400_000_000,
            "growth_thesis_he": "החברה פועלת בשוק נישתי צומח במהירות.",
            "reasoning_he": "שרשרת חשיבה לדוגמה עבור הזדמנות ה-small-cap.",
            "key_risks_he": ["תחרות גוברת"],
            "opportunity_score": 7,
        }
    ],
    "smallcap_error_he": None,
}


def test_dashboard_renders_happy_path_without_exception():
    with patch("dashboard.api_client.fetch_health", return_value={"status": "ok"}), patch(
        "dashboard.api_client.fetch_dashboard_snapshot", return_value=FAKE_SNAPSHOT
    ):
        at = AppTest.from_file("../dashboard/app.py")
        at.run(timeout=30)
    assert not at.exception
    body = "\n".join(md.value for md in at.markdown)
    assert "התרעות וסיכונים" in body


def test_dashboard_renders_backend_offline_state_without_exception():
    with patch("dashboard.api_client.fetch_health", side_effect=BackendError("השרת אינו זמין")):
        at = AppTest.from_file("../dashboard/app.py")
        at.run(timeout=30)
    assert not at.exception
    assert any("לא ניתן להתחבר" in e.value for e in at.error)


def test_dashboard_renders_partial_section_failures_without_exception():
    partial_snapshot = dict(FAKE_SNAPSHOT)
    partial_snapshot["risk_alerts"] = []
    partial_snapshot["risk_alerts_error_he"] = "לא ניתן היה להפיק הערכות סיכון עבור אף אחד מהניירות ברשימת המעקב."
    with patch("dashboard.api_client.fetch_health", return_value={"status": "ok"}), patch(
        "dashboard.api_client.fetch_dashboard_snapshot", return_value=partial_snapshot
    ):
        at = AppTest.from_file("../dashboard/app.py")
        at.run(timeout=30)
    assert not at.exception
    assert any("לא ניתן היה להפיק הערכות סיכון" in w.value for w in at.warning)
