import os
import re
import json
import spacy
import logging
from spacy.pipeline import EntityRuler
import openai

logger = logging.getLogger(__name__)

nlp = spacy.load("en_core_web_sm")

# Add EntityRuler to match roles and technologies
ruler = nlp.add_pipe("entity_ruler", before="ner")

patterns = [
    {"label": "ROLE", "pattern": [{"LOWER": "python"}, {"LOWER": "developer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "python"}, {"LOWER": "engineer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "react"}, {"LOWER": "engineer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "react"}, {"LOWER": "developer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "data"}, {"LOWER": "analyst"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "data"}, {"LOWER": "engineer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "ai"}, {"LOWER": "developer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "ai"}, {"LOWER": "engineer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "full"}, {"LOWER": "stack"}, {"LOWER": "developer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "frontend"}, {"LOWER": "developer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "backend"}, {"LOWER": "developer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "node"}, {"LOWER": "developer"}]},
    {"label": "ROLE", "pattern": [{"LOWER": "software"}, {"LOWER": "engineer"}]},

    {"label": "TECH", "pattern": [{"LOWER": "fastapi"}]},
    {"label": "TECH", "pattern": [{"LOWER": "postgresql"}]},
    {"label": "TECH", "pattern": [{"LOWER": "react"}]},
    {"label": "TECH", "pattern": [{"LOWER": "django"}]},
    {"label": "TECH", "pattern": [{"LOWER": "python"}]},
    {"label": "TECH", "pattern": [{"LOWER": "node"}]},
    {"label": "TECH", "pattern": [{"LOWER": "typescript"}]},
    {"label": "TECH", "pattern": [{"LOWER": "javascript"}]},
    {"label": "TECH", "pattern": [{"LOWER": "docker"}]},
    {"label": "TECH", "pattern": [{"LOWER": "kubernetes"}]},
    {"label": "TECH", "pattern": [{"LOWER": "pandas"}]},
    {"label": "TECH", "pattern": [{"LOWER": "scikit-learn"}]},
]
ruler.add_patterns(patterns)

# A salary pattern that catches things like "$5,000 - $7,000 USD", "USD 4000", "ETB 15000", "15000 birr", etc.
SALARY_RE = re.compile(
    r'(?:'
    r'(?:\$|USD|ETB|birr)\s?[\d,]+\s?[-–]\s?(?:\$|USD|ETB|birr)?\s?[\d,]+\s?(?:USD|ETB|birr)?|'
    r'[\d,]+\s?[-–]\s?(?:\$|USD|ETB|birr)?\s?[\d,]+\s?(?:USD|ETB|birr)|'
    r'(?:\$|USD|ETB|birr)\s?[\d,]+|'
    r'[\d,]+\s?(?:USD|ETB|birr)'
    r')',
    re.IGNORECASE
)

# Company heuristics
COMPANY_RE = re.compile(
    r'(?:company|employer|at|hiring\s+by)\s*:\s*([^\n\r]+)', re.IGNORECASE
)

CANONICAL_TECHS = {
    "fastapi": "FastAPI",
    "postgresql": "PostgreSQL",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "scikit-learn": "scikit-learn",
}

def extract_job_fields(text: str) -> dict:
    doc = nlp(text)

    roles = [ent.text for ent in doc.ents if ent.label_ == "ROLE"]
    techs = [ent.text for ent in doc.ents if ent.label_ == "TECH"]

    # Deduplicate and match role names titlecase/exact representation
    unique_roles = []
    for r in roles:
        r_title = r.strip()
        # Clean extra whitespace
        r_title = " ".join(r_title.split())
        r_title = r_title.title()
        if r_title not in unique_roles:
            unique_roles.append(r_title)

    unique_techs = sorted(list(set(CANONICAL_TECHS.get(t.lower(), t.title()) for t in techs)))

    salary_match = SALARY_RE.search(text)
    salary_range = salary_match.group(0).strip() if salary_match else None

    # Try company heuristic match
    company_match = COMPANY_RE.search(text)
    company = "Unknown"
    if company_match:
        company = company_match.group(1).strip()
        # Clean company name
        company = company.split(",")[0].split(".")[0].strip()
    else:
        # Simple fallback checks
        lines = text.split("\n")
        for line in lines:
            if "company:" in line.lower() or "employer:" in line.lower():
                parts = line.split(":")
                if len(parts) > 1:
                    company = parts[1].strip()
                    break

    job_title = unique_roles[0] if unique_roles else "General Staff"

    return {
        "job_title": job_title,
        "skills_required": json.dumps(unique_techs),
        "salary_range": salary_range,
        "company": company
    }

def extract_job_fields_llm(text: str) -> dict:
    """Attempt to extract fields using OpenAI LLM first, and gracefully fallback."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            client = openai.OpenAI(api_key=api_key)
            prompt = f"""
            You are a highly capable data extraction bot.
            Extract the following fields from the job posting below.
            Return the output strictly as a JSON object with the exact keys:
            - "job_title": string
            - "company": string (use "Unknown" if not found)
            - "salary_range": string (or null if not found)
            - "skills_required": list of strings (e.g. ["Python", "Docker"])

            Job Posting:
            \"\"\"
            {text}
            \"\"\"
            """
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if content:
                data = json.loads(content)
                return {
                    "job_title": data.get("job_title", "General Staff"),
                    "company": data.get("company", "Unknown"),
                    "salary_range": data.get("salary_range"),
                    "skills_required": json.dumps(data.get("skills_required", []))
                }
        except Exception as e:
            logger.error(f"OpenAI extraction failed, falling back to spaCy: {e}")

    # Fallback to existing logic
    return extract_job_fields(text)
