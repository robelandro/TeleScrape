import unittest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, TargetChannel, RawMessage, ExtractedJob, AnalyticsCache
from app.scraper import run_scrape_cycle

class TestScraper(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_simulated_scrape(self):
        # Insert a target channel
        channel = TargetChannel(
            channel_name="@react_gigs",
            is_active=True
        )
        self.session.add(channel)
        self.session.commit()

        # Run simulated scrape cycle inside asyncio loop
        asyncio.run(run_scrape_cycle(self.session))

        # Query and assert we have scraped messages
        raw_msgs = self.session.query(RawMessage).all()
        extracted_jobs = self.session.query(ExtractedJob).all()
        analytics_caches = self.session.query(AnalyticsCache).all()

        self.assertGreater(len(raw_msgs), 0)
        self.assertGreater(len(extracted_jobs), 0)
        self.assertEqual(len(raw_msgs), len(extracted_jobs))

        # Verify last_scraped_message_id is updated
        updated_channel = self.session.query(TargetChannel).first()
        self.assertGreater(updated_channel.last_scraped_message_id, 0)
        self.assertIsNotNone(updated_channel.last_scraped_at)

        # Check that we have computed growth slopes
        self.assertGreater(len(analytics_caches), 0)

if __name__ == "__main__":
    unittest.main()
