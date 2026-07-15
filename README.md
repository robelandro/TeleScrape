# TeleScrape: Local Telegram Job Analytics System

TeleScrape is a self-contained local system that scrapes public Telegram job channels, extracts structured job information (roles, skills, companies, salaries) using local NLP, forecasts weekly category growth using lightweight ML, and exposes everything through a REST API, an interactive React portal, and a Model Context Protocol (MCP) server.

The entire system is designed to run locally, on-device—no cloud APIs or cloud AI calls required.

---

## Key Features

1. **Incremental Scraper:** Driven by Telethon (user session) and APScheduler. It tracks `last_scraped_message_id` per channel to scrape only new messages. Handles rate limits with backoff automatically.
2. **High-Fidelity Simulation Fallback:** If Telegram API credentials are not provided or if `SIMULATION_MODE=true` is set, the scraper falls back to an integrated sandbox simulator. This generates realistic, randomized job postings across the last 30 days to build beautifully populated dashboards, charts, and slopes immediately on startup.
3. **Local NLP Extraction:** Leverages spaCy (`en_core_web_sm` with a custom `EntityRuler` pipeline) and high-precision regex to identify job roles, companies, salary ranges, and map technologies (e.g. FastAPI, PostgreSQL, TypeScript) into canonical, structured JSON arrays.
4. **Lightweight ML Trends Forecasting:** A nightly background task aggregates job categories by relative week index and fits a scikit-learn `LinearRegression` model to calculate the weekly growth slope (coefficient), saving computed rankings in `AnalyticsCache`.
5. **FastAPI REST API & RBAC:** Secure API endpoints guarded by JWT authentication with distinct `admin` (can manage channels) and `viewer` (read-only) roles. Contains paginated job retrieval with text, skill, and minimum-salary filters.
6. **Unified FastMCP Server:** Built with FastMCP (using standard ASGI lifespan management) and mounted directly under the FastAPI server at `/mcp`, allowing local LLMs (like Claude Desktop or Cursor) to execute natural language queries against active trends, search job listings, or register new sources.
7. **Interactive React UI Portal:** Designed with React, Vite, Tailwind CSS v4, TanStack Query, and Recharts. Includes responsive trend line charts, daily ingestion bar charts, and administrative channel controls.

---

## Technical Architecture

```
                                      +--------------------------+
                                      |  Telegram (User Session) |
                                      +-------------+------------+
                                                     |
                                                     | Telethon (user account, not bot)
                                                     v
+------------------+                  +-------------+------------+
|  MCP Clients      |                  |  Scraper Job (APScheduler)|
|  (Claude/Cursor)  |                  +-------------+------------+
+--------+----------+                                |
         |                                           v
         | MCP (stdio / HTTP)          +-------------+------------+
         v                             | Local AI/ML Processing    |
+--------+----------+  (in-process)    |  - spaCy EntityRuler       |
|  FastMCP Server    |<---------------->|  - Regex (salary/skills)  |
+--------------------+                  |  - sklearn LinearRegression|
                                        +-------------+------------+
                                                      |
+--------------------+                               v
|  React UI (Vite)   |<-------------->  +-------------+------------+
+--------------------+     REST/JWT     |  FastAPI Backend          |
                                        +-------------+------------+
                                                      |
                                                      v
                                        +-------------+------------+
                                        | SQLite (SQLAlchemy+Alembic)|
                                        +----------------------------+
```

---

## Step-by-Step Setup Guide

### Option A: Run via Docker Compose (Recommended)

This is the easiest way to launch the entire system. It builds the backend (FastAPI, scraper, scheduler, FastMCP) and the frontend (built assets served through Nginx, which acts as a reverse proxy routing `/api` and `/mcp` requests directly to the backend container).

1. Clone or access the project repository.
2. Build and run the containers:
   ```bash
   docker compose up --build
   ```
3. Open your browser and navigate to:
   - **React Portal:** [http://localhost:5173](http://localhost:5173)
   - **FastAPI Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Model Context Protocol Endpoint:** `http://localhost:5173/mcp` (or `http://localhost:8000/mcp`)
4. Sign in with one of the pre-seeded demo accounts:
   - **Admin (full read/write):** Username: `admin` | Password: `admin123`
   - **Viewer (read-only):** Username: `viewer` | Password: `viewer123`

---

### Option B: Local Setup for Development

If you prefer to run the API, scraper, and React frontend directly on your local system:

#### 1. Setup the Backend
1. Go to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Download the spaCy English model:
   ```bash
   python -m spacy download en_core_web_sm
   ```
4. Run Alembic migrations to set up the SQLite database:
   ```bash
   alembic upgrade head
   ```
5. Seed the database with demo users and initial target channels:
   ```bash
   PYTHONPATH=. python app/seed.py
   ```
6. Start the FastAPI backend server:
   ```bash
   PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

#### 2. Setup the Frontend
1. Open a new terminal and navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Start the Vite React development server:
   ```bash
   npm run dev -- --host 127.0.0.1 --port 5173
   ```
4. Access the portal at [http://localhost:5173](http://localhost:5173).

---

## Configuration & Environment Variables

You can customize the system behavior in `docker-compose.yml` or your local terminal environment:

*   `DATABASE_URL`: SQLAlchemy connection string (Defaults to `sqlite:///./backend/data.db`).
*   `JWT_SECRET`: Secret key used to sign JSON Web Tokens.
*   `SIMULATION_MODE`: Set to `true` (default) to run the high-fidelity mock scraper. Set to `false` to attempt real scrapes.
*   `TG_API_ID`: Your Telegram API ID (required for real scraping).
*   `TG_API_HASH`: Your Telegram API Hash (required for real scraping).

---

## MCP Server Integration

The FastMCP server is hosted inside the main FastAPI process and mounted under the `/mcp` route.

### Exposing to Claude Desktop or Cursor
To let your AI assistants use the tools of this project directly, add the following configuration into your Claude Desktop configuration file (typically `~/.codeium/` or `~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "telescrape": {
      "command": "python3",
      "args": ["-m", "app.mcp_server"],
      "env": {
        "DATABASE_URL": "sqlite:////path/to/your/backend/data.db",
        "PYTHONPATH": "/path/to/your/backend"
      }
    }
  }
}
```

### Available Tools:
1.  `get_market_trends(limit: int)`: Retrieve highest-growth job categories sorted by calculated Linear Regression slope.
2.  `add_telegram_source(channel_name: str)`: Monitored a new Telegram job channel username.
3.  `search_active_jobs(query: str, min_salary: int)`: Full-text search over indexed jobs.

---

## Running Tests

All core extraction, forecasting, scraping, and REST API layers are fully tested. To execute all backend tests, navigate to the `backend` directory and run:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p "test_*.py"
```

To run a specific test suite:
- **NLP Extraction Tests:** `PYTHONPATH=. python3 -m unittest tests/test_nlp.py`
- **Forecasting ML Tests:** `PYTHONPATH=. python3 -m unittest tests/test_forecasting.py`
- **Scraper Tests:** `PYTHONPATH=. python3 -m unittest tests/test_scraper.py`
- **REST API Integration Tests:** `PYTHONPATH=. python3 -m unittest tests/test_api.py`
- **MCP Tool Tests:** `PYTHONPATH=. python3 -m unittest tests/test_mcp.py`
