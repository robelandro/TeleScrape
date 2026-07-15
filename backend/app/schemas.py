from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "viewer"  # 'admin' | 'viewer'

class UserResponse(UserBase):
    id: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    token: str
    username: str
    role: str

class LoginRequest(BaseModel):
    username: str
    password: str

class ChannelBase(BaseModel):
    channel_name: str

class ChannelCreate(ChannelBase):
    pass

class ChannelResponse(ChannelBase):
    id: int
    is_active: bool
    last_scraped_message_id: int
    last_scraped_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class JobResponse(BaseModel):
    id: int
    job_title: str
    company: str
    salary_range: Optional[str] = None
    skills_required: str  # JSON array string
    post_date: date

    class Config:
        from_attributes = True

class DashboardSummaryResponse(BaseModel):
    total_jobs_scraped: int
    monitored_sources: int
    fastest_growing: str

class ChartDataPoint(BaseModel):
    date_str: str
    post_count: int

class CategorySeriesPoint(BaseModel):
    date_str: str
    values: dict  # e.g. {"Python Developer": 5, "React Engineer": 4}

class DashboardChartsResponse(BaseModel):
    volume_by_day: List[ChartDataPoint]
    category_trends: List[dict]  # Recharts friendly list of dicts with date and category counts
