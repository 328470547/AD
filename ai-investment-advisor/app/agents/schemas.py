"""
Structured output schemas for the AI reasoning agents.

Field *names* stay in English (so the FastAPI layer, Streamlit dashboard and
tests can address them programmatically), but every field whose value is
free text is documented as Hebrew output and suffixed `_he` - Claude is
instructed (see prompts.py) to only ever populate these with fluent,
professional financial Hebrew. Using `with_structured_output` (Anthropic
tool-calling under the hood) keeps the model honest about the schema while
still writing natural language into each field.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskLevel = Literal["גבוה", "בינוני", "נמוך"]
Sentiment = Literal["חיובי", "שלילי", "מעורב", "ניטרלי"]
HealthLevel = Literal["חזק", "בינוני", "חלש"]


class NewsSentimentAnalysis(BaseModel):
    market_sentiment: Sentiment = Field(description="הערכת הסנטימנט הכללי של השוק על סמך החדשות שסופקו")
    headline_he: str = Field(description="כותרת קצרה וממוקדת בעברית שמסכמת את מצב השוק כרגע")
    market_impact_summary_he: str = Field(
        description="סיכום ההשפעה הפוטנציאלית של החדשות על השוק, בעברית מקצועית וברורה, 3-5 משפטים"
    )
    key_drivers_he: list[str] = Field(
        default_factory=list, description="רשימת הגורמים/האירועים המרכזיים המשפיעים על השוק, כל אחד כמשפט קצר בעברית"
    )
    affected_sectors_he: list[str] = Field(
        default_factory=list, description="רשימת הסקטורים המושפעים ביותר, בעברית (למשל: טכנולוגיה, אנרגיה, פיננסים)"
    )
    reasoning_he: str = Field(
        description="שרשרת החשיבה (Chain of Thought) המפורטת שהובילה למסקנות - כיצד הכתבות הובילו להערכה, בעברית"
    )


class RiskAssessment(BaseModel):
    ticker: str
    company_name: str = ""
    risk_level: RiskLevel = Field(description="רמת הסיכון המוערכת להשקעה בנייר זה כרגע")
    is_flagged: bool = Field(description="true אם יש להציג התרעה בולטת/אדומה עבור נייר זה בדשבורד")
    warning_headline_he: str = Field(description="כותרת אזהרה קצרה, חדה וברורה בעברית (עד 12 מילים)")
    warning_detail_he: str = Field(description="הסבר מפורט של הסיכון והנימוקים העסקיים/פיננסיים, בעברית")
    red_flags_he: list[str] = Field(default_factory=list, description="רשימת דגלים אדומים קונקרטיים שזוהו, בעברית")
    reasoning_he: str = Field(description="שרשרת חשיבה מפורטת המנמקת את הערכת הסיכון צעד-אחר-צעד, בעברית")


class CompanyReportAnalysis(BaseModel):
    ticker: str
    company_name: str = ""
    fiscal_period_he: str = Field(default="", description="תקופת הדיווח, למשל 'שנת כספים 2025' או 'רבעון 3 2025'")
    financial_health: HealthLevel = Field(description="הערכה כללית של החוסן הפיננסי של החברה")
    summary_he: str = Field(description="סיכום מצבה הפיננסי של החברה על בסיס הדוח, בעברית, 3-5 משפטים")
    key_metrics_commentary_he: str = Field(
        description="פרשנות למדדים הפיננסיים המרכזיים שסופקו (הכנסות, רווח נקי, נכסים, התחייבויות, מזומן), בעברית"
    )
    reasoning_he: str = Field(description="שרשרת חשיבה מפורטת המנתחת את הנתונים ומגיעה למסקנות, בעברית")
    recommendation_he: str = Field(
        description="המלצה זהירה ומנומקת בעברית, תוך ציון מפורש שאין מדובר בייעוץ השקעות מחייב"
    )


class SmallCapOpportunity(BaseModel):
    ticker: str
    company_name: str = ""
    market_cap_usd: Optional[float] = None
    growth_thesis_he: str = Field(description="תזת הצמיחה של החברה - למה יש לה פוטנציאל, בעברית")
    reasoning_he: str = Field(description="שרשרת חשיבה המנמקת מדוע החברה מעניינת להשקעה כרגע, בעברית")
    key_risks_he: list[str] = Field(default_factory=list, description="הסיכונים המרכזיים הכרוכים בהשקעה זו, בעברית")
    opportunity_score: int = Field(ge=1, le=10, description="ציון 1 (חלש) עד 10 (מצוין) למידת האטרקטיביות")


class SmallCapScreenerResult(BaseModel):
    """Wrapper so the LLM returns one structured object instead of a bare
    list, which is more reliable with tool-calling-based structured output."""

    opportunities: list[SmallCapOpportunity] = Field(default_factory=list)


class DashboardSnapshot(BaseModel):
    """Aggregated payload for the Streamlit dashboard - one call fetches
    everything it needs to render. Each section degrades independently:
    if one agent/provider fails, its `*_error_he` is set and the other
    sections still render normally."""

    generated_at: datetime
    watchlist: list[str] = Field(default_factory=list)

    risk_alerts: list[RiskAssessment] = Field(default_factory=list)
    risk_alerts_error_he: Optional[str] = None

    news_sentiment: Optional[NewsSentimentAnalysis] = None
    news_error_he: Optional[str] = None

    company_reports: list[CompanyReportAnalysis] = Field(default_factory=list)
    company_reports_error_he: Optional[str] = None

    smallcap_opportunities: list[SmallCapOpportunity] = Field(default_factory=list)
    smallcap_error_he: Optional[str] = None
