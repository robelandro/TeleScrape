import unittest
import json
from app.nlp import extract_job_fields

class TestNLPExtractor(unittest.TestCase):
    def test_python_developer_post(self):
        text = """
        We are hiring a Python Developer!
        Company: TechCorp LLC.
        Salary: $5,000 - $7,000 USD
        Skills: Python, FastAPI, React, PostgreSQL.
        """
        fields = extract_job_fields(text)
        self.assertEqual(fields["job_title"], "Python Developer")
        self.assertEqual(fields["company"], "TechCorp LLC")
        self.assertEqual(fields["salary_range"], "$5,000 - $7,000 USD")
        skills = json.loads(fields["skills_required"])
        self.assertIn("Python", skills)
        self.assertIn("FastAPI", skills)
        self.assertIn("React", skills)
        self.assertIn("PostgreSQL", skills)

    def test_react_engineer_post(self):
        text = """
        Looking for a React Engineer.
        Employer: WebSolutions.
        Salary: USD 4000.
        Required experience: React, TypeScript, JavaScript.
        """
        fields = extract_job_fields(text)
        self.assertEqual(fields["job_title"], "React Engineer")
        self.assertEqual(fields["company"], "WebSolutions")
        self.assertEqual(fields["salary_range"], "USD 4000")
        skills = json.loads(fields["skills_required"])
        self.assertIn("React", skills)
        self.assertIn("TypeScript", skills)

    def test_general_staff_fallback(self):
        text = "Random post without job title, but has salary of ETB 15000."
        fields = extract_job_fields(text)
        self.assertEqual(fields["job_title"], "General Staff")
        self.assertEqual(fields["salary_range"], "ETB 15000")
        self.assertEqual(fields["company"], "Unknown")

if __name__ == "__main__":
    unittest.main()
