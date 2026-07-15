import unittest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, ExtractedJob, AnalyticsCache
from app.forecasting import compute_growth_slope, recompute_all_trend_slopes

class TestForecasting(unittest.TestCase):
    def setUp(self):
        # In-memory database for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_insufficient_data(self):
        # Insert less than 4 posts
        today = datetime.date.today()
        for i in range(3):
            self.session.add(ExtractedJob(
                raw_message_id=i + 1,
                job_title="Python Developer",
                post_date=today
            ))
        self.session.commit()

        slope = compute_growth_slope("Python Developer", self.session)
        self.assertEqual(slope, 0.0)

    def test_growing_trend_slope(self):
        # Let's mock a rising trend
        # Week 0: 2 posts, Week 1: 4 posts, Week 2: 6 posts, Week 3: 8 posts
        # total posts >= 4
        today = datetime.date.today()
        raw_id = 1

        # Week 0 (0 to 6 days from starting point)
        for _ in range(2):
            self.session.add(ExtractedJob(
                raw_message_id=raw_id,
                job_title="React Engineer",
                post_date=today - datetime.timedelta(days=21)
            ))
            raw_id += 1

        # Week 1
        for _ in range(4):
            self.session.add(ExtractedJob(
                raw_message_id=raw_id,
                job_title="React Engineer",
                post_date=today - datetime.timedelta(days=14)
            ))
            raw_id += 1

        # Week 2
        for _ in range(6):
            self.session.add(ExtractedJob(
                raw_message_id=raw_id,
                job_title="React Engineer",
                post_date=today - datetime.timedelta(days=7)
            ))
            raw_id += 1

        # Week 3
        for _ in range(8):
            self.session.add(ExtractedJob(
                raw_message_id=raw_id,
                job_title="React Engineer",
                post_date=today
            ))
            raw_id += 1

        self.session.commit()

        slope = compute_growth_slope("React Engineer", self.session)
        # Week counts are [2, 4, 6, 8] for week indices [0, 1, 2, 3]
        # Slope should be positive (2.0)
        self.assertGreater(slope, 0.0)
        self.assertAlmostEqual(slope, 2.0)

        # Run full slopes recomputation
        recompute_all_trend_slopes(self.session)

        cache_entry = self.session.query(AnalyticsCache).filter_by(job_category="React Engineer").first()
        self.assertIsNotNone(cache_entry)
        self.assertEqual(cache_entry.total_posts_30d, 20)
        self.assertAlmostEqual(cache_entry.growth_slope, 2.0)

if __name__ == "__main__":
    unittest.main()
