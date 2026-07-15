import datetime
import pandas as pd
from sklearn.linear_model import LinearRegression
from app.models import ExtractedJob, AnalyticsCache
from sqlalchemy import func

def compute_growth_slope(job_category: str, session) -> float:
    rows = session.query(ExtractedJob.post_date).filter(
        ExtractedJob.job_title == job_category
    ).all()
    if len(rows) < 4:
        return 0.0

    df = pd.DataFrame(rows, columns=["post_date"])
    df["post_datetime"] = pd.to_datetime(df["post_date"])

    # Calculate relative week index to avoid wrap-around year boundaries
    min_date = df["post_datetime"].min()
    df["week_index"] = (df["post_datetime"] - min_date).dt.days // 7

    weekly_counts = df.groupby("week_index").size().reset_index(name="count")

    # If we only have 1 week of data, slope is 0.0
    if len(weekly_counts) < 2:
        return 0.0

    X = weekly_counts["week_index"].values.reshape(-1, 1)
    y = weekly_counts["count"].values

    model = LinearRegression().fit(X, y)
    return float(model.coef_[0])

def recompute_all_trend_slopes(session):
    # Find all distinct job titles
    distinct_titles = session.query(ExtractedJob.job_title).distinct().all()
    distinct_titles = [r[0] for r in distinct_titles if r[0]]

    thirty_days_ago = datetime.date.today() - datetime.timedelta(days=30)

    for title in distinct_titles:
        # Compute growth slope
        slope = compute_growth_slope(title, session)

        # Count total posts in the last 30 days
        total_30d = session.query(func.count(ExtractedJob.id)).filter(
            ExtractedJob.job_title == title,
            ExtractedJob.post_date >= thirty_days_ago
        ).scalar() or 0

        # Update or insert into AnalyticsCache
        cache_entry = session.query(AnalyticsCache).filter_by(job_category=title).first()
        if cache_entry:
            cache_entry.total_posts_30d = total_30d
            cache_entry.growth_slope = slope
            cache_entry.last_updated_at = func.now()
        else:
            cache_entry = AnalyticsCache(
                job_category=title,
                total_posts_30d=total_30d,
                growth_slope=slope
            )
            session.add(cache_entry)

    session.commit()
