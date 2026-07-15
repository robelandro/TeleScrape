import json
import logging
from typing import List, Optional, Dict, Any
from fastmcp import FastMCP

from app.db import SessionLocal
from app.models import AnalyticsCache, TargetChannel, ExtractedJob, RawMessage
from app.nlp import extract_job_fields

logger = logging.getLogger(__name__)

mcp = FastMCP("TeleScrape")

@mcp.tool
def get_market_trends(limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieve the highest-growth developer job trends based on
    linear regression slopes calculated on scraped data."""
    db = SessionLocal()
    try:
        trends = db.query(AnalyticsCache).order_by(AnalyticsCache.growth_slope.desc()).limit(limit).all()
        return [
            {
                "job_category": t.job_category,
                "total_posts_30d": t.total_posts_30d,
                "growth_slope": t.growth_slope,
                "last_updated_at": t.last_updated_at.isoformat() if t.last_updated_at else None
            }
            for t in trends
        ]
    finally:
        db.close()

@mcp.tool
def add_telegram_source(channel_name: str) -> Dict[str, Any]:
    """Add a Telegram channel to be monitored and scraped for job postings."""
    if not channel_name.startswith("@"):
        channel_name = "@" + channel_name

    db = SessionLocal()
    try:
        existing = db.query(TargetChannel).filter_by(channel_name=channel_name).first()
        if existing:
            return {"success": False, "message": f"Channel {channel_name} is already monitored."}

        channel = TargetChannel(
            channel_name=channel_name,
            is_active=True,
            added_by=1  # Seeded default admin ID
        )
        db.add(channel)
        db.commit()
        return {"success": True, "message": f"Successfully queued {channel_name} for indexing."}
    finally:
        db.close()

@mcp.tool
def search_active_jobs(query: str, min_salary: Optional[int] = None) -> List[Dict[str, Any]]:
    """Full-text search across extracted job postings by title or skills required,
    with an optional minimum salary filter."""
    db = SessionLocal()
    try:
        # Basic filtering across job_title or skills_required
        jobs_query = db.query(ExtractedJob).filter(
            (ExtractedJob.job_title.ilike(f"%{query}%")) |
            (ExtractedJob.skills_required.ilike(f"%{query}%"))
        )
        all_jobs = jobs_query.order_by(ExtractedJob.post_date.desc()).all()

        # Helper to parse first integer from salary
        def parse_min_salary(salary_str: Optional[str]) -> Optional[int]:
            if not salary_str:
                return None
            import re
            digits = re.findall(r'\d+', salary_str.replace(',', ''))
            if digits:
                return int(digits[0])
            return None

        filtered_jobs = []
        for j in all_jobs:
            if min_salary is not None:
                num_salary = parse_min_salary(j.salary_range)
                if num_salary is None or num_salary < min_salary:
                    continue
            filtered_jobs.append({
                "id": j.id,
                "job_title": j.job_title,
                "company": j.company,
                "salary_range": j.salary_range,
                "skills_required": json.loads(j.skills_required) if j.skills_required else [],
                "post_date": j.post_date.isoformat() if j.post_date else None
            })

        return filtered_jobs
    finally:
        db.close()

# Create the HTTP App sub-application
mcp_app = mcp.http_app(path="/")
