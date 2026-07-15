import os
import re
import datetime
import asyncio
import logging
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from app.db import get_db, engine, SessionLocal
from app.models import Base, User, TargetChannel, RawMessage, ExtractedJob, AnalyticsCache
from app.schemas import (
    UserCreate, UserResponse, Token, LoginRequest,
    ChannelCreate, ChannelResponse, JobResponse,
    DashboardSummaryResponse, DashboardChartsResponse, ChartDataPoint
)
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user, get_admin_user
from app.scraper import run_scrape_cycle
from app.mcp_server import mcp_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Startup:
    logger.info("Starting background scheduler...")
    scheduler.add_job(trigger_scrape, "interval", minutes=30, id="scrape_job")
    scheduler.start()

    import threading
    threading.Thread(target=trigger_scrape, daemon=True).start()

    # Delegate to mcp_app lifespan for session manager initialization
    async with mcp_app.lifespan(app_instance):
        yield

    # Shutdown:
    logger.info("Shutting down background scheduler...")
    scheduler.shutdown()

app = FastAPI(title="TeleScrape Local Job Analytics API", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local ease of use, let React frontend connect
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background scheduler
scheduler = BackgroundScheduler()

def trigger_scrape():
    db = SessionLocal()
    try:
        # Run async scraper in new event loop
        asyncio.run(run_scrape_cycle(db))
    except Exception as e:
        logger.exception(f"Scheduler scraper job failed: {e}")
    finally:
        db.close()

# Mount MCP Server
app.mount("/mcp", mcp_app)

# --- AUTH ENDPOINTS ---

@app.post("/api/auth/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    # Check if username already exists
    existing = db.query(User).filter_by(username=user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")

    user = User(
        username=user_in.username,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role or "viewer"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.post("/api/auth/login", response_model=Token)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    token = create_access_token(data={"sub": user.username})
    return Token(token=token, username=user.username, role=user.role)

# --- CHANNELS ENDPOINTS ---

@app.get("/api/channels", response_model=List[ChannelResponse])
def get_channels(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(TargetChannel).all()

@app.post("/api/channels", response_model=ChannelResponse)
def add_channel(channel_in: ChannelCreate, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    existing = db.query(TargetChannel).filter_by(channel_name=channel_in.channel_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel already monitored")

    channel = TargetChannel(
        channel_name=channel_in.channel_name,
        is_active=True,
        added_by=current_user.id
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel

@app.delete("/api/channels/{channel_id}")
def delete_channel(channel_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    channel = db.query(TargetChannel).filter_by(id=channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Also clean up associated raw messages & jobs if desired, or just delete channel
    # Delete associated ExtractedJob and RawMessage
    raws = db.query(RawMessage).filter_by(channel_id=channel_id).all()
    for r in raws:
        db.query(ExtractedJob).filter_by(raw_message_id=r.id).delete()
    db.query(RawMessage).filter_by(channel_id=channel_id).delete()

    db.delete(channel)
    db.commit()
    return {"success": True, "message": "Channel and associated data deleted"}

# --- JOBS ENDPOINTS ---

def parse_min_salary(salary_str: Optional[str]) -> Optional[int]:
    if not salary_str:
        return None
    # Find all digits in the string
    digits = re.findall(r'\d+', salary_str.replace(',', ''))
    if digits:
        # Return first numerical value (usually the lower bound)
        return int(digits[0])
    return None

@app.get("/api/jobs")
def get_jobs(
    limit: int = 50,
    offset: int = 0,
    title: Optional[str] = "",
    min_salary: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ExtractedJob)
    if title:
        query = query.filter(ExtractedJob.job_title.ilike(f"%{title}%"))

    all_jobs = query.order_by(ExtractedJob.post_date.desc()).all()

    # Filter by min_salary in python because of text-based salary ranges in DB
    filtered_jobs = []
    for job in all_jobs:
        if min_salary is not None:
            num_salary = parse_min_salary(job.salary_range)
            if num_salary is None or num_salary < min_salary:
                continue
        filtered_jobs.append(job)

    total = len(filtered_jobs)
    paginated = filtered_jobs[offset:offset+limit]

    return {
        "total": total,
        "jobs": [
            JobResponse(
                id=j.id,
                job_title=j.job_title,
                company=j.company,
                salary_range=j.salary_range,
                skills_required=j.skills_required,
                post_date=j.post_date
            ) for j in paginated
        ]
    }

# --- DASHBOARD ENDPOINTS ---

@app.get("/api/dashboard/summary", response_model=DashboardSummaryResponse)
def get_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total_jobs = db.query(ExtractedJob).count()
    monitored_sources = db.query(TargetChannel).filter_by(is_active=True).count()

    # Get fastest growing
    fastest = db.query(AnalyticsCache).order_by(AnalyticsCache.growth_slope.desc()).first()
    if fastest and fastest.growth_slope > 0:
        fastest_growing = f"{fastest.job_category} (+{fastest.growth_slope:.1f} posts/week)"
    else:
        fastest_growing = "N/A"

    return DashboardSummaryResponse(
        total_jobs_scraped=total_jobs,
        monitored_sources=monitored_sources,
        fastest_growing=fastest_growing
    )

@app.get("/api/dashboard/charts", response_model=DashboardChartsResponse)
def get_charts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 1. Volume by day (last 14 days)
    today = datetime.date.today()
    fourteen_days_ago = today - datetime.timedelta(days=14)

    daily_counts = db.query(
        ExtractedJob.post_date,
        func.count(ExtractedJob.id)
    ).filter(
        ExtractedJob.post_date >= fourteen_days_ago
    ).group_by(ExtractedJob.post_date).order_by(ExtractedJob.post_date.asc()).all()

    volume_by_day = []
    # Fill in any missing dates with 0 counts to make beautiful charts
    date_map = {r[0]: r[1] for r in daily_counts}
    for i in range(15):
        d = fourteen_days_ago + datetime.timedelta(days=i)
        volume_by_day.append(ChartDataPoint(
            date_str=d.strftime("%Y-%m-%d"),
            post_count=date_map.get(d, 0)
        ))

    # 2. Category trends by day (last 14 days)
    trends_query = db.query(
        ExtractedJob.post_date,
        ExtractedJob.job_title,
        func.count(ExtractedJob.id)
    ).filter(
        ExtractedJob.post_date >= fourteen_days_ago
    ).group_by(ExtractedJob.post_date, ExtractedJob.job_title).all()

    # Recharts friendly list of dicts: [{"date_str": "2026-07-15", "Python Developer": 5, "React Engineer": 3}]
    # Collect all unique categories in this timeframe
    categories = sorted(list(set(r[1] for r in trends_query if r[1])))

    category_trends = []
    # Initialize trend map for each of the last 14 days
    for i in range(15):
        d = fourteen_days_ago + datetime.timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        day_dict = {"date_str": d_str}
        for cat in categories:
            day_dict[cat] = 0
        category_trends.append(day_dict)

    for r in trends_query:
        d_str = r[0].strftime("%Y-%m-%d")
        cat = r[1]
        count = r[2]
        for item in category_trends:
            if item["date_str"] == d_str:
                item[cat] = count
                break

    return DashboardChartsResponse(
        volume_by_day=volume_by_day,
        category_trends=category_trends
    )
