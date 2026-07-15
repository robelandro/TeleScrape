import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import get_db
from app.models import Base, User, TargetChannel, ExtractedJob
from app.auth import get_password_hash

# Share a single connection across all sessions (StaticPool) with an in-memory DB
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

class TestAPI(unittest.TestCase):
    def setUp(self):
        # Create tables on the shared in-memory DB
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)

        # Seed test db
        db = TestingSessionLocal()
        self.admin = User(
            username="admin_test",
            password_hash=get_password_hash("password123"),
            role="admin"
        )
        self.viewer = User(
            username="viewer_test",
            password_hash=get_password_hash("password123"),
            role="viewer"
        )
        db.add_all([self.admin, self.viewer])
        db.commit()
        db.refresh(self.admin)
        db.refresh(self.viewer)
        db.close()

    def tearDown(self):
        # Clean up database tables
        Base.metadata.drop_all(bind=engine)

    def test_login_success(self):
        resp = self.client.post("/api/auth/login", json={
            "username": "admin_test",
            "password": "password123"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("token", data)
        self.assertEqual(data["username"], "admin_test")
        self.assertEqual(data["role"], "admin")

    def test_login_failure(self):
        resp = self.client.post("/api/auth/login", json={
            "username": "admin_test",
            "password": "wrong_password"
        })
        self.assertEqual(resp.status_code, 400)

    def test_channels_rbac_and_crud(self):
        # 1. Login as admin
        login_resp = self.client.post("/api/auth/login", json={
            "username": "admin_test",
            "password": "password123"
        })
        admin_token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Add channel (admin)
        add_resp = self.client.post("/api/channels", json={"channel_name": "@react_gigs_test"}, headers=headers)
        self.assertEqual(add_resp.status_code, 200)
        chan_data = add_resp.json()
        self.assertEqual(chan_data["channel_name"], "@react_gigs_test")

        # 3. Add same channel should fail
        add_resp_dup = self.client.post("/api/channels", json={"channel_name": "@react_gigs_test"}, headers=headers)
        self.assertEqual(add_resp_dup.status_code, 400)

        # 4. Login as viewer
        login_resp_viewer = self.client.post("/api/auth/login", json={
            "username": "viewer_test",
            "password": "password123"
        })
        viewer_token = login_resp_viewer.json()["token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        # 5. Try adding channel as viewer (should fail)
        add_resp_fail = self.client.post("/api/channels", json={"channel_name": "@viewer_unauthorized"}, headers=viewer_headers)
        self.assertEqual(add_resp_fail.status_code, 403)

        # 6. Read channels list as viewer
        get_resp = self.client.get("/api/channels", headers=viewer_headers)
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(len(get_resp.json()), 1)

        # 7. Delete channel as admin
        del_resp = self.client.delete(f"/api/channels/{chan_data['id']}", headers=headers)
        self.assertEqual(del_resp.status_code, 200)

    def test_jobs_dashboard_endpoints(self):
        # Login as viewer
        login_resp = self.client.post("/api/auth/login", json={
            "username": "viewer_test",
            "password": "password123"
        })
        token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Seed some jobs directly
        db = TestingSessionLocal()
        import datetime
        job1 = ExtractedJob(
            raw_message_id=101,
            job_title="Python Developer",
            company="TechCorp",
            salary_range="$5,000 USD",
            skills_required='["Python"]',
            post_date=datetime.date.today()
        )
        job2 = ExtractedJob(
            raw_message_id=102,
            job_title="React Engineer",
            company="SoftCorp",
            salary_range="USD 3000",
            skills_required='["React"]',
            post_date=datetime.date.today() - datetime.timedelta(days=1)
        )
        db.add_all([job1, job2])
        db.commit()
        db.close()

        # Test GET jobs
        get_jobs_resp = self.client.get("/api/jobs", headers=headers)
        self.assertEqual(get_jobs_resp.status_code, 200)
        jobs_data = get_jobs_resp.json()
        self.assertEqual(jobs_data["total"], 2)

        # Test filter by title
        get_jobs_resp_f = self.client.get("/api/jobs?title=python", headers=headers)
        self.assertEqual(get_jobs_resp_f.json()["total"], 1)

        # Test filter by min_salary
        get_jobs_resp_s = self.client.get("/api/jobs?min_salary=4000", headers=headers)
        self.assertEqual(get_jobs_resp_s.json()["total"], 1) # matches Python Developer ($5,000 USD)

        # Test GET summary
        summary_resp = self.client.get("/api/dashboard/summary", headers=headers)
        self.assertEqual(summary_resp.status_code, 200)
        self.assertEqual(summary_resp.json()["total_jobs_scraped"], 2)

        # Test GET charts
        charts_resp = self.client.get("/api/dashboard/charts", headers=headers)
        self.assertEqual(charts_resp.status_code, 200)
        self.assertIn("volume_by_day", charts_resp.json())
        self.assertIn("category_trends", charts_resp.json())

if __name__ == "__main__":
    unittest.main()
