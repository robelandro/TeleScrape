import unittest
import json
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, AnalyticsCache, TargetChannel, ExtractedJob
from app.mcp_server import get_market_trends, add_telegram_source, search_active_jobs
import app.mcp_server as mcp_mod

# Override database connection in mcp_server modules to use shared in-memory DB or test engine
# Since we import mcp_server, we can temporarily patch its DB session creator if we want, or create our own setup.
# Actually, we can patch `SessionLocal` inside `app.mcp_server` and `app.nlp`!
# Let's do that dynamically in setUp.

class TestMCP(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.TestingSessionLocal = sessionmaker(bind=self.engine)

        # Patch the SessionLocal used in mcp_server
        self.original_session_local = mcp_mod.SessionLocal
        mcp_mod.SessionLocal = self.TestingSessionLocal

    def tearDown(self):
        mcp_mod.SessionLocal = self.original_session_local

    def test_get_market_trends(self):
        db = self.TestingSessionLocal()
        db.add_all([
            AnalyticsCache(job_category="Python Developer", total_posts_30d=15, growth_slope=3.5),
            AnalyticsCache(job_category="React Engineer", total_posts_30d=25, growth_slope=5.2)
        ])
        db.commit()
        db.close()

        trends = get_market_trends()
        self.assertEqual(len(trends), 2)
        self.assertEqual(trends[0]["job_category"], "React Engineer") # ordered by slope desc
        self.assertEqual(trends[0]["growth_slope"], 5.2)

    def test_add_telegram_source(self):
        # Add channel
        res = add_telegram_source("python_gigs_mcp")
        self.assertTrue(res["success"])

        db = self.TestingSessionLocal()
        channel = db.query(TargetChannel).filter_by(channel_name="@python_gigs_mcp").first()
        self.assertIsNotNone(channel)
        self.assertTrue(channel.is_active)
        db.close()

    def test_search_active_jobs(self):
        db = self.TestingSessionLocal()
        db.add_all([
            ExtractedJob(
                raw_message_id=1,
                job_title="AI Engineer",
                company="DeepMind",
                salary_range="$10,000 USD",
                skills_required='["Python", "PyTorch"]',
                post_date=datetime.date.today()
            ),
            ExtractedJob(
                raw_message_id=2,
                job_title="Django Engineer",
                company="WebInc",
                salary_range="USD 3500",
                skills_required='["Python", "Django"]',
                post_date=datetime.date.today()
            )
        ])
        db.commit()
        db.close()

        # Search Python
        results = search_active_jobs(query="Python")
        self.assertEqual(len(results), 2)

        # Search Django
        results_django = search_active_jobs(query="Django")
        self.assertEqual(len(results_django), 1)
        self.assertEqual(results_django[0]["job_title"], "Django Engineer")

        # Search with min_salary filter
        results_salary = search_active_jobs(query="Python", min_salary=5000)
        self.assertEqual(len(results_salary), 1)
        self.assertEqual(results_salary[0]["job_title"], "AI Engineer")

if __name__ == "__main__":
    unittest.main()
