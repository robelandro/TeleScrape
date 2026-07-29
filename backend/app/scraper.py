import os
import asyncio
import random
import datetime
import logging
from sqlalchemy import func
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

from app.db import SessionLocal
from app.models import TargetChannel, RawMessage, ExtractedJob
from app.nlp import extract_job_fields_llm
from app.forecasting import recompute_all_trend_slopes

logger = logging.getLogger(__name__)

from telethon.sessions import StringSession
from app.models import Config
from app.crypto import decrypt_value

def get_telegram_credentials(session):
    # Fetch admin user implicitly for now, as jobs run in background
    # Usually there is only one admin running the system, or we can fetch the first valid cred
    api_id_config = session.query(Config).filter_by(key="TG_API_ID").first()
    api_hash_config = session.query(Config).filter_by(key="TG_API_HASH").first()
    session_config = session.query(Config).filter_by(key="TG_SESSION").first()

    api_id = api_id_config.value if api_id_config else os.getenv("TG_API_ID")
    api_hash = None
    if api_hash_config:
        api_hash = decrypt_value(api_hash_config.value) if api_hash_config.encrypt_type == "encrypted" else api_hash_config.value
    else:
        api_hash = os.getenv("TG_API_HASH")

    session_str = None
    if session_config:
        session_str = decrypt_value(session_config.value) if session_config.encrypt_type == "encrypted" else session_config.value

    return api_id, api_hash, session_str

# Mock postings templates
MOCK_JOBS_TEMPLATES = [
    {
        "role": "Python Developer",
        "company": "TechCorp LLC",
        "salary": "$5,000 - $7,000 USD",
        "skills": "Python, FastAPI, React, PostgreSQL",
        "text_tmpl": "We are hiring a Python Developer!\nCompany: TechCorp LLC\nSalary: $5,000 - $7,000 USD\nSkills: Python, FastAPI, React, PostgreSQL"
    },
    {
        "role": "React Engineer",
        "company": "WebSolutions",
        "salary": "USD 4000",
        "skills": "React, TypeScript, JavaScript",
        "text_tmpl": "Looking for a React Engineer.\nEmployer: WebSolutions\nSalary: USD 4000\nRequired experience: React, TypeScript, JavaScript"
    },
    {
        "role": "Data Analyst",
        "company": "GlobalData",
        "salary": "ETB 15000",
        "skills": "Python, Pandas, PostgreSQL",
        "text_tmpl": "We need a Data Analyst urgently.\nCompany: GlobalData\nSalary: ETB 15000\nTechnologies: Python, Pandas, PostgreSQL"
    },
    {
        "role": "AI Engineer",
        "company": "DeepAI",
        "salary": "$6,000 - $9,000 USD",
        "skills": "Python, scikit-learn, PyTorch",
        "text_tmpl": "Urgent opening for an AI Engineer.\nEmployer: DeepAI\nSalary: $6,000 - $9,000 USD\nTech stack: Python, scikit-learn, PyTorch"
    },
    {
        "role": "Software Engineer",
        "company": "SoftSys",
        "salary": "15000 birr",
        "skills": "JavaScript, Node, Docker",
        "text_tmpl": "Join us as a Software Engineer.\nCompany: SoftSys\nSalary: 15000 birr\nSkills: JavaScript, Node, Docker"
    }
]

async def run_simulated_scrape(channel, session, start_date=None, end_date=None):
    logger.info(f"Running simulated scrape for channel: {channel.channel_name}")
    start_id = channel.last_scraped_message_id or 0

    # Let's generate messages across the last 30 days to build a beautiful trend
    today = datetime.date.today()
    num_messages = random.randint(15, 25)

    for i in range(1, num_messages + 1):
        # Allow cancellation check
        await asyncio.sleep(0.01)

        msg_id = start_id + i
        # Spread messages over the last 28 days
        days_ago = random.randint(0, 28)
        posted_at = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=random.randint(0, 23))

        if start_date and posted_at.date() < start_date:
            continue
        if end_date and posted_at.date() > end_date:
            continue

        # Pick random template
        tmpl = random.choice(MOCK_JOBS_TEMPLATES)

        # Add some random modification to avoid absolute duplicates
        salary_mod = tmpl["salary"]
        if "USD" in salary_mod and "-" in salary_mod:
            low = random.randint(3, 8) * 1000
            high = low + random.randint(1, 4) * 1000
            salary_mod = f"${low:,} - ${high:,} USD"

        message_text = tmpl["text_tmpl"].replace(tmpl["salary"], salary_mod)

        # Check if already exists just in case
        existing = session.query(RawMessage).filter_by(
            channel_id=channel.id,
            telegram_message_id=msg_id
        ).first()

        if not existing:
            raw = RawMessage(
                channel_id=channel.id,
                telegram_message_id=msg_id,
                message_text=message_text,
                posted_at=posted_at
            )
            session.add(raw)
            session.flush() # get raw.id

            fields = extract_job_fields_llm(message_text)

            session.add(ExtractedJob(
                raw_message_id=raw.id,
                job_title=fields["job_title"],
                company=fields["company"],
                salary_range=fields["salary_range"],
                skills_required=fields["skills_required"],
                post_date=posted_at.date()
            ))

            channel.last_scraped_message_id = max(channel.last_scraped_message_id or 0, msg_id)

    channel.last_scraped_at = func.now()
    session.commit()
    logger.info(f"Simulated scrape finished. Scraped {num_messages} messages for {channel.channel_name}.")

