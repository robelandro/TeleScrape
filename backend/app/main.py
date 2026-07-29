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
from app.models import Base, User, TargetChannel, RawMessage, ExtractedJob, AnalyticsCache, Config
from app.crypto import encrypt_value, decrypt_value
from app.schemas import (
    UserCreate, UserResponse, Token, LoginRequest,
    ChannelCreate, ChannelResponse, JobResponse,
    DashboardSummaryResponse, DashboardChartsResponse, ChartDataPoint,
    TelegramConfig, SendCodeRequest, LoginCodeRequest, ScrapeRequest
)
import json
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user, get_admin_user
from app.scraper import run_scrape_cycle, start_listener, stop_listener, restart_listener_sync, start_channel_scrape_task, cancel_channel_scrape_task, active_scrapes
from app.mcp_server import mcp_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Startup:
    logger.info("Starting background scheduler...")
    interval_minutes = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "30"))
    scheduler.add_job(trigger_scrape, "interval", minutes=interval_minutes, id="scrape_job")
    scheduler.start()

    import threading
    threading.Thread(target=trigger_scrape, daemon=True).start()

    # Start real-time listener
    asyncio.create_task(start_listener())

    # Delegate to mcp_app lifespan for session manager initialization
    async with mcp_app.lifespan(app_instance):
        yield

    # Shutdown:
    logger.info("Shutting down real-time listener...")
    await stop_listener()

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

