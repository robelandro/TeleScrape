from sqlalchemy import Column, Integer, String, Boolean, Text, Date, DateTime, ForeignKey, UniqueConstraint, func, Float
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")  # 'admin' | 'viewer'
    created_at = Column(DateTime, server_default=func.now())

class TargetChannel(Base):
    __tablename__ = "target_channels"
    id = Column(Integer, primary_key=True)
    channel_name = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    added_by = Column(Integer, ForeignKey("users.id"))
    last_scraped_message_id = Column(Integer, default=0)
    last_scraped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class RawMessage(Base):
    __tablename__ = "raw_messages"
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("target_channels.id"))
    telegram_message_id = Column(Integer, nullable=False)
    message_text = Column(Text)
    posted_at = Column(DateTime, nullable=False)
    scraped_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("channel_id", "telegram_message_id"),)

class ExtractedJob(Base):
    __tablename__ = "extracted_jobs"
    id = Column(Integer, primary_key=True)
    raw_message_id = Column(Integer, ForeignKey("raw_messages.id"), unique=True)
    job_title = Column(String(150), nullable=False)
    company = Column(String(100), default="Unknown")
    salary_range = Column(String(100), nullable=True)
    skills_required = Column(Text, nullable=True)  # JSON array string
    post_date = Column(Date, nullable=False)

class AnalyticsCache(Base):
    __tablename__ = "analytics_cache"
    job_category = Column(String(100), primary_key=True)
    total_posts_30d = Column(Integer, nullable=False)
    growth_slope = Column(Float, nullable=False)
    last_updated_at = Column(DateTime, server_default=func.now())