async def run_real_scrape(channel, session, start_date=None, end_date=None):
    logger.info(f"Running real Telethon scrape for channel: {channel.channel_name}")

    api_id, api_hash, session_str = get_telegram_credentials(session)
    if not api_id or not api_hash:
        logger.error("Missing TG_API_ID or TG_API_HASH. Cannot run real scrape.")
        return

    if not session_str:
        logger.error("Missing Telegram session. User needs to login via Settings.")
        return

    try:
        client = TelegramClient(StringSession(session_str), api_id=int(api_id), api_hash=api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("Telethon user not authorized. Falling back or skipping.")
            await client.disconnect()
            return


        # Determine iterator args
        iter_kwargs = {"limit": None}
        if start_date and end_date:
            # When scraping a date range, we might fetch older messages
            iter_kwargs["offset_date"] = end_date + datetime.timedelta(days=1)
        else:
            iter_kwargs["min_id"] = channel.last_scraped_message_id or 0

        async for message in client.iter_messages(channel.channel_name, **iter_kwargs):
            if start_date and message.date.date() < start_date:
                # Since messages are retrieved in reverse chronological order, if we pass the start date, we can break
                break
            if end_date and message.date.date() > end_date:
                continue

            if not message.text:
                continue

            existing = session.query(RawMessage).filter_by(
                channel_id=channel.id,
                telegram_message_id=message.id
            ).first()

            if not existing:
                raw = RawMessage(
                    channel_id=channel.id,
                    telegram_message_id=message.id,
                    message_text=message.text,
                    posted_at=message.date
                )
                session.add(raw)
                session.flush()

                fields = extract_job_fields_llm(message.text)
                session.add(ExtractedJob(
                    raw_message_id=raw.id,
                    job_title=fields["job_title"],
                    company=fields["company"],
                    salary_range=fields["salary_range"],
                    skills_required=fields["skills_required"],
                    post_date=message.date.date()
                ))

                channel.last_scraped_message_id = max(channel.last_scraped_message_id or 0, message.id)

        await client.disconnect()

    except FloodWaitError as e:
        logger.warning(f"FloodWaitError: rate limited by Telegram. Must sleep for {e.seconds}s")
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.exception(f"Error scraping real channel {channel.channel_name}: {e}")

    channel.last_scraped_at = func.now()
    session.commit()

async def run_scrape_cycle(db_session):
    logger.info("Starting scraper cycle...")
    active_channels = db_session.query(TargetChannel).filter_by(is_active=True).all()

    api_id, api_hash, session_str = get_telegram_credentials(db_session)
    simulation_mode = os.getenv("SIMULATION_MODE", "true").lower() == "true" or not api_id or not api_hash or not session_str

    for ch in active_channels:
        if simulation_mode:
            await run_simulated_scrape(ch, db_session)
        else:
            await run_real_scrape(ch, db_session)

    logger.info("Scraper cycle finished. Recomputing trend slopes...")
    recompute_all_trend_slopes(db_session)
    logger.info("Trend slopes recomputed successfully.")

# --- On-Demand Scraping Tasks Management ---
active_scrapes = {}

async def _channel_scrape_task_wrapper(channel_id, db_session, start_date, end_date):
    try:
        channel = db_session.query(TargetChannel).filter_by(id=channel_id).first()
        if not channel:
            return

        api_id, api_hash, session_str = get_telegram_credentials(db_session)
        simulation_mode = os.getenv("SIMULATION_MODE", "true").lower() == "true" or not api_id or not api_hash or not session_str

        if simulation_mode:
            await run_simulated_scrape(channel, db_session, start_date, end_date)
        else:
            await run_real_scrape(channel, db_session, start_date, end_date)

        recompute_all_trend_slopes(db_session)
    except asyncio.CancelledError:
        logger.info(f"Scrape task for channel {channel_id} was cancelled.")
    except Exception as e:
        logger.exception(f"Error during on-demand scrape for channel {channel_id}: {e}")
    finally:
        active_scrapes.pop(channel_id, None)
        db_session.close()

def start_channel_scrape_task(channel_id, start_date, end_date):
    if channel_id in active_scrapes:
        raise ValueError("A scrape task is already running for this channel.")

    db_session = SessionLocal()
    task = asyncio.create_task(_channel_scrape_task_wrapper(channel_id, db_session, start_date, end_date))
    active_scrapes[channel_id] = task

def cancel_channel_scrape_task(channel_id):
    if channel_id in active_scrapes:
        task = active_scrapes[channel_id]
        task.cancel()
        return True
    return False

# Real-time listener
_listener_client = None

async def start_listener(db_session=None):
    global _listener_client
    if _listener_client:
        await stop_listener()

    close_db = False
    if db_session is None:
        db_session = SessionLocal()
        close_db = True

    try:
        api_id, api_hash, session_str = get_telegram_credentials(db_session)
        simulation_mode = os.getenv("SIMULATION_MODE", "true").lower() == "true" or not api_id or not api_hash or not session_str

        if simulation_mode:
            logger.info("Simulation mode active. Real-time listener not started.")
            return

        active_channels = db_session.query(TargetChannel).filter_by(is_active=True).all()
        channel_names = [ch.channel_name for ch in active_channels]

        if not channel_names:
            logger.info("No active channels to monitor. Real-time listener not started.")
            return

        _listener_client = TelegramClient(StringSession(session_str), api_id=int(api_id), api_hash=api_hash)
        await _listener_client.connect()
        if not await _listener_client.is_user_authorized():
            logger.error("Telethon user not authorized. Real-time listener cannot start.")
            await _listener_client.disconnect()
            _listener_client = None
            return

        @_listener_client.on(events.NewMessage(chats=channel_names))
        async def handler(event):
            logger.info(f"New real-time message received in {event.chat.username or event.chat.title}")
            if not event.message.text:
                return

            db = SessionLocal()
            try:
                # Find channel ID
                chat_identifier = ""
                if event.chat.username:
                    chat_identifier = f"@{event.chat.username}"
                elif event.chat.title:
                    chat_identifier = event.chat.title

                channel = None
                if chat_identifier:
                    channel = db.query(TargetChannel).filter(TargetChannel.channel_name.ilike(f"%{chat_identifier}%")).first()

                if not channel:
                    # Fallback check
                    for ch in active_channels:
                        if ch.channel_name.lower().replace("@", "") == str(event.chat.username).lower():
                            channel = ch
                            break

                if not channel:
                    logger.warning(f"Could not map incoming message to a known active channel: {chat_identifier}")
                    return

                existing = db.query(RawMessage).filter_by(
                    channel_id=channel.id,
                    telegram_message_id=event.message.id
                ).first()

                if not existing:
                    raw = RawMessage(
                        channel_id=channel.id,
                        telegram_message_id=event.message.id,
                        message_text=event.message.text,
                        posted_at=event.message.date
                    )
                    db.add(raw)
                    db.flush()

                    fields = extract_job_fields_llm(event.message.text)
                    db.add(ExtractedJob(
                        raw_message_id=raw.id,
                        job_title=fields["job_title"],
                        company=fields["company"],
                        salary_range=fields["salary_range"],
                        skills_required=fields["skills_required"],
                        post_date=event.message.date.date()
                    ))

                    channel.last_scraped_message_id = max(channel.last_scraped_message_id or 0, event.message.id)
                    channel.last_scraped_at = func.now()
                    db.commit()

                    # Optional: Recompute trends in background or lightly here
                    # recompute_all_trend_slopes(db)
            except Exception as e:
                logger.exception(f"Error processing real-time message: {e}")
            finally:
                db.close()

        logger.info(f"Real-time listener started for {len(channel_names)} channels.")

    except Exception as e:
        logger.exception(f"Failed to start real-time listener: {e}")
    finally:
        if close_db:
            db_session.close()

async def stop_listener():
    global _listener_client
    if _listener_client:
        logger.info("Stopping real-time listener...")
        await _listener_client.disconnect()
        _listener_client = None
        logger.info("Real-time listener stopped.")

import threading

def restart_listener_sync():
    """Synchronous helper to restart listener in background."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(start_listener())
    except RuntimeError:
        # If no loop is running in this thread, try to create a new one in a daemon thread
        def start_in_new_loop():
            asyncio.run(start_listener())
        threading.Thread(target=start_in_new_loop, daemon=True).start()