# Telegram Config Endpoints
@app.post("/api/telegram/config")
def update_telegram_config(config: TelegramConfig, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    # Save TG_API_ID (raw)
    api_id_config = db.query(Config).filter_by(key="TG_API_ID", user_id=current_user.id).first()
    if not api_id_config:
        api_id_config = Config(key="TG_API_ID", user_id=current_user.id)
        db.add(api_id_config)
    api_id_config.value = config.api_id
    api_id_config.encrypt_type = "raw"

    # Save TG_API_HASH (encrypted)
    api_hash_config = db.query(Config).filter_by(key="TG_API_HASH", user_id=current_user.id).first()
    if not api_hash_config:
        api_hash_config = Config(key="TG_API_HASH", user_id=current_user.id)
        db.add(api_hash_config)
    api_hash_config.value = encrypt_value(config.api_hash)
    api_hash_config.encrypt_type = "encrypted"

    db.commit()

    # Also update the current env for immediate usage
    os.environ["TG_API_ID"] = config.api_id
    os.environ["TG_API_HASH"] = config.api_hash
    if config.api_id and config.api_hash:
        os.environ["SIMULATION_MODE"] = "false"

    return {"message": "Telegram configuration saved to database"}

@app.get("/api/telegram/config")
def get_telegram_config(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")

    api_id_config = db.query(Config).filter_by(key="TG_API_ID", user_id=current_user.id).first()
    api_hash_config = db.query(Config).filter_by(key="TG_API_HASH", user_id=current_user.id).first()

    if api_id_config:
        api_id = api_id_config.value
    if api_hash_config:
        if api_hash_config.encrypt_type == "encrypted":
            try:
                api_hash = decrypt_value(api_hash_config.value)
            except Exception:
                api_hash = None
        else:
            api_hash = api_hash_config.value

    return {"is_configured": bool(api_id and api_hash), "api_id": api_id}

@app.delete("/api/telegram/config")
def delete_telegram_config(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    db.query(Config).filter(Config.key.in_(["TG_API_ID", "TG_API_HASH", "TG_SESSION"]), Config.user_id == current_user.id).delete(synchronize_session=False)
    db.commit()

    if "TG_API_ID" in os.environ:
        del os.environ["TG_API_ID"]
    if "TG_API_HASH" in os.environ:
        del os.environ["TG_API_HASH"]
    os.environ["SIMULATION_MODE"] = "true"

    restart_listener_sync()

    return {"message": "Telegram configuration removed"}

@app.post("/api/telegram/auth/send_code")
async def send_telegram_code(req: SendCodeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    # Retrieve api_id and api_hash from DB
    api_id_config = db.query(Config).filter_by(key="TG_API_ID", user_id=current_user.id).first()
    api_hash_config = db.query(Config).filter_by(key="TG_API_HASH", user_id=current_user.id).first()

    if not api_id_config or not api_hash_config:
        raise HTTPException(status_code=400, detail="Telegram API ID and Hash must be configured first.")

    api_id = int(api_id_config.value)
    api_hash = decrypt_value(api_hash_config.value) if api_hash_config.encrypt_type == "encrypted" else api_hash_config.value

    # Create client with new StringSession
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    try:
        sent_code = await client.send_code_request(req.phone_number)

        # Temporarily store the session string and phone_code_hash
        session_str = client.session.save()

        pending_session = db.query(Config).filter_by(key="TG_PENDING_SESSION", user_id=current_user.id).first()
        if not pending_session:
            pending_session = Config(key="TG_PENDING_SESSION", user_id=current_user.id)
            db.add(pending_session)
        pending_session.value = encrypt_value(session_str)
        pending_session.encrypt_type = "encrypted"

        db.commit()

        return {"phone_code_hash": sent_code.phone_code_hash}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.disconnect()

@app.post("/api/telegram/auth/login")
async def login_telegram(req: LoginCodeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    api_id_config = db.query(Config).filter_by(key="TG_API_ID", user_id=current_user.id).first()
    api_hash_config = db.query(Config).filter_by(key="TG_API_HASH", user_id=current_user.id).first()
    pending_session_config = db.query(Config).filter_by(key="TG_PENDING_SESSION", user_id=current_user.id).first()

    if not api_id_config or not api_hash_config or not pending_session_config:
        raise HTTPException(status_code=400, detail="Missing configuration or pending session.")

    api_id = int(api_id_config.value)
    api_hash = decrypt_value(api_hash_config.value) if api_hash_config.encrypt_type == "encrypted" else api_hash_config.value
    session_str = decrypt_value(pending_session_config.value) if pending_session_config.encrypt_type == "encrypted" else pending_session_config.value

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.connect()

    try:
        try:
            await client.sign_in(phone=req.phone_number, phone_code_hash=req.phone_code_hash, code=req.code)
        except SessionPasswordNeededError:
            if not req.password:
                raise HTTPException(status_code=401, detail="2FA Password required")
            await client.sign_in(password=req.password)

        # Save authorized session
        auth_session_str = client.session.save()
        auth_session = db.query(Config).filter_by(key="TG_SESSION", user_id=current_user.id).first()
        if not auth_session:
            auth_session = Config(key="TG_SESSION", user_id=current_user.id)
            db.add(auth_session)
        auth_session.value = encrypt_value(auth_session_str)
        auth_session.encrypt_type = "encrypted"

        # Cleanup pending
        db.delete(pending_session_config)
        db.commit()

        restart_listener_sync()

        return {"message": "Logged in successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.disconnect()

@app.post("/api/telegram/auth/logout")
async def logout_telegram(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    api_id_config = db.query(Config).filter_by(key="TG_API_ID", user_id=current_user.id).first()
    api_hash_config = db.query(Config).filter_by(key="TG_API_HASH", user_id=current_user.id).first()
    auth_session_config = db.query(Config).filter_by(key="TG_SESSION", user_id=current_user.id).first()

    if not auth_session_config:
        return {"message": "Not logged in"}

    api_id = int(api_id_config.value)
    api_hash = decrypt_value(api_hash_config.value) if api_hash_config.encrypt_type == "encrypted" else api_hash_config.value
    session_str = decrypt_value(auth_session_config.value) if auth_session_config.encrypt_type == "encrypted" else auth_session_config.value

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    await client.connect()
    try:
        await client.log_out()
    except Exception:
        pass # Ignore errors if already logged out remotely
    finally:
        await client.disconnect()

    # Delete from DB
    db.delete(auth_session_config)
    db.commit()

    restart_listener_sync()

    return {"message": "Logged out successfully"}

@app.get("/api/telegram/auth/status")
def get_telegram_auth_status(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    auth_session_config = db.query(Config).filter_by(key="TG_SESSION", user_id=current_user.id).first()
    return {"is_logged_in": bool(auth_session_config)}

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

    restart_listener_sync()
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

    restart_listener_sync()
    return {"success": True, "message": "Channel and associated data deleted"}

@app.post("/api/channels/{channel_id}/scrape")
async def trigger_channel_scrape(channel_id: int, scrape_req: ScrapeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    channel = db.query(TargetChannel).filter_by(id=channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        start_channel_scrape_task(channel_id, scrape_req.start_date, scrape_req.end_date)
        return {"success": True, "message": f"Scrape started for channel {channel.channel_name}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/channels/{channel_id}/cancel_scrape")
async def cancel_channel_scrape(channel_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    if cancel_channel_scrape_task(channel_id):
        return {"success": True, "message": "Scrape task cancelled."}
    else:
        raise HTTPException(status_code=400, detail="No active scrape task found for this channel.")

@app.get("/api/channels/{channel_id}/scrape_status")
def get_channel_scrape_status(channel_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"is_scraping": channel_id in active_scrapes}

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
