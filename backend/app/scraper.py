import os
import asyncio
import random
import datetime
import logging
from sqlalchemy import func
from telethon import TelegramClient
from telethon.errors import FloodWaitError

from app.models import TargetChannel, RawMessage, ExtractedJob
from app.nlp import extract_job_fields
from app.forecasting import recompute_all_trend_slopes

logger = logging.getLogger(__name__)

# Telethon configuration
TG_API_ID = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true" or not TG_API_ID or not TG_API_HASH

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

async def run_simulated_scrape(channel, session):
    logger.info(f"Running simulated scrape for channel: {channel.channel_name}")
    start_id = channel.last_scraped_message_id or 0

    # Let's generate messages across the last 30 days to build a beautiful trend
    today = datetime.date.today()
    num_messages = random.randint(15, 25)

    for i in range(1, num_messages + 1):
        msg_id = start_id + i
        # Spread messages over the last 28 days
        days_ago = random.randint(0, 28)
        posted_at = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=random.randint(0, 23))

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

            fields = extract_job_fields(message_text)

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

async def run_real_scrape(channel, session):
    logger.info(f"Running real Telethon scrape for channel: {channel.channel_name}")
    try:
        # User session file saved inside a local data folder
        client = TelegramClient("telescrape_session", api_id=TG_API_ID, api_hash=TG_API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("Telethon user not authorized. Falling back or skipping.")
            await client.disconnect()
            return

        async for message in client.iter_messages(
            channel.channel_name,
            min_id=channel.last_scraped_message_id or 0,
            limit=None
        ):
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

                fields = extract_job_fields(message.text)
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

    for ch in active_channels:
        if SIMULATION_MODE:
            await run_simulated_scrape(ch, db_session)
        else:
            await run_real_scrape(ch, db_session)

    logger.info("Scraper cycle finished. Recomputing trend slopes...")
    recompute_all_trend_slopes(db_session)
    logger.info("Trend slopes recomputed successfully.")
